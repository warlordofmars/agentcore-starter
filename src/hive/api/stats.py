# Copyright (c) 2026 John Carter. All rights reserved.
"""
Usage stats and activity log endpoints for the Hive management API.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from hive.api._auth import require_mgmt_user
from hive.models import PagedResponse, StatsResponse
from hive.quota import _exempt_users, get_client_limit, get_memory_limit, get_storage_bytes_limit
from hive.storage import HiveStorage

router = APIRouter(tags=["stats"])

_ACTIVITY_LIMIT_DEFAULT = 100
_ACTIVITY_LIMIT_MAX = 500


def _storage() -> HiveStorage:
    return HiveStorage()


@router.get(
    "/stats",
    summary="Get usage statistics",
    description="Return summary counts for memories, clients, and activity events. Admins see platform-wide totals; non-admins see only their own data.",
    responses={401: {"description": "Unauthorized"}},
)
async def get_stats(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> StatsResponse:
    owner_user_id = None if claims.get("role") == "admin" else claims["sub"]
    today = date.today()
    last_7 = [(today - timedelta(days=i)).isoformat() for i in range(7)]

    events_today = storage.get_events_for_date(today.isoformat())
    events_7 = storage.get_events_for_dates(last_7, limit=10000)

    is_admin = claims.get("role") == "admin"
    is_exempt = claims["sub"] in _exempt_users()
    unlimited = is_admin or is_exempt

    # Resolve per-user limit overrides for non-exempt users.
    user = storage.get_user_by_id(claims["sub"]) if not unlimited else None
    effective_memory_limit = (
        user.memory_limit if (user and user.memory_limit is not None) else get_memory_limit()
    )
    effective_storage_bytes_limit = (
        user.storage_bytes_limit
        if (user and user.storage_bytes_limit is not None)
        else get_storage_bytes_limit()
    )

    return StatsResponse(
        total_memories=storage.count_memories(owner_user_id=owner_user_id),
        total_clients=storage.count_clients(owner_user_id=owner_user_id),
        total_users=storage.count_users() if is_admin else None,
        events_today=len(events_today),
        events_last_7_days=len(events_7),
        memory_limit=None if unlimited else effective_memory_limit,
        client_limit=None if unlimited else get_client_limit(),
        total_storage_bytes=storage.sum_storage_bytes(owner_user_id=owner_user_id),
        storage_bytes_limit=None if unlimited else effective_storage_bytes_limit,
    )


@router.get(
    "/activity",
    summary="Get activity log",
    description="Return recent activity events (memory creates, updates, deletes, client registrations, etc.) for the configured number of days.",
    responses={401: {"description": "Unauthorized"}},
)
async def get_activity(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    days: Annotated[int, Query(ge=1, le=90, description="Number of days of history to return")] = 7,
    limit: Annotated[
        int, Query(ge=1, le=_ACTIVITY_LIMIT_MAX, description="Max events to return")
    ] = _ACTIVITY_LIMIT_DEFAULT,
) -> PagedResponse:
    today = date.today()
    dates = [
        (today - timedelta(days=i)).isoformat()
        for i in range(days)  # NOSONAR — days bounded by FastAPI Query(ge=1, le=90)
    ]
    events = storage.get_events_for_dates(dates, limit=limit + 1)

    has_more = len(events) > limit
    events = events[:limit]

    return PagedResponse(
        items=[
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "client_id": e.client_id,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata,
            }
            for e in events
        ],
        count=len(events),
        has_more=has_more,
        next_cursor=None,
    )
