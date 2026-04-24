# Copyright (c) 2026 John Carter. All rights reserved.
"""
Memory version history endpoints for the Hive management API.

All routes require a valid management JWT via require_mgmt_user.
Non-admin users can only access versions of their own memories.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from hive.api._auth import require_mgmt_user
from hive.models import (
    ActivityEvent,
    EventType,
    MemoryVersionResponse,
)
from hive.storage import HiveStorage

router = APIRouter(tags=["versions"])

_MEMORY_NOT_FOUND = "Memory not found"
_VERSION_NOT_FOUND = "Version not found"


def _storage() -> HiveStorage:
    return HiveStorage()


def _user_filter(claims: dict[str, Any]) -> str | None:
    return None if claims.get("role") == "admin" else claims["sub"]


@router.get(
    "/memories/{memory_id}/versions",
    summary="List version history for a memory",
    description="Return all previous versions of a memory, newest first. Non-admins can only access their own memories.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
    },
)
async def list_versions(
    memory_id: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> list[MemoryVersionResponse]:
    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    versions = storage.list_memory_versions(memory_id)
    return [MemoryVersionResponse.from_version(v) for v in versions]


@router.post(
    "/memories/{memory_id}/restore",
    summary="Restore a memory to a previous version",
    description="Overwrite the current memory value with a previous version snapshot. Non-admins can only restore their own memories.",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": _MEMORY_NOT_FOUND},
    },
)
async def restore_version(
    memory_id: str,
    version_timestamp: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> MemoryVersionResponse:
    memory = storage.get_memory_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)
    owner_user_id = _user_filter(claims)
    if owner_user_id and memory.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail=_MEMORY_NOT_FOUND)

    version = storage.get_memory_version(memory_id, version_timestamp)
    if version is None:
        raise HTTPException(status_code=404, detail=_VERSION_NOT_FOUND)

    memory.value = version.value
    memory.tags = version.tags
    memory.updated_at = datetime.now(timezone.utc)
    storage.put_memory(memory)
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_updated,
            client_id=claims["sub"],
            metadata={"memory_id": memory_id, "version_timestamp": version_timestamp},
        )
    )
    return MemoryVersionResponse.from_version(version)
