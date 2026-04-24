# Copyright (c) 2026 John Carter. All rights reserved.
"""Pydantic models for Hive API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Memory(BaseModel):
    memory_id: str
    key: str
    value: str
    tags: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None


class MemoryList(BaseModel):
    items: list[Memory]
    next_cursor: str | None = None
