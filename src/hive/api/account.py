# Copyright (c) 2026 John Carter. All rights reserved.
"""
Account self-service endpoints.

- DELETE /api/account        — GDPR Article 17 right-to-erasure
- GET    /api/account/export — GDPR Article 20 right-to-portability / CCPA §1798.100
- GET    /api/account/stats  — Personal usage analytics (#535)
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hive.api._auth import require_mgmt_user
from hive.models import ActivityEvent, EventType
from hive.quota import _exempt_users, get_memory_limit, get_storage_bytes_limit
from hive.storage import HiveStorage

router = APIRouter(tags=["account"])

EXPORT_RATE_LIMIT_SECONDS = 300  # one export per 5 minutes per user
EXPORT_ACTIVITY_LOOKBACK_DAYS = 90  # activity-log retention per Privacy Policy §9
EXPORT_CLIENTS_LIMIT = 1000  # safety cap; quota is much lower in practice

# #535 — stats endpoint config
_STATS_CACHE_TTL = 60.0  # seconds; per-user, per-window
_STATS_EVENT_LIMIT = 100_000  # upper bound when pulling events for aggregation
_STATS_TOP_RECALLED_N = 10


def _storage() -> HiveStorage:
    return HiveStorage()


# Module-level cache keyed by ``f"{user_id}:{window_days}"``; stores
# (timestamp, data) tuples. ``_STATS_CACHE_TTL`` is honoured on read.
# Separate from ``_auth``-flow caches so a delete_account can wipe all
# entries for a user in a single loop.
_STATS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class AccountDeleteRequest(BaseModel):
    confirm: bool = False


@router.delete(
    "/account",
    summary="Delete my account",
    description=(
        "Permanently delete all data for the authenticated user: memories, OAuth clients, "
        "and the user record itself. Requires `confirm: true` in the request body. "
        "The deletion is recorded in an immutable audit log. This action cannot be undone."
    ),
    status_code=204,
    responses={
        400: {"description": "confirm must be true"},
        401: {"description": "Unauthorized"},
        404: {"description": "User not found"},
    },
)
async def delete_account(
    body: AccountDeleteRequest,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> None:
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true to delete your account")

    user_id: str = claims["sub"]

    user = storage.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    counts = storage.delete_user_data(user_id)

    storage.log_audit_event(
        ActivityEvent(
            event_type=EventType.account_deleted,
            client_id="SYSTEM",
            metadata={
                "deleted_user_id": user_id,
                "deleted_memories": counts["deleted_memories"],
                "deleted_clients": counts["deleted_clients"],
            },
        )
    )


@router.get(
    "/account/export",
    summary="Export my data",
    description=(
        "Stream a JSON document containing the authenticated user's profile, "
        "all their memories, OAuth clients, and recent activity log entries "
        "(90-day window, matching the retention policy). Satisfies GDPR "
        "Article 20 and CCPA §1798.100 portability rights. Rate-limited to "
        "one export per 5 minutes per user."
    ),
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "User not found"},
        429: {"description": "Export rate limit exceeded"},
    },
)
async def export_account(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> StreamingResponse:
    user_id: str = claims["sub"]

    user = storage.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Rate limit: one export per EXPORT_RATE_LIMIT_SECONDS. The counter item
    # has a matching TTL and is only set on first write (``if_not_exists``),
    # so DynamoDB cleans it up on its own after the window passes.
    count = storage.increment_rate_limit_counter(
        user_id, "export", ttl_seconds=EXPORT_RATE_LIMIT_SECONDS
    )
    if count > 1:
        raise HTTPException(
            status_code=429,
            detail="Exports are limited to one per 5 minutes.",
            headers={"Retry-After": str(EXPORT_RATE_LIMIT_SECONDS)},
        )

    now = datetime.now(timezone.utc)

    clients, _ = storage.list_clients(owner_user_id=user_id, limit=EXPORT_CLIENTS_LIMIT)
    client_ids = {c.client_id for c in clients}

    today = now.date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(EXPORT_ACTIVITY_LOOKBACK_DAYS)]

    def _stream() -> Iterator[str]:
        yield "{"
        yield f'"exported_at":{json.dumps(now.isoformat())},'
        yield '"user":' + json.dumps(
            {
                "user_id": user.user_id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "created_at": user.created_at.isoformat(),
            }
        )
        yield ',"memories":['
        for i, memory in enumerate(storage.iter_all_memories(owner_user_id=user_id)):
            if i:
                yield ","
            yield json.dumps(
                {
                    "memory_id": memory.memory_id,
                    "key": memory.key,
                    "value": memory.value,
                    "tags": memory.tags,
                    "owner_client_id": memory.owner_client_id,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                    "expires_at": (
                        memory.expires_at.isoformat() if memory.expires_at is not None else None
                    ),
                }
            )
        yield '],"clients":['
        for i, client in enumerate(clients):
            if i:
                yield ","
            yield json.dumps(
                {
                    "client_id": client.client_id,
                    "client_name": client.client_name,
                    "client_type": client.client_type.value,
                    "created_at": client.created_at.isoformat(),
                }
            )
        yield '],"activity_log":['
        events = storage.get_events_for_dates(dates, limit=10000)
        emitted = 0
        for event in events:
            if event.client_id not in client_ids:
                continue
            if emitted:
                yield ","
            emitted += 1
            yield json.dumps(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "client_id": event.client_id,
                    "timestamp": event.timestamp.isoformat(),
                    "metadata": event.metadata,
                }
            )
        yield "]}"

    filename = f"hive-export-{user_id}-{now.strftime('%Y%m%d')}.json"
    return StreamingResponse(
        _stream(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# #535 — /account/stats
#
# Personal usage analytics for the Stats tab. Returns eight pre-aggregated
# graph datasets plus a ``client_names`` lookup map (for
# ClientContribution's legend) in a single response so the UI renders
# without chained round-trips. Results are cached for ``_STATS_CACHE_TTL`` seconds per
# ``(user_id, window_days)`` key — the aggregation walks every memory and
# a windowed slice of the activity log, so the cache shields the table
# from repeated panel refreshes.
# ---------------------------------------------------------------------------


def _compute_account_stats(
    user_id: str, window_days: int, storage: HiveStorage, is_admin: bool = False
) -> dict[str, Any]:
    """Walk storage once and assemble the eight aggregate series.

    Each series is small ( ≤ number of memories or ≤ window_days entries ),
    so the full response stays well under a reasonable Lambda response size.
    Individual graph widgets slice further on the client as they render.
    """
    memories = list(storage.iter_all_memories(owner_user_id=user_id))
    clients, _ = storage.list_clients(owner_user_id=user_id, limit=EXPORT_CLIENTS_LIMIT)

    # Activity events can be logged under a variety of actor ids depending
    # on the code path: management-API memory CRUD writes ``client_id =
    # claims['sub']`` (the user id), MCP tool calls write the OAuth client
    # id, and memories may retain an ``owner_client_id`` for a client that
    # has since been deleted. Broaden the actor set so none of these fall
    # silently off the heatmap / contribution charts.
    activity_actor_ids: set[str] = {c.client_id for c in clients}
    activity_actor_ids.add(user_id)
    for m in memories:
        if m.owner_client_id:
            activity_actor_ids.add(m.owner_client_id)

    # Anchor the window in UTC — the rest of the module uses UTC for day
    # math, and `date.today()` in local time can shift the heatmap /
    # days_since_* buckets by one day around midnight.
    today = datetime.now(timezone.utc).date()
    window_dates = [(today - timedelta(days=i)).isoformat() for i in range(window_days)]
    events = storage.get_events_for_dates(window_dates, limit=_STATS_EVENT_LIMIT)
    own_events = [e for e in events if e.client_id in activity_actor_ids]

    # activity_heatmap — one row per date in the window, count of own events.
    per_date: dict[str, int] = {}
    for e in own_events:
        iso_day = e.timestamp.date().isoformat()
        per_date[iso_day] = per_date.get(iso_day, 0) + 1
    activity_heatmap = [
        {"date": iso_day, "count": per_date.get(iso_day, 0)} for iso_day in window_dates
    ]

    # top_recalled — N most-hit memories by recall_count.
    top_recalled = [
        {"memory_id": m.memory_id, "key": m.key, "recall_count": m.recall_count}
        for m in sorted(memories, key=lambda m: m.recall_count, reverse=True)[
            :_STATS_TOP_RECALLED_N
        ]
        if m.recall_count > 0
    ]

    # tag_distribution — count of memories per tag, descending.
    tag_counts: dict[str, int] = {}
    for m in memories:
        for t in m.tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tag_distribution: list[dict[str, Any]] = [
        {"tag": t, "count": c}
        for t, c in sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # memory_growth — cumulative count at end of each day in the window.
    # Baseline = memories created before the window start; then advance one
    # day at a time adding anything whose created_at falls on-or-before it.
    sorted_mems = sorted(memories, key=lambda m: m.created_at)
    window_start = today - timedelta(days=window_days - 1)
    idx = 0
    cumulative = 0
    while idx < len(sorted_mems) and sorted_mems[idx].created_at.date() < window_start:
        cumulative += 1
        idx += 1
    memory_growth: list[dict[str, Any]] = []
    for i in range(window_days):
        day = window_start + timedelta(days=i)
        while idx < len(sorted_mems) and sorted_mems[idx].created_at.date() <= day:
            cumulative += 1
            idx += 1
        memory_growth.append({"date": day.isoformat(), "cumulative": cumulative})

    # Admins and explicitly-exempted users both get an unbounded limit —
    # matches the exemption logic in /api/stats (#535 follow-up).
    is_exempt = is_admin or user_id in _exempt_users()
    # Per-user limit overrides (None = no override, use system default).
    acct_user = storage.get_user_by_id(user_id) if not is_exempt else None
    effective_memory_limit = (
        acct_user.memory_limit
        if acct_user and acct_user.memory_limit is not None
        else get_memory_limit()
    )
    effective_storage_limit = (
        acct_user.storage_bytes_limit
        if acct_user and acct_user.storage_bytes_limit is not None
        else get_storage_bytes_limit()
    )
    quota = {
        "memory_count": len(memories),
        "memory_limit": None if is_exempt else effective_memory_limit,
        "storage_bytes": sum(m.size_bytes or 0 for m in memories),
        "storage_bytes_limit": None if is_exempt else effective_storage_limit,
    }

    # freshness — days since creation + days since last access per memory.
    # Falls back to days_since_created when the memory has never been
    # recalled (last_accessed_at is None).
    freshness = []
    for m in memories:
        age = (today - m.created_at.date()).days
        accessed_age = (
            (today - m.last_accessed_at.date()).days if m.last_accessed_at is not None else age
        )
        freshness.append(
            {
                "memory_id": m.memory_id,
                "key": m.key,
                "tags": m.tags,
                "days_since_created": age,
                "days_since_accessed": accessed_age,
            }
        )

    # client_contribution — events-per-day-per-client-id for stacked chart.
    contrib: dict[tuple[str, str], int] = {}
    for e in own_events:
        key = (e.timestamp.date().isoformat(), e.client_id)
        contrib[key] = contrib.get(key, 0) + 1
    client_contribution = [
        {"date": d, "client_id": cid, "count": n} for (d, cid), n in sorted(contrib.items())
    ]
    # client_names — display-name lookup so the ClientContribution chart
    # can label each stacked segment without a second round-trip. Falls
    # back to the client_id prefix on the UI side for ids we can't
    # resolve (e.g. deleted clients, or the user_id actor itself).
    client_names: dict[str, str] = {c.client_id: c.client_name for c in clients}

    # tag_cooccurrence — undirected edges between tags that share a memory,
    # weighted by how many memories they co-appear in. Sorted by weight
    # descending so the UI can pick a sensible top-K for a force-graph.
    cooccur: dict[tuple[str, str], int] = {}
    for m in memories:
        tags = sorted(set(m.tags))
        for i, src in enumerate(tags):
            for tgt in tags[i + 1 :]:
                cooccur[(src, tgt)] = cooccur.get((src, tgt), 0) + 1
    tag_cooccurrence: list[dict[str, Any]] = [
        {"source": s, "target": t, "weight": w}
        for (s, t), w in sorted(cooccur.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return {
        "window_days": window_days,
        "activity_heatmap": activity_heatmap,
        "top_recalled": top_recalled,
        "tag_distribution": tag_distribution,
        "memory_growth": memory_growth,
        "quota": quota,
        "freshness": freshness,
        "client_contribution": client_contribution,
        "client_names": client_names,
        "tag_cooccurrence": tag_cooccurrence,
    }


@router.get(
    "/account/stats",
    summary="Personal usage analytics",
    description=(
        "Return eight pre-aggregated graph datasets for the authenticated user "
        "(activity heatmap, top-recalled memories, tag distribution, memory "
        "growth, quota, freshness, client contribution, tag co-occurrence) "
        "plus a ``client_names`` lookup map so chart labels can resolve "
        "client IDs without a second round-trip. "
        "Results are cached server-side for 60s per (user, window) pair."
    ),
    responses={401: {"description": "Unauthorized"}, 422: {"description": "Invalid window"}},
)
async def get_account_stats(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    window: Annotated[
        str,
        Query(
            pattern="^(30|90|365)$",
            description="Time window for date-scoped series: 30 | 90 | 365 (days).",
        ),
    ] = "90",
) -> dict[str, Any]:
    user_id: str = claims["sub"]
    is_admin = claims.get("role") == "admin"
    window_days = int(window)

    cache_key = f"{user_id}:{window_days}"
    cached = _STATS_CACHE.get(cache_key)
    if cached is not None:
        if time.time() - cached[0] < _STATS_CACHE_TTL:
            return cached[1]
        # Drop the expired entry so the cache doesn't grow unbounded as
        # new (user, window) keys are seen over the Lambda's lifetime.
        _STATS_CACHE.pop(cache_key, None)

    data = _compute_account_stats(user_id, window_days, storage, is_admin=is_admin)
    _STATS_CACHE[cache_key] = (time.time(), data)
    return data
