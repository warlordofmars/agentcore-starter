# Copyright (c) 2026 John Carter. All rights reserved.
"""
Per-client rate limiting for Hive.

Rate limit counters are stored in DynamoDB using atomic increments so they
are safe under concurrent Lambda invocations. Counters expire automatically
via DynamoDB TTL.

Configuration (environment variables):
  HIVE_RATE_LIMIT_RPM              Requests per minute per client (default 60)
  HIVE_RATE_LIMIT_RPD              Requests per day per client (default 1000)
  HIVE_RATE_LIMIT_EXEMPT_CLIENTS   Comma-separated client IDs exempt from limits

Override mechanism: set HIVE_RATE_LIMIT_EXEMPT_CLIENTS to a comma-separated
list of client IDs that should bypass rate limiting (e.g. internal test clients
or trusted integrations).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from hive.storage import HiveStorage

# ---------------------------------------------------------------------------
# Defaults (overridable via environment variables)
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_RPM = 60
DEFAULT_RATE_LIMIT_RPD = 1000


def _rpm() -> int:
    return int(os.environ.get("HIVE_RATE_LIMIT_RPM", str(DEFAULT_RATE_LIMIT_RPM)))


def _rpd() -> int:
    return int(os.environ.get("HIVE_RATE_LIMIT_RPD", str(DEFAULT_RATE_LIMIT_RPD)))


def _exempt_clients() -> set[str]:
    raw = os.environ.get("HIVE_RATE_LIMIT_EXEMPT_CLIENTS", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class RateLimitExceeded(Exception):
    """Raised when a client exceeds its rate limit."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_rate_limit(client_id: str, storage: HiveStorage) -> None:
    """Check and enforce per-client rate limits.

    Atomically increments DynamoDB counters for the current minute and day
    windows. Raises RateLimitExceeded (with retry_after seconds) if either
    limit is exceeded.

    Does nothing for clients listed in HIVE_RATE_LIMIT_EXEMPT_CLIENTS.
    """
    if client_id in _exempt_clients():
        return

    now = datetime.now(timezone.utc)
    rpm = _rpm()
    rpd = _rpd()

    # Per-minute window — counter expires 2 minutes after the window key
    min_key = now.strftime("%Y-%m-%dT%H:%M")
    min_count = storage.increment_rate_limit_counter(client_id, f"min#{min_key}", ttl_seconds=120)
    if min_count > rpm:
        retry_after = 60 - now.second
        raise RateLimitExceeded(retry_after=retry_after)

    # Per-day window — counter expires 2 days after the window key
    day_key = now.strftime("%Y-%m-%d")
    day_count = storage.increment_rate_limit_counter(
        client_id, f"day#{day_key}", ttl_seconds=86400 * 2
    )
    if day_count > rpd:
        retry_after = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
        raise RateLimitExceeded(retry_after=retry_after)
