# Copyright (c) 2026 John Carter. All rights reserved.
"""
Per-user usage quotas for Hive free tier.

Quota limits are configurable via environment variables and checked before
write operations (creating a new memory, registering a new OAuth client).
Per-user overrides stored on the User model take precedence over system defaults.

Configuration (environment variables):
  HIVE_QUOTA_MAX_MEMORIES       Max stored memories per user (default 500)
  HIVE_QUOTA_MAX_CLIENTS        Max OAuth clients per user (default 10)
  HIVE_QUOTA_MAX_STORAGE_BYTES  Max total stored bytes per user (default 100 MB)
  HIVE_QUOTA_EXEMPT_USERS       Comma-separated user IDs exempt from quotas
"""

from __future__ import annotations

import os

from hive.storage import HiveStorage

DEFAULT_QUOTA_MAX_MEMORIES = 500
DEFAULT_QUOTA_MAX_CLIENTS = 10
DEFAULT_QUOTA_MAX_STORAGE_BYTES = 100 * 1024 * 1024  # 100 MB


def _max_memories() -> int:
    return int(os.environ.get("HIVE_QUOTA_MAX_MEMORIES", str(DEFAULT_QUOTA_MAX_MEMORIES)))


def _max_clients() -> int:
    return int(os.environ.get("HIVE_QUOTA_MAX_CLIENTS", str(DEFAULT_QUOTA_MAX_CLIENTS)))


def _max_storage_bytes() -> int:
    return int(os.environ.get("HIVE_QUOTA_MAX_STORAGE_BYTES", str(DEFAULT_QUOTA_MAX_STORAGE_BYTES)))


def _exempt_users() -> set[str]:
    raw = os.environ.get("HIVE_QUOTA_EXEMPT_USERS", "")
    return {u.strip() for u in raw.split(",") if u.strip()}


def get_memory_limit() -> int:
    """Return the configured memory quota limit."""
    return _max_memories()


def get_client_limit() -> int:
    """Return the configured client quota limit."""
    return _max_clients()


def get_storage_bytes_limit() -> int:
    """Return the configured storage bytes quota limit."""
    return _max_storage_bytes()


class QuotaExceeded(Exception):
    """Raised when a user exceeds a quota limit."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def check_memory_quota(user_id: str | None, storage: HiveStorage) -> None:
    """Raise QuotaExceeded if the user has reached their memory limit.

    Passes silently for None user_id (pre-migration items without an owner)
    and for users listed in HIVE_QUOTA_EXEMPT_USERS.
    Per-user memory_limit overrides stored on the User model take precedence
    over the system default.
    """
    if user_id is None or user_id in _exempt_users():
        return
    user = storage.get_user_by_id(user_id)
    limit = user.memory_limit if user and user.memory_limit is not None else _max_memories()
    count = storage.count_memories(owner_user_id=user_id)
    if count >= limit:
        raise QuotaExceeded(
            f"Memory quota reached ({count}/{limit}). Delete some memories to store new ones."
        )


def check_storage_quota(user_id: str | None, new_value_bytes: int, storage: HiveStorage) -> None:
    """Raise QuotaExceeded if storing new_value_bytes would exceed the user's storage limit.

    Passes silently for None user_id and HIVE_QUOTA_EXEMPT_USERS.
    Per-user storage_bytes_limit overrides take precedence over the system default.
    """
    if user_id is None or user_id in _exempt_users():
        return
    user = storage.get_user_by_id(user_id)
    limit = (
        user.storage_bytes_limit
        if user and user.storage_bytes_limit is not None
        else _max_storage_bytes()
    )
    current = storage.sum_storage_bytes(owner_user_id=user_id)
    projected = current + new_value_bytes
    if projected > limit:
        raise QuotaExceeded(
            f"Storage quota reached ({projected}/{limit} bytes). "
            "Delete some memories to free space."
        )


def check_client_quota(user_id: str, storage: HiveStorage) -> None:
    """Raise QuotaExceeded if the user has reached their client limit."""
    if user_id in _exempt_users():
        return
    limit = _max_clients()
    count = storage.count_clients(owner_user_id=user_id)
    if count >= limit:
        raise QuotaExceeded(
            f"Client quota reached ({count}/{limit}). "
            "Delete an existing client to register a new one."
        )
