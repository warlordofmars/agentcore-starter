# Copyright (c) 2026 John Carter. All rights reserved.
"""
Memory CRUD endpoints for the Hive management API.

All routes require a valid management JWT via require_mgmt_user.
Non-admin users can only access their own memories (owner_user_id filtering).
Admins can access all memories.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from hive.api._auth import require_mgmt_user
from hive.metrics import emit_metric
from hive.models import (
    ActivityEvent,
    EventType,
    Memory,
    MemoryCreate,
    MemoryResponse,
    MemorySearchResult,
    MemoryUpdate,
    PagedResponse,
)
from hive.quota import QuotaExceeded, check_memory_quota, check_storage_quota
from hive.storage import HiveStorage
from hive.vector_store import VectorIndexNotFoundError, VectorStore

router = APIRouter(tags=["memories"])

_MEMORY_NOT_FOUND = "Memory not found"
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 200


def _storage() -> HiveStorage:
    return HiveStorage()


def _vector_store() -> VectorStore:
    return VectorStore()


def _user_filter(claims: dict[str, Any]) -> str | None:
    """Return owner_user_id filter for non-admins; None for admins (see all)."""
    return None if claims.get("role") == "admin" else claims["sub"]


@router.get(
    "/memories",
    summary="List or search memories",
    description="Return a paginated list of memories. Supports optional tag filtering and semantic search. Non-admins see only their own memories.",
    responses={401: {"description": "Unauthorized"}},
)
async def list_memories(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    vs: Annotated[VectorStore, Depends(_vector_store)],
    tag: Annotated[str | None, Query(description="Filter by tag")] = None,
    search: Annotated[str | None, Query(description="Semantic search query")] = None,
    limit: Annotated[
        int, Query(ge=1, le=_LIMIT_MAX, description="Max items to return")
    ] = _LIMIT_DEFAULT,
    cursor: Annotated[
        str | None, Query(description="Pagination cursor from previous response")
    ] = None,
) -> PagedResponse:
    owner_user_id = _user_filter(claims)

    if search:
        # Semantic search — top-K, no pagination
        client_id: str = claims["sub"]
        try:
            pairs = vs.search(search, client_id, top_k=min(limit, 50))
        except VectorIndexNotFoundError:
            return PagedResponse(items=[], count=0, has_more=False, next_cursor=None)
        results = storage.hydrate_memory_ids(pairs)
        if owner_user_id:
            results = [(m, s) for m, s in results if m.owner_user_id == owner_user_id]
        return PagedResponse(
            items=[
                MemorySearchResult.from_memory_and_score(m, score).model_dump()
                for m, score in results
            ],
            count=len(results),
            has_more=False,
            next_cursor=None,
        )

    if tag:
        items, next_cursor = storage.list_memories_by_tag(tag, limit=limit, cursor=cursor)
        if owner_user_id:
            items = [m for m in items if m.owner_user_id == owner_user_id]
    else:
        items, next_cursor = storage.list_all_memories(
            owner_user_id=owner_user_id, limit=limit, cursor=cursor
        )
    return PagedResponse(
        items=[MemoryResponse.from_memory(m).model_dump() for m in items],
        count=len(items),
        has_more=next_cursor is not None,
        next_cursor=next_cursor,
    )


@router.post(
    "/memories",
    summary="Create or update a memory",
    description="Create a new memory or update an existing one with the same key. Returns 201 on create, 200 on update. Non-admins cannot overwrite another user's memory.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Memory not found (non-admin cannot overwrite another user's memory)"},
        413: {"description": "Memory value too large"},
    },
)
async def create_memory(
    body: MemoryCreate,
    response: Response,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> MemoryResponse:
    owner_user_id: str = claims["sub"]

    existing = storage.get_memory_by_key(body.key)
    if existing:
        # Non-admins cannot overwrite another user's memory
        if (
            existing.owner_user_id is not None
            and existing.owner_user_id != owner_user_id
            and claims.get("role") != "admin"
        ):
            raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)

        old_size = existing.size_bytes or 0
        existing.value = body.value
        existing.tags = body.tags
        existing.updated_at = datetime.now(timezone.utc)
        if body.ttl_seconds is not None:
            existing.expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.ttl_seconds)
        delta = len(body.value.encode("utf-8")) - old_size
        if delta > 0:
            try:
                check_storage_quota(owner_user_id, delta, storage)
            except QuotaExceeded as exc:
                await emit_metric("RateLimitedRequests")
                await emit_metric("RateLimitedRequests", endpoint="/api/memories", reason="quota")
                raise HTTPException(status_code=429, detail=exc.detail) from exc
        try:
            storage.put_memory(existing)
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        storage.log_event(
            ActivityEvent(
                event_type=EventType.memory_updated,
                client_id=owner_user_id,
                metadata={"key": body.key, "tags": body.tags},
            )
        )
        response.status_code = 200
        return MemoryResponse.from_memory(existing)

    try:
        check_memory_quota(owner_user_id, storage)
        check_storage_quota(owner_user_id, len(body.value.encode("utf-8")), storage)
    except QuotaExceeded as exc:
        # #367 — track 429s so admins can see quota pressure in the dashboard.
        # Emit twice: aggregate (Environment only) for the dashboard count, and
        # a fully-dimensioned record for drill-down (endpoint + reason).
        await emit_metric("RateLimitedRequests")
        await emit_metric("RateLimitedRequests", endpoint="/api/memories", reason="quota")
        raise HTTPException(status_code=429, detail=exc.detail) from exc
    expires_at = None
    if body.ttl_seconds is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.ttl_seconds)
    memory = Memory(
        key=body.key,
        value=body.value,
        tags=body.tags,
        owner_client_id=owner_user_id,
        owner_user_id=owner_user_id,
        expires_at=expires_at,
    )
    try:
        storage.put_memory(memory)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_created,
            client_id=owner_user_id,
            metadata={"key": body.key, "tags": body.tags},
        )
    )
    response.status_code = 201
    return MemoryResponse.from_memory(memory)


@router.get(
    "/memories/export",
    summary="Export memories as JSON Lines",
    description="Stream all memories (or those with a given tag) as newline-delimited JSON. Sets Content-Disposition for browser download.",
    responses={401: {"description": "Unauthorized"}},
)
async def export_memories(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    tag: Annotated[str | None, Query(description="Filter by tag")] = None,
) -> StreamingResponse:
    owner_user_id = _user_filter(claims)

    def _stream():
        for memory in storage.iter_all_memories(owner_user_id=owner_user_id, tag=tag):
            yield json.dumps(MemoryResponse.from_memory(memory).model_dump(), default=str) + "\n"

    filename = f"memories-{tag}.jsonl" if tag else "memories.jsonl"
    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/memories/import",
    summary="Bulk import memories from JSON Lines",
    description="Import memories from a newline-delimited JSON body. Each line must be a JSON object with key, value, and tags fields. Upserts by key.",
    responses={401: {"description": "Unauthorized"}},
)
async def import_memories(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    body: Annotated[str, Body(media_type="application/x-ndjson")],
) -> dict[str, Any]:
    owner_user_id: str = claims["sub"]
    created = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for i, line in enumerate(body.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            key = data["key"]
            value = data["value"]
            tags = data.get("tags", [])
        except (json.JSONDecodeError, KeyError) as exc:
            errors.append({"line": i + 1, "error": str(exc)})
            continue

        existing = storage.get_memory_by_key(key)
        if existing:
            existing.value = value
            existing.tags = tags
            existing.updated_at = datetime.now(timezone.utc)
            try:
                storage.put_memory(existing)
            except ValueError as exc:
                errors.append({"line": i + 1, "key": key, "error": str(exc)})
                continue
            updated += 1
        else:
            memory = Memory(
                key=key,
                value=value,
                tags=tags,
                owner_client_id=owner_user_id,
                owner_user_id=owner_user_id,
            )
            try:
                storage.put_memory(memory)
            except ValueError as exc:
                errors.append({"line": i + 1, "key": key, "error": str(exc)})
                continue
            created += 1

    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_created,
            client_id=owner_user_id,
            metadata={"created": created, "updated": updated},
        )
    )
    return {"created": created, "updated": updated, "errors": errors}


@router.get(
    "/memories/{memory_id}/content",
    summary="Download memory content from S3",
    description="Stream raw binary or large-text content from S3 for image, blob, and text-large memories. Non-admins can only access their own memories.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
        409: {"description": "Memory has no S3 content"},
    },
)
async def get_memory_content(
    memory_id: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> StreamingResponse:
    from hive.blob_store import BlobStore

    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    if memory.s3_uri is None:
        raise HTTPException(status_code=409, detail="Memory has no S3 content")

    owner = memory.owner_user_id or memory.owner_client_id
    blob_store = BlobStore()
    body = blob_store.get(owner, memory_id)
    content_type = memory.content_type or "application/octet-stream"
    return StreamingResponse(
        iter([body]),
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{memory.key}"'},
    )


@router.get(
    "/memories/{memory_id}",
    summary="Get a memory by ID",
    description="Retrieve a single memory by its unique ID. Non-admins can only access their own memories.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
    },
)
async def get_memory(
    memory_id: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> MemoryResponse:
    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    return MemoryResponse.from_memory(memory)


@router.patch(
    "/memories/{memory_id}",
    summary="Update a memory",
    description="Partially update a memory's value and/or tags by ID. Non-admins can only update their own memories.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
        413: {"description": "Memory value too large"},
    },
)
async def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> MemoryResponse:
    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)

    old_size = memory.size_bytes or 0
    if body.value is not None:
        memory.value = body.value
    if body.tags is not None:
        memory.tags = body.tags
    if body.ttl_seconds is not None:
        memory.expires_at = (
            None
            if body.ttl_seconds == 0
            else datetime.now(timezone.utc) + timedelta(seconds=body.ttl_seconds)
        )
    memory.updated_at = datetime.now(timezone.utc)

    if body.value is not None:
        delta = len(body.value.encode("utf-8")) - old_size
        if delta > 0 and memory.owner_user_id is not None:
            try:
                check_storage_quota(memory.owner_user_id, delta, storage)
            except QuotaExceeded as exc:
                await emit_metric("RateLimitedRequests")
                await emit_metric(
                    "RateLimitedRequests",
                    endpoint="/api/memories/{memory_id}",
                    reason="quota",
                )
                raise HTTPException(status_code=429, detail=exc.detail) from exc

    try:
        storage.put_memory(memory)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_updated,
            client_id=claims["sub"],
            metadata={"memory_id": memory_id},
        )
    )
    return MemoryResponse.from_memory(memory)


@router.delete(
    "/memories/{memory_id}",
    summary="Delete a memory",
    description="Permanently delete a memory by ID. Non-admins can only delete their own memories.",
    status_code=204,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
    },
)
async def delete_memory(
    memory_id: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> None:
    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)

    storage.delete_memory(memory_id)
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_deleted,
            client_id=claims["sub"],
            metadata={"memory_id": memory_id},
        )
    )


@router.delete(
    "/memories",
    summary="Bulk delete memories by tag",
    description="Delete all memories with the given tag. Non-admins can only delete their own memories.",
    responses={
        400: {"description": "tag query parameter is required"},
        401: {"description": "Unauthorized"},
    },
)
async def delete_memories_by_tag(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
    tag: Annotated[str | None, Query(description="Tag to bulk-delete")] = None,
) -> dict[str, int]:
    if not tag:
        raise HTTPException(status_code=400, detail="tag query parameter is required")
    owner_user_id = _user_filter(claims)
    deleted = storage.delete_memories_by_tag(tag, owner_user_id=owner_user_id)
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_deleted,
            client_id=claims["sub"],
            metadata={"tag": tag, "count": deleted},
        )
    )
    return {"deleted": deleted}
