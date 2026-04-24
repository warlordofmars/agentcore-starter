# Copyright (c) 2026 John Carter. All rights reserved.
"""Shared FastAPI auth dependencies for management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hive.auth.tokens import decode_mgmt_jwt, validate_bearer_token
from hive.metrics import emit_metric
from hive.rate_limiter import RateLimitExceeded, check_rate_limit
from hive.storage import HiveStorage

_bearer = HTTPBearer()


def _get_storage() -> HiveStorage:
    return HiveStorage()


async def require_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    storage: HiveStorage = Depends(_get_storage),
) -> tuple[HiveStorage, str]:
    """
    FastAPI dependency that validates the Bearer token and returns
    (storage, client_id).  Raises HTTP 401 on failure, 429 on rate limit.
    """
    try:
        token = validate_bearer_token(f"Bearer {credentials.credentials}", storage)
    except ValueError as exc:
        await emit_metric("TokenValidationFailures")
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    try:
        check_rate_limit(token.client_id, storage)
    except RateLimitExceeded as exc:
        # #367 — surface rate-limit pressure in the admin dashboard. Emit
        # twice: aggregate (Environment only) + drill-down (endpoint + reason).
        await emit_metric("RateLimitedRequests")
        await emit_metric("RateLimitedRequests", endpoint="/api", reason="rate_limit")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    return storage, token.client_id


def require_scope(required_scope: str):
    """Return a FastAPI dependency that validates the Bearer token and checks for a scope."""

    async def _dep(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        storage: HiveStorage = Depends(_get_storage),
    ) -> tuple[HiveStorage, str]:
        try:
            token = validate_bearer_token(f"Bearer {credentials.credentials}", storage)
        except ValueError as exc:
            await emit_metric("TokenValidationFailures")
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if required_scope not in set(token.scope.split()):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope: '{required_scope}' required",
            )
        return storage, token.client_id

    return _dep


# Module-level instances so tests can override them via app.dependency_overrides
require_memories_read = require_scope("memories:read")
require_memories_write = require_scope("memories:write")
require_clients_read = require_scope("clients:read")
require_clients_write = require_scope("clients:write")


# ---------------------------------------------------------------------------
# Management JWT dependencies (human users of the management UI)
# ---------------------------------------------------------------------------


def require_mgmt_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    """Validate a management JWT and return its claims.

    Does not hit DynamoDB — the JWT is self-contained.
    Raises HTTP 401 on invalid/expired token.
    """
    from jose import JWTError

    try:
        return decode_mgmt_jwt(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_admin(
    claims: dict[str, Any] = Depends(require_mgmt_user),
) -> dict[str, Any]:
    """Require admin role on top of a valid management JWT."""
    if claims.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims
