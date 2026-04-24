# Copyright (c) 2026 John Carter. All rights reserved.
"""
Hive MCP Server — FastMCP tool definitions.

All tools validate the OAuth 2.1 Bearer token passed in the MCP request
context before performing any storage operation.

Tools:
  ping()                      — health check (auth-only, no storage access)
  remember(key, value, tags)  — store a memory
  recall(key)                 — retrieve a memory by key
  forget(key)                 — delete a memory by key
  list_memories(tag)          — list memories by tag
  list_tags()                 — list distinct tags for the caller's memories
  summarize_context(topic)    — synthesise memories into a summary
  pack_context(topic, ...)    — token-budget-aware context pack (#452)
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from urllib.parse import quote, unquote

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken as FastMCPAccessToken
from fastmcp.server.auth import RemoteAuthProvider, TokenVerifier
from fastmcp.server.dependencies import get_access_token, get_http_request
from fastmcp.tools.tool import ToolResult
from mcp.types import ImageContent
from pydantic import AnyHttpUrl
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse as StarletteJSONResponse

from hive.auth.tokens import ISSUER, _origin_verify_secret, validate_bearer_token
from hive.hybrid_search import (
    DEFAULT_W_KEYWORD,
    DEFAULT_W_RECENCY,
    DEFAULT_W_SEMANTIC,
    blend_score,
    keyword_score,
    recency_score,
    tokenize,
)
from hive.logging_config import configure_logging, get_logger, new_request_id, set_request_context
from hive.metrics import emit_metric
from hive.models import ActivityEvent, EventType, Memory, MemorySearchResult
from hive.quota import QuotaExceeded, check_memory_quota, check_storage_quota, get_memory_limit
from hive.rate_limiter import (
    DEFAULT_RATE_LIMIT_RPD,
    DEFAULT_RATE_LIMIT_RPM,
    RateLimitExceeded,
    check_rate_limit,
)
from hive.storage import HiveStorage, VersionConflict
from hive.vector_store import VectorIndexNotFoundError, VectorStore

configure_logging("mcp")
logger = get_logger("hive.server")

_MEMORIES_READ_SCOPE = "memories:read"

DEFAULT_MAX_VALUE_BYTES = 10 * 1024 * 1024


def _max_value_bytes() -> int:
    """Max UTF-8 byte size of a memory value. Configurable via HIVE_MAX_VALUE_BYTES."""
    return int(os.environ.get("HIVE_MAX_VALUE_BYTES", str(DEFAULT_MAX_VALUE_BYTES)))


class HiveTokenVerifier(TokenVerifier):
    """Wraps Hive token validation for FastMCP's built-in auth middleware.

    Enables FastMCP to return HTTP 401 + WWW-Authenticate headers on
    unauthenticated requests, triggering the OAuth flow in clients like
    Claude Desktop.  The full validation (rate limit, scope) is still
    enforced per-tool by _auth().
    """

    async def verify_token(self, token: str) -> FastMCPAccessToken | None:
        try:
            validated = validate_bearer_token(f"Bearer {token}", HiveStorage())
            return FastMCPAccessToken(
                token=token,
                client_id=validated.client_id,
                scopes=validated.scope.split(),
                expires_at=int(validated.expires_at.timestamp()),
            )
        except ValueError:
            return None


class _OriginVerifyMiddleware(BaseHTTPMiddleware):
    """Reject requests missing the CloudFront X-Origin-Verify secret.

    Disabled when HIVE_ORIGIN_VERIFY_PARAM is not set (local dev / non-prod).
    """

    async def dispatch(self, request: StarletteRequest, call_next):  # type: ignore[override]
        expected = _origin_verify_secret()
        if (
            expected
            and expected != "CHANGE_ME_ON_FIRST_DEPLOY"
            and request.headers.get("x-origin-verify") != expected
        ):
            return StarletteJSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)


def _app_version() -> str:
    if v := os.environ.get("APP_VERSION"):
        return v
    try:
        return importlib.metadata.version("hive")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


mcp = FastMCP(
    name="Hive",
    instructions=(
        f"Hive {_app_version()} — shared persistent memory server for Claude agents and teams. "
        "Use the memory tools to store, retrieve, and organise information across "
        "conversations and agent runs."
    ),
    auth=RemoteAuthProvider(
        token_verifier=HiveTokenVerifier(),
        authorization_servers=[AnyHttpUrl(ISSUER)],
        base_url=ISSUER,
        scopes_supported=["memories:read", "memories:write"],
        resource_name="Hive",
    ),
)

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def _auth(ctx: Context | None, required_scope: str | None = None) -> tuple[HiveStorage, str]:
    """Validate Bearer token; return (storage, client_id).

    Reads the Authorization header from the HTTP request when running under
    FastMCP's HTTP transport, falling back to ctx.request_context.meta for
    direct invocation (integration tests).  Also sets per-request logging
    context (request_id, client_id).

    If required_scope is given, raises ToolError if the token lacks that scope.
    Emits the ``TokenValidationFailures`` metric on auth rejection so the
    CloudWatch AuthFailures alarm has something to fire on.
    """
    storage = HiveStorage()
    auth_header: str | None = None
    request_id = new_request_id()

    # HTTP transport (Lambda / local HTTP server)
    try:
        request = get_http_request()
        auth_header = request.headers.get("authorization")
        # Prefer the Lambda / ALB request ID for correlation with CloudWatch.
        request_id = (
            request.headers.get("x-amzn-requestid")
            or request.headers.get("x-request-id")
            or request_id
        )
    except RuntimeError:
        pass

    # Fallback: direct invocation or integration tests pass token via meta.
    # Tests inject a plain dict; FastMCP passes a Pydantic Meta model whose
    # extra fields live in model_extra rather than being dict-accessible.
    if not auth_header and ctx and ctx.request_context and ctx.request_context.meta:
        meta = ctx.request_context.meta
        if isinstance(meta, dict):
            meta_dict: dict[str, Any] = meta
        else:
            meta_dict = getattr(meta, "model_extra", None) or {}
        auth_header = meta_dict.get("Authorization") or meta_dict.get("authorization")

    try:
        token = validate_bearer_token(auth_header, storage)
    except ValueError as exc:
        await emit_metric("TokenValidationFailures")
        raise ToolError(f"Unauthorized: {exc}") from exc

    if required_scope and required_scope not in set(token.scope.split()):
        raise ToolError(f"Insufficient scope: '{required_scope}' required")

    try:
        check_rate_limit(token.client_id, storage)
    except RateLimitExceeded as exc:
        # #367 — track 429-equivalent events so admins can see pressure in the
        # dashboard. Emit twice: aggregate (Environment only) + drill-down
        # dimensions (endpoint + reason).
        await emit_metric("RateLimitedRequests")
        await emit_metric("RateLimitedRequests", endpoint="mcp", reason="rate_limit")
        raise ToolError(f"Rate limit exceeded. Retry after {exc.retry_after}s.") from exc

    set_request_context(request_id, token.client_id)
    return storage, token.client_id


def _vector_store() -> VectorStore:
    return VectorStore()


def _log(storage: HiveStorage, event: ActivityEvent) -> None:
    """Record the event in both the user-visible activity log and the
    immutable compliance audit log (#395).

    Memory reads/writes/deletes surface in the Activity Log UI via the
    LOG# partition; the AUDIT# partition carries the same events but
    with a distinct retention (``HIVE_AUDIT_RETENTION_DAYS``, default
    365 days) and survives an activity-log purge.
    """
    storage.log_event(event)
    storage.log_audit_event(event)


# ---------------------------------------------------------------------------
# Response metadata — every tool response carries quota + rate-limit state
# under ``_meta.hive`` so well-behaved agents can self-throttle.
# ---------------------------------------------------------------------------


def _quota_meta(storage: HiveStorage, client_id: str) -> dict[str, Any]:
    """Build the ``_meta.hive`` block from the caller's current quota state."""
    client = storage.get_client(client_id)
    owner_user_id = client.owner_user_id if client else None
    memory_limit = get_memory_limit()
    used = storage.count_memories(owner_user_id=owner_user_id) if owner_user_id else 0
    return {
        "hive": {
            "memory_quota": {
                "used": used,
                "limit": memory_limit,
                "remaining": max(0, memory_limit - used),
            },
            "rate_limit": {
                "per_minute_limit": int(
                    os.environ.get("HIVE_RATE_LIMIT_RPM", str(DEFAULT_RATE_LIMIT_RPM))
                ),
                "per_day_limit": int(
                    os.environ.get("HIVE_RATE_LIMIT_RPD", str(DEFAULT_RATE_LIMIT_RPD))
                ),
            },
        }
    }


def _conflict_message(
    key: str,
    attempted_version: str | None,
    current_value: str | None,
    current_version: str | None,
) -> str:
    """Serialise an optimistic-lock conflict into a ToolError message (#391).

    ToolError currently has no structured-data slot, so agents parse the
    JSON block appended to the text message to decide how to reconcile.
    """
    payload = {
        "conflict": True,
        "key": key,
        "attempted_version": attempted_version,
        "current_version": current_version,
        "current_value": current_value,
    }
    return (
        f"Conflict: memory {key!r} was updated since version "
        f"{attempted_version!r}. " + json.dumps(payload)
    )


def _tool_result(
    payload: Any,
    storage: HiveStorage,
    client_id: str,
    *,
    memory: Memory | None = None,
) -> ToolResult:
    """Wrap a tool's return value in an MCP ``ToolResult`` carrying quota +
    rate-limit metadata in ``_meta.hive``. Strings become text content;
    dicts become structured content so clients can still use them directly.

    When the tool operated on a specific memory, pass it via ``memory=`` so
    its optimistic-lock version is surfaced as ``_meta.hive.memory.version``
    — the agent can thread that back into a subsequent ``remember`` call.
    """
    meta = _quota_meta(storage, client_id)
    if memory is not None:
        meta["hive"]["memory"] = {"key": memory.key, "version": memory.version}
    if isinstance(payload, dict):
        return ToolResult(structured_content=payload, meta=meta)
    return ToolResult(content=payload, meta=meta)


_SUMMARY_MAX_TOKENS = 512
_SUMMARY_SYSTEM_PROMPT = (
    "You synthesise a set of memories into a concise briefing for the agent "
    "that will use them. Return only the synthesis — no preamble, no "
    "disclaimers. Preserve specific names, numbers, and decisions verbatim; "
    "paraphrase the rest. Target 2-5 short paragraphs."
)


async def _sampled_summary(
    ctx: Context | None,
    topic: str,
    memories: list[Memory],
    fallback: str,
) -> str:
    """Synthesise a set of memories via MCP Sampling (#448).

    Sends a ``sampling/createMessage`` request back to the client and uses
    its model to produce the summary. If the client doesn't support
    sampling, the transport rejects it, or ctx is unavailable (e.g. direct
    invocation in tests), returns ``fallback`` — the deterministic
    concatenated listing — so the tool never fails just because an agent
    can't sample.
    """
    if ctx is None:
        return fallback

    body = "\n\n".join(f"- **{m.key}**: {m.value}" for m in memories)
    prompt = (
        f"The following memories are tagged '{topic}'. Synthesise them into a briefing.\n\n{body}"
    )
    try:
        result = await ctx.sample(
            prompt,
            system_prompt=_SUMMARY_SYSTEM_PROMPT,
            max_tokens=_SUMMARY_MAX_TOKENS,
        )
    except Exception:
        logger.info("MCP sampling unavailable; falling back to concat summary", exc_info=True)
        return fallback

    text = getattr(result, "text", None) or fallback
    return text.strip() or fallback


async def _report_progress(
    ctx: Context | None, progress: float, total: float | None, message: str
) -> None:
    """Emit an MCP ``notifications/progress`` event if the client supports it.

    Any exception from the transport (client doesn't support progress, the
    ctx is stale, etc.) is swallowed — progress is advisory, never fatal.
    Policy: tools whose expected duration exceeds ~2s call this at sensible
    milestones so clients can render a progress indicator.
    """
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=progress, total=total, message=message)
    except Exception:
        logger.debug("progress notification dropped", exc_info=True)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Ping",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def ping(ctx: Context | None = None) -> str:
    """Lightweight health check — returns 'ok' when the Bearer token is valid.

    Performs no storage reads or writes. A successful call confirms both
    connectivity to the MCP server and that the caller's token is still valid.
    """
    storage, client_id = await _auth(ctx)
    await emit_metric("ToolInvocations", operation="ping")
    return _tool_result("ok", storage, client_id)


@mcp.tool(
    title="Remember",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def remember(
    key: Annotated[str, "Unique key to store the memory under"],
    value: Annotated[
        str,
        f"Content of the memory. Maximum {_max_value_bytes()} bytes (UTF-8 encoded); "
        "configurable via HIVE_MAX_VALUE_BYTES.",
    ],
    tags: Annotated[list[str] | None, "Optional tags for categorisation"] = None,
    ttl_seconds: Annotated[
        int | None, "Seconds until the memory expires. None = never expires."
    ] = None,
    version: Annotated[
        str | None,
        "Optimistic-lock token from a prior recall/list_memories response. "
        "If provided, the write is rejected with a conflict error when the "
        "stored memory's version has moved on since the caller read it.",
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Store or update a memory with optional tags and optional TTL."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    limit = _max_value_bytes()
    actual = len(value.encode("utf-8"))
    if actual > limit:
        await emit_metric("ToolErrors", operation="remember")
        raise ToolError(f"Value exceeds maximum size of {limit} bytes ({actual} bytes provided)")

    tags = tags or []
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        if ttl_seconds is not None
        else None
    )

    # Check if a memory with this key already exists (upsert path)
    existing = storage.get_memory_by_key(key)

    if existing:
        # Optimistic lock: reject early if the caller's version is already stale.
        if version is not None and existing.version != version:
            await emit_metric("ToolErrors", operation="remember")
            raise ToolError(_conflict_message(key, version, existing.value, existing.version))
        # Idempotent: skip write and log if nothing changed
        if (
            existing.value == value
            and set(existing.tags) == set(tags)
            and existing.expires_at == expires_at
        ):
            logger.info(
                "Memory unchanged",
                extra={
                    "tool": "remember",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "status": "unchanged",
                },
            )
            return _tool_result(f"Memory '{key}' unchanged.", storage, client_id)
        old_size = existing.size_bytes or 0
        existing.value = value
        existing.tags = tags
        existing.expires_at = expires_at
        existing.updated_at = datetime.now(timezone.utc)
        delta = actual - old_size
        if delta > 0:
            try:
                check_storage_quota(existing.owner_user_id, delta, storage)
            except QuotaExceeded as exc:
                raise ToolError(exc.detail) from exc
        try:
            storage.put_memory(existing, expected_version=version)
        except VersionConflict as exc:
            await emit_metric("ToolErrors", operation="remember")
            raise ToolError(
                _conflict_message(
                    key, exc.attempted_version, exc.current_value, exc.current_version
                )
            ) from exc
        except ValueError as exc:
            await emit_metric("ToolErrors", operation="remember")
            raise ToolError(str(exc)) from exc
        event_type = EventType.memory_updated
        action = "Updated"
        try:
            _vector_store().upsert_memory(
                existing.model_copy(update={"value": value})
                if existing.value_type == "text-large"
                else existing
            )
        except Exception:
            logger.warning("Vector upsert failed (non-fatal)", exc_info=True)
    else:
        client = storage.get_client(client_id)
        if client is None:
            raise ToolError("Unable to load client record for authenticated caller.")
        owner_user_id = client.owner_user_id
        try:
            check_memory_quota(owner_user_id, storage)
            check_storage_quota(owner_user_id, actual, storage)
        except QuotaExceeded as exc:
            raise ToolError(exc.detail) from exc
        memory = Memory(
            key=key,
            value=value,
            tags=tags,
            owner_client_id=client_id,
            owner_user_id=owner_user_id,
            expires_at=expires_at,
        )
        try:
            storage.put_memory(memory)
        except ValueError as exc:
            await emit_metric("ToolErrors", operation="remember")
            raise ToolError(str(exc)) from exc
        event_type = EventType.memory_created
        action = "Stored"
        try:
            _vector_store().upsert_memory(
                memory.model_copy(update={"value": value})
                if memory.value_type == "text-large"
                else memory
            )
        except Exception:
            logger.warning("Vector upsert failed (non-fatal)", exc_info=True)

    _log(
        storage,
        ActivityEvent(
            event_type=event_type,
            client_id=client_id,
            metadata={"key": key, "tags": tags},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "%s memory '%s'",
        action,
        key,
        extra={
            "tool": "remember",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="remember")
    await emit_metric(
        "StorageLatencyMs", value=float(duration_ms), unit="Milliseconds", operation="remember"
    )
    return _tool_result(f"{action} memory '{key}'.", storage, client_id)


@mcp.tool(
    title="Remember if absent",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def remember_if_absent(
    key: Annotated[str, "Unique key to store the memory under"],
    value: Annotated[
        str,
        f"Content of the memory. Maximum {_max_value_bytes()} bytes (UTF-8 encoded); "
        "configurable via HIVE_MAX_VALUE_BYTES.",
    ],
    tags: Annotated[list[str] | None, "Optional tags for categorisation"] = None,
    ttl_seconds: Annotated[
        int | None, "Seconds until the memory expires. None = never expires."
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Store a memory **only if** no memory with the given key already exists.

    Returns "Stored memory '{key}'." on write, or
    "Memory '{key}' already exists — not overwritten." on skip.

    Uses a read-then-write check. Two concurrent callers with the same key
    can still race in the narrow window between the read and the write;
    strict DynamoDB-level atomicity is tracked in #391.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    limit = _max_value_bytes()
    actual = len(value.encode("utf-8"))
    if actual > limit:
        await emit_metric("ToolErrors", operation="remember_if_absent")
        raise ToolError(f"Value exceeds maximum size of {limit} bytes ({actual} bytes provided)")

    tags = tags or []
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        if ttl_seconds is not None
        else None
    )

    existing = storage.get_memory_by_key(key)
    if existing:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Memory '%s' already exists — not overwritten",
            key,
            extra={
                "tool": "remember_if_absent",
                "duration_ms": duration_ms,
                "status": "skipped",
            },
        )
        await emit_metric("ToolInvocations", operation="remember_if_absent")
        return _tool_result(f"Memory '{key}' already exists — not overwritten.", storage, client_id)

    client = storage.get_client(client_id)
    if client is None:
        raise ToolError("Unable to load client record for authenticated caller.")
    owner_user_id = client.owner_user_id
    try:
        check_memory_quota(owner_user_id, storage)
        check_storage_quota(owner_user_id, actual, storage)
    except QuotaExceeded as exc:
        raise ToolError(exc.detail) from exc

    memory = Memory(
        key=key,
        value=value,
        tags=tags,
        owner_client_id=client_id,
        owner_user_id=owner_user_id,
        expires_at=expires_at,
    )
    try:
        storage.put_memory(memory)
    except ValueError as exc:
        await emit_metric("ToolErrors", operation="remember_if_absent")
        raise ToolError(str(exc)) from exc
    try:
        _vector_store().upsert_memory(
            memory.model_copy(update={"value": value})
            if memory.value_type == "text-large"
            else memory
        )
    except Exception:
        logger.warning("Vector upsert failed (non-fatal)", exc_info=True)

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_created,
            client_id=client_id,
            metadata={"key": key, "tags": tags},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Stored memory '%s' (if_absent)",
        key,
        extra={
            "tool": "remember_if_absent",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="remember_if_absent")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="remember_if_absent",
    )
    return _tool_result(f"Stored memory '{key}'.", storage, client_id)


_BLOB_MAX_BYTES = 10 * 1024 * 1024  # 10 MB hard cap, matches Lambda payload ceiling


@mcp.tool(
    title="Remember blob",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def remember_blob(
    key: Annotated[str, "Unique key to store the binary memory under"],
    data: Annotated[str, "Base64-encoded binary content"],
    content_type: Annotated[str, "MIME type of the content (e.g. image/png, application/pdf)"],
    tags: Annotated[list[str] | None, "Optional tags for categorisation"] = None,
    ctx: Context | None = None,
) -> str:
    """Store a binary memory (image, PDF, or other binary file) identified by key.

    ``data`` must be standard Base64-encoded bytes. ``content_type`` must be a
    valid MIME type — memories whose type begins with ``image/`` are stored as
    ``value_type="image"``; all others use ``value_type="blob"``. The encoded
    payload may not exceed 10 MB.

    Calling ``remember_blob`` with the same key again replaces the existing
    blob (upsert semantics).  Use ``recall(key)`` to retrieve the blob as an
    MCP ``ImageContent`` block.
    """
    import base64

    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    content_type = content_type.strip()
    if not content_type:
        await emit_metric("ToolErrors", operation="remember_blob")
        raise ToolError("content_type must be a non-empty MIME type string.")

    try:
        raw = base64.b64decode(data, validate=True)
    except Exception as exc:
        await emit_metric("ToolErrors", operation="remember_blob")
        raise ToolError(f"data is not valid Base64: {exc}") from exc

    if len(raw) > _BLOB_MAX_BYTES:
        await emit_metric("ToolErrors", operation="remember_blob")
        raise ToolError(f"Binary payload exceeds the 10 MB limit ({len(raw)} bytes provided).")

    value_type: str = "image" if content_type.startswith("image/") else "blob"
    tags = tags or []

    existing = storage.get_memory_by_key(key)
    if existing:
        old_blob_size = existing.size_bytes or 0
        delta = len(raw) - old_blob_size
        if delta > 0:
            try:
                check_storage_quota(existing.owner_user_id, delta, storage)
            except QuotaExceeded as exc:
                raise ToolError(exc.detail) from exc
        owner = existing.owner_user_id or existing.owner_client_id
        s3_uri = storage.blob_store.put(
            owner=owner,
            memory_id=existing.memory_id,
            body=raw,
            content_type=content_type,
        )
        existing.value = ""
        existing.value_type = value_type  # type: ignore[assignment]
        existing.content_type = content_type
        existing.s3_uri = s3_uri
        existing.size_bytes = len(raw)
        existing.tags = tags
        existing.updated_at = datetime.now(timezone.utc)
        try:
            storage.put_memory(existing)
        except ValueError as exc:
            await emit_metric("ToolErrors", operation="remember_blob")
            raise ToolError(str(exc)) from exc
        event_type = EventType.memory_updated
        action = "Updated"
    else:
        client = storage.get_client(client_id)
        if client is None:
            raise ToolError("Unable to load client record for authenticated caller.")
        owner_user_id = client.owner_user_id
        try:
            check_memory_quota(owner_user_id, storage)
            check_storage_quota(owner_user_id, len(raw), storage)
        except QuotaExceeded as exc:
            raise ToolError(exc.detail) from exc
        memory = Memory(
            key=key,
            value="",
            tags=tags,
            owner_client_id=client_id,
            owner_user_id=owner_user_id,
            value_type=value_type,  # type: ignore[arg-type]
            content_type=content_type,
            size_bytes=len(raw),
        )
        owner = owner_user_id or client_id
        s3_uri = storage.blob_store.put(
            owner=owner,
            memory_id=memory.memory_id,
            body=raw,
            content_type=content_type,
        )
        memory.s3_uri = s3_uri
        try:
            storage.put_memory(memory)
        except ValueError as exc:
            await emit_metric("ToolErrors", operation="remember_blob")
            raise ToolError(str(exc)) from exc
        event_type = EventType.memory_created
        action = "Stored"

    _log(
        storage,
        ActivityEvent(
            event_type=event_type,
            client_id=client_id,
            metadata={"key": key, "tags": tags, "content_type": content_type},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "%s blob memory '%s'",
        action,
        key,
        extra={
            "tool": "remember_blob",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="remember_blob")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="remember_blob",
    )
    return _tool_result(f"{action} blob memory '{key}'.", storage, client_id)


@mcp.tool(
    title="Recall",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def recall(
    key: Annotated[str, "Key of the memory to retrieve"],
    ctx: Context | None = None,
) -> str:
    """Retrieve a memory by its key."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)

    # record_recall atomically bumps recall_count + last_accessed_at and
    # returns the updated Memory (None if missing/expired).
    memory = storage.record_recall(key)
    if memory is None:
        logger.warning(
            "Memory not found for key '%s'",
            key,
            extra={
                "tool": "recall",
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "status": "not_found",
            },
        )
        await emit_metric("ToolErrors", operation="recall")
        raise ToolError(f"No memory found for key '{key}'.")

    # A redacted memory tombstone surfaces a safe sentinel — the fact that
    # the memory once existed is itself the signal (#400).
    if memory.redacted_at is not None:
        sentinel = (
            f"Memory '{key}' was redacted on {memory.redacted_at.isoformat()}. Value removed."
        )
        _log(
            storage,
            ActivityEvent(
                event_type=EventType.memory_recalled,
                client_id=client_id,
                metadata={"key": key, "redacted": True},
            ),
        )
        await emit_metric("ToolInvocations", operation="recall")
        return _tool_result(sentinel, storage, client_id, memory=memory)

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_recalled,
            client_id=client_id,
            metadata={"key": key},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Recalled memory '%s'",
        key,
        extra={
            "tool": "recall",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="recall")
    await emit_metric(
        "StorageLatencyMs", value=float(duration_ms), unit="Milliseconds", operation="recall"
    )
    if memory.value_type == "text-large":
        try:
            recalled_value = storage.fetch_blob_value(memory)
        except Exception:
            logger.warning(
                "blob_fetch_failed for recall key='%s'",
                key,
                exc_info=True,
            )
            recalled_value = f"[memory content unavailable — blob fetch failed for key '{key}']"
        return _tool_result(recalled_value, storage, client_id, memory=memory)
    if memory.value_type in ("image", "blob"):
        import base64

        try:
            raw = storage.fetch_blob_bytes(memory)
            b64 = base64.b64encode(raw).decode("ascii")
            mime = memory.content_type or "application/octet-stream"
            meta = _quota_meta(storage, client_id)
            meta["hive"]["memory"] = {"key": memory.key, "version": memory.version}
            return ToolResult(
                content=[ImageContent(type="image", data=b64, mimeType=mime)],
                meta=meta,
            )
        except Exception:
            logger.warning(
                "blob_fetch_failed for recall key='%s'",
                key,
                exc_info=True,
            )
            recalled_value = (
                f"[binary memory content unavailable — blob fetch failed for key '{key}']"
            )
            return _tool_result(recalled_value, storage, client_id, memory=memory)
    recalled_value = memory.value or ""
    return _tool_result(recalled_value, storage, client_id, memory=memory)


@mcp.tool(
    title="Forget",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def forget(
    key: Annotated[str, "Key of the memory to delete"],
    ctx: Context | None = None,
) -> str:
    """Delete a memory by its key."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    existing = storage.get_memory_by_key(key)
    if existing is None:
        logger.warning(
            "Memory not found for key '%s'",
            key,
            extra={
                "tool": "forget",
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "status": "not_found",
            },
        )
        await emit_metric("ToolErrors", operation="forget")
        raise ToolError(f"No memory found for key '{key}'.")

    storage.delete_memory(existing.memory_id)
    try:
        _vector_store().delete_memory(existing.memory_id, client_id)
    except Exception:
        logger.warning("Vector delete failed (non-fatal)", exc_info=True)
    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_deleted,
            client_id=client_id,
            metadata={"key": key},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Deleted memory '%s'",
        key,
        extra={
            "tool": "forget",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="forget")
    await emit_metric(
        "StorageLatencyMs", value=float(duration_ms), unit="Milliseconds", operation="forget"
    )
    return _tool_result(f"Deleted memory '{key}'.", storage, client_id)


@mcp.tool(
    title="Forget all (by tag)",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def forget_all(
    tag: Annotated[str, "Tag of the memories to delete"],
    ctx: Context | None = None,
) -> str:
    """Delete all memories that have the given tag."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    deleted = storage.delete_memories_by_tag(tag)
    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_deleted,
            client_id=client_id,
            metadata={"tag": tag, "count": deleted},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Deleted %d memories with tag '%s'",
        deleted,
        tag,
        extra={
            "tool": "forget_all",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="forget_all")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="forget_all",
    )
    return _tool_result(f"Deleted {deleted} memories with tag '{tag}'.", storage, client_id)


_REDACTION_SENTINEL = "__redacted__"


@mcp.tool(
    title="Redact memory",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def redact_memory(
    key: Annotated[str, "Key of the memory to redact"],
    reason: Annotated[
        str | None,
        "Optional reason written to the audit trail (PII, secret leak, etc.)",
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Tombstone a memory: replace its value with a sentinel and record
    ``redacted_at``, preserving the audit trail (#400).

    Use this when the value contains content that must be removed (PII,
    secret accidentally captured, etc.) but the fact that the memory
    existed is itself meaningful. For full deletion, use ``forget``.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    existing = storage.get_memory_by_key(key)
    if existing is None:
        await emit_metric("ToolErrors", operation="redact_memory")
        raise ToolError(f"No memory found for key '{key}'.")
    if existing.is_redacted:
        return _tool_result(f"Memory '{key}' is already redacted.", storage, client_id)

    # Record the pre-redaction value in the audit log BEFORE we overwrite
    # it — the tombstone path is the only thing that preserves what was
    # there when a reviewer needs to understand a redaction after-the-fact.
    storage.log_audit_event(
        ActivityEvent(
            event_type=EventType.memory_redacted,
            client_id=client_id,
            metadata={
                "key": key,
                "memory_id": existing.memory_id,
                "reason": reason,
                "previous_value": existing.value,
                "previous_tags": existing.tags,
            },
        )
    )

    existing.value = _REDACTION_SENTINEL
    existing.redacted_at = datetime.now(timezone.utc)
    existing.updated_at = existing.redacted_at
    storage.put_memory(existing)
    try:
        _vector_store().delete_memory(existing.memory_id, client_id)
    except Exception:
        logger.warning("Vector delete on redaction failed (non-fatal)", exc_info=True)

    # The user-visible activity log gets a sanitised entry so the Activity Log
    # UI surfaces the redaction without leaking the pre-redaction value.
    storage.log_event(
        ActivityEvent(
            event_type=EventType.memory_redacted,
            client_id=client_id,
            metadata={"key": key, "reason": reason},
        )
    )

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Redacted memory '%s'",
        key,
        extra={"tool": "redact_memory", "duration_ms": duration_ms, "status": "success"},
    )
    await emit_metric("ToolInvocations", operation="redact_memory")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="redact_memory",
    )
    return _tool_result(f"Redacted memory '{key}'.", storage, client_id)


@mcp.tool(
    title="Memory history",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def memory_history(
    key: Annotated[str, "Key of the memory to retrieve history for"],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Return the version history of a memory (previous values before each overwrite)."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:read")

    memory = storage.get_memory_by_key(key)
    if memory is None:
        raise ToolError(f"No memory found for key '{key}'.")
    versions = storage.list_memory_versions(memory.memory_id)
    duration_ms = int((time.monotonic() - t0) * 1000)
    await emit_metric("ToolInvocations", operation="memory_history")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="memory_history",
    )
    items = [
        {
            "version_timestamp": v.version_timestamp,
            "value": v.value,
            "tags": v.tags,
            "recorded_at": v.recorded_at.isoformat(),
        }
        for v in versions
    ]
    return _tool_result({"versions": items, "count": len(items)}, storage, client_id)


@mcp.tool(
    title="Restore memory",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def restore_memory(
    key: Annotated[str, "Key of the memory to restore"],
    version_timestamp: Annotated[str, "Version timestamp to restore (from memory_history)"],
    ctx: Context | None = None,
) -> str:
    """Restore a memory to a previous version."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope="memories:write")

    memory = storage.get_memory_by_key(key)
    if memory is None:
        raise ToolError(f"No memory found for key '{key}'.")
    version = storage.get_memory_version(memory.memory_id, version_timestamp)
    if version is None:
        raise ToolError(f"Version '{version_timestamp}' not found for memory '{key}'.")

    memory.value = version.value
    memory.tags = version.tags
    memory.updated_at = datetime.now(timezone.utc)
    storage.put_memory(memory)
    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_updated,
            client_id=client_id,
            metadata={"key": key, "version_timestamp": version_timestamp},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    await emit_metric("ToolInvocations", operation="restore_memory")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="restore_memory",
    )
    return _tool_result(
        f"Restored memory '{key}' to version '{version_timestamp}'.", storage, client_id
    )


@mcp.tool(
    title="List memories",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def list_memories(
    tag: Annotated[str, "Tag to filter memories by"],
    limit: Annotated[int, "Maximum number of memories to return (1–500)"] = 100,
    cursor: Annotated[str | None, "Pagination cursor from a previous call"] = None,
    include_redacted: Annotated[
        bool,
        "Include tombstoned (redacted) memories in the result. False by default.",
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List memories that have a specific tag, with optional pagination."""
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    client = storage.get_client(client_id)
    if client is None:
        raise ToolError("Unable to load client record for authenticated caller.")
    if client.owner_user_id is None:
        raise ToolError(
            "Client is not associated with a user account; per-user memory scoping is required."
        )
    owner_user_id = client.owner_user_id

    limit = max(1, min(limit, 500))
    memories, next_cursor = storage.list_memories_by_tag(
        tag, limit=limit, cursor=cursor, owner_user_id=owner_user_id
    )
    if not include_redacted:
        memories = [m for m in memories if not m.is_redacted]
    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_listed,
            client_id=client_id,
            metadata={"tag": tag, "count": len(memories)},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Listed %d memories for tag '%s'",
        len(memories),
        tag,
        extra={
            "tool": "list_memories",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="list_memories")
    await emit_metric(
        "StorageLatencyMs", value=float(duration_ms), unit="Milliseconds", operation="list_memories"
    )
    result: dict[str, Any] = {
        "items": [
            {
                "key": m.key,
                "value": m.value if m.value_type not in ("image", "blob") else None,
                "value_type": m.value_type,
                "content_type": m.content_type,
                "size_bytes": m.size_bytes,
                "tags": m.tags,
                "owner_client_id": m.owner_client_id,
                "recall_count": m.recall_count,
                "last_accessed_at": (
                    m.last_accessed_at.isoformat() if m.last_accessed_at else None
                ),
                "version": m.version,
            }
            for m in memories
        ],
        "count": len(memories),
        "has_more": next_cursor is not None,
    }
    if next_cursor:
        result["next_cursor"] = next_cursor
    return _tool_result(result, storage, client_id)


@mcp.tool(
    title="List tags",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def list_tags(ctx: Context | None = None) -> dict[str, Any]:
    """List all distinct tags currently in use across the caller's memories.

    Returns tags sorted alphabetically. Useful for discovering the tag
    namespace of an existing memory corpus before calling `list_memories`.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    tags = storage.list_distinct_tags(client_id)
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Listed %d distinct tags",
        len(tags),
        extra={
            "tool": "list_tags",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="list_tags")
    await emit_metric(
        "StorageLatencyMs", value=float(duration_ms), unit="Milliseconds", operation="list_tags"
    )
    return _tool_result({"tags": tags, "count": len(tags)}, storage, client_id)


@mcp.tool(
    title="Summarise context",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def summarize_context(
    topic: Annotated[str, "Topic or tag to summarise memories about"],
    ctx: Context | None = None,
) -> str:
    """
    Retrieve all memories related to a topic and return a synthesised summary.

    Memories are retrieved by tag matching the topic.  The summary lists each
    memory and then provides a combined overview paragraph.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    client = storage.get_client(client_id)
    if client is None:
        raise ToolError("Unable to load client record for authenticated caller.")
    if client.owner_user_id is None:
        raise ToolError(
            "Client is not associated with a user account; per-user memory scoping is required."
        )
    owner_user_id = client.owner_user_id

    await _report_progress(ctx, 0, 2, f"Retrieving memories for '{topic}'...")
    memories, _ = storage.list_memories_by_tag(topic, limit=500, owner_user_id=owner_user_id)
    await _report_progress(
        ctx, 1, 2, f"Retrieved {len(memories)} memories; synthesising summary..."
    )

    if not memories:
        logger.info(
            "No memories for topic '%s'",
            topic,
            extra={
                "tool": "summarize_context",
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "status": "empty",
            },
        )
        await emit_metric("ToolInvocations", operation="summarize_context")
        return _tool_result(f"No memories found for topic '{topic}'.", storage, client_id)

    lines = [f"## Memories tagged '{topic}'\n"]
    for m in memories:
        lines.append(f"**{m.key}**: {m.value}")

    lines.append(f"\n---\n*{len(memories)} memory/memories found for topic '{topic}'.*")
    concat_summary = "\n".join(lines)

    # Try MCP Sampling first (#448). If the client supports it, we get a real
    # LLM synthesis without any server-side Bedrock cost; otherwise the
    # sampler raises and we fall back to the concatenated listing above.
    summary = await _sampled_summary(ctx, topic, memories, concat_summary)

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.context_summarized,
            client_id=client_id,
            metadata={"topic": topic, "memory_count": len(memories)},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Summarized %d memories for topic '%s'",
        len(memories),
        topic,
        extra={
            "tool": "summarize_context",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="summarize_context")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="summarize_context",
    )
    return _tool_result(summary, storage, client_id)


@mcp.tool(
    title="Search memories",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def search_memories(
    query: Annotated[str, "Natural language search query"],
    top_k: Annotated[int, "Maximum number of results to return (1–50)"] = 10,
    min_score: Annotated[
        float | None,
        "Minimum blended score (0.0–1.0). Results below this threshold are "
        "excluded. None disables filtering.",
    ] = None,
    filter_tags: Annotated[
        list[str] | None,
        "Optional list of tags. Only memories carrying ALL of the given tags "
        "are returned. None disables filtering.",
    ] = None,
    w_semantic: Annotated[
        float, "Weight for semantic/vector similarity (default 0.6)"
    ] = DEFAULT_W_SEMANTIC,
    w_keyword: Annotated[
        float, "Weight for keyword (term-frequency) match (default 0.3)"
    ] = DEFAULT_W_KEYWORD,
    w_recency: Annotated[
        float, "Weight for recency decay against last_accessed_at/updated_at (default 0.1)"
    ] = DEFAULT_W_RECENCY,
    include_redacted: Annotated[
        bool,
        "Include tombstoned (redacted) memories in the result. False by default.",
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search memories using hybrid retrieval: semantic + keyword + recency.

    Final score is a weighted sum of (a) cosine similarity from the vector
    store, (b) a term-frequency keyword match, and (c) an exponential
    recency decay. Weights are re-normalised to sum to 1.0; pass any
    relative weighting. Per-signal sub-scores are returned on each item
    for debugging.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    top_k = max(1, min(top_k, 50))
    threshold = max(0.0, min(1.0, min_score)) if min_score is not None else None
    required_tags = set(filter_tags) if filter_tags else None

    # Always request a wider candidate pool than top_k so keyword + recency
    # blending has headroom to re-rank, and (if tag filtering is on) so the
    # post-filter still leaves up to top_k survivors.
    search_top_k = 50 if required_tags else min(max(top_k * 3, 10), 50)

    await _report_progress(ctx, 0, 3, f"Running vector search for '{query}'...")
    try:
        pairs = _vector_store().search(query, client_id, top_k=search_top_k)
    except VectorIndexNotFoundError:
        return _tool_result({"items": [], "count": 0, "query": query}, storage, client_id)
    except Exception:
        logger.warning("Vector search failed (non-fatal)", exc_info=True)
        return _tool_result({"items": [], "count": 0, "query": query}, storage, client_id)

    await _report_progress(
        ctx, 1, 3, f"Vector search returned {len(pairs)} candidates; hydrating..."
    )
    hydrated = storage.hydrate_memory_ids(pairs)

    # Score each hydrated memory. sem_map lets us pair each Memory with its
    # original cosine similarity; absent memories (hydrate dropped expired
    # ones) are simply skipped.
    query_tokens = tokenize(query)
    now = datetime.now(timezone.utc)
    scored: list[tuple[Memory, float, float, float, float]] = []
    for m, sem in hydrated:
        # For text-large memories, keyword scoring uses the empty inline
        # placeholder — fetching S3 blobs per candidate would be too
        # expensive. Semantic relevance from the vector index covers the
        # large-document recall path.
        kw = keyword_score(query_tokens, m.value or "")
        rec = recency_score(m, now=now)
        blended = blend_score(
            semantic=sem,
            keyword=kw,
            recency=rec,
            w_semantic=w_semantic,
            w_keyword=w_keyword,
            w_recency=w_recency,
        )
        scored.append((m, blended, sem, kw, rec))

    if not include_redacted:
        scored = [row for row in scored if not row[0].is_redacted]

    if threshold is not None:
        scored = [row for row in scored if row[1] >= threshold]

    if required_tags:
        scored = [row for row in scored if required_tags.issubset(row[0].tags)]

    scored.sort(key=lambda row: row[1], reverse=True)
    scored = scored[:top_k]
    await _report_progress(ctx, 2, 3, f"Ranked {len(scored)} result(s); returning.")

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_searched,
            client_id=client_id,
            metadata={"query": query, "result_count": len(scored)},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Searched memories for '%s', %d result(s)",
        query,
        len(scored),
        extra={
            "tool": "search_memories",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="search_memories")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="search_memories",
    )
    return _tool_result(
        {
            "items": [
                MemorySearchResult.from_memory_and_score(
                    m,
                    blended,
                    semantic_score=sem,
                    keyword_score=kw,
                    recency_score=rec,
                ).model_dump()
                for m, blended, sem, kw, rec in scored
            ],
            "count": len(scored),
            "query": query,
        },
        storage,
        client_id,
    )


@mcp.tool(
    title="Relate memories",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def relate_memories(
    key: Annotated[str, "Key of the memory to find relations for"],
    top_k: Annotated[int, "Maximum number of results to return (1–50)"] = 5,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Return memories most semantically similar to the one at ``key``.

    The source memory's value is used as the vector search query and the
    source memory itself is excluded from the results.  ``score`` ranges
    from 0.0 to 1.0 where higher means more semantically similar.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    top_k = max(1, min(top_k, 50))

    memory = storage.get_memory_by_key(key)
    if memory is None:
        raise ToolError(f"No memory found for key '{key}'.")

    query_value = memory.value or ""
    if memory.value_type == "text-large":
        try:
            query_value = storage.fetch_blob_value(memory)
        except Exception:
            logger.warning(
                "blob_fetch_failed for relate_memories key='%s'",
                key,
                exc_info=True,
            )

    try:
        # Fetch top_k+1 so that dropping the source still leaves up to top_k.
        pairs = _vector_store().search(query_value, client_id, top_k=top_k + 1)
    except VectorIndexNotFoundError:
        return _tool_result({"items": [], "count": 0, "key": key}, storage, client_id)
    except Exception:
        logger.warning("Vector search failed (non-fatal)", exc_info=True)
        return _tool_result({"items": [], "count": 0, "key": key}, storage, client_id)

    pairs = [(mid, score) for mid, score in pairs if mid != memory.memory_id][:top_k]
    results = storage.hydrate_memory_ids(pairs)

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_searched,
            client_id=client_id,
            metadata={"key": key, "result_count": len(results), "related_to": memory.memory_id},
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "Related memories for '%s', %d result(s)",
        key,
        len(results),
        extra={
            "tool": "relate_memories",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="relate_memories")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="relate_memories",
    )
    return _tool_result(
        {
            "items": [
                MemorySearchResult.from_memory_and_score(m, score).model_dump()
                for m, score in results
            ],
            "count": len(results),
            "key": key,
        },
        storage,
        client_id,
    )


# ---------------------------------------------------------------------------
# pack_context (#452)
# ---------------------------------------------------------------------------
#
# Token-budget-aware retrieval: agents ask for "as much relevant context
# as fits in N tokens" rather than top-K or everything-under-a-tag. The
# tool runs the same hybrid search as `search_memories`, re-orders by
# the caller's preferred strategy, estimates tokens per candidate, and
# greedily packs until the budget is exhausted.


_PACK_CONTEXT_CANDIDATE_POOL = 50
_PACK_CONTEXT_DEFAULT_BUDGET = 2000
_PACK_CONTEXT_MAX_BUDGET = 100_000
# Conservative char-per-token ratio that covers both English prose and
# code/JSON fragments without pulling in tiktoken (a ~10MB C extension).
# Over-estimating is fine — agents prefer under-budget to over-budget.
_PACK_CONTEXT_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count for a block of text.

    Uses a simple chars-per-token heuristic (4 chars ≈ 1 token, the
    long-run Anthropic/OpenAI English average) instead of tiktoken so
    the Lambda bundle stays slim. Slightly conservative — the packer
    would rather leave budget on the table than overflow.
    """
    if not text:
        return 0
    # ceil so a 3-char string still costs 1 token, not 0.
    return (len(text) + _PACK_CONTEXT_CHARS_PER_TOKEN - 1) // _PACK_CONTEXT_CHARS_PER_TOKEN


def _score_for_ordering(
    ordering: str,
    *,
    semantic: float,
    recency: float,
    blended: float,
) -> float:
    """Pick the sort key for a candidate memory based on the ordering mode.

    Extracted so the pack-context unit tests can assert each mode
    directly without walking the full pipeline.
    """
    if ordering == "relevance":
        return semantic
    if ordering == "recency":
        return recency
    # Default: relevance+recency blend (matches search_memories default).
    return blended


def pack_memories_within_budget(
    memories: list[tuple[Memory, float]],
    budget_tokens: int,
) -> tuple[list[Memory], int]:
    """Greedily pack memories into a token budget, preserving input order.

    ``memories`` is a pre-sorted list of ``(Memory, score)`` tuples.
    The function preserves the upstream ordering and ignores ``score``
    itself — the caller is responsible for sorting. Returns the subset
    that fits and the sum of their estimated tokens (including the
    ``\\n`` separators that ``_render_packed_context`` inserts between
    entries, so the returned token count matches the rendered block).

    Items larger than the remaining budget are skipped — we don't
    truncate individual memories because a half-quoted decision is
    worse than a missing one. The caller can raise the budget or
    adjust ordering to surface smaller candidates.
    """
    separator_tokens = estimate_tokens("\n")
    packed: list[Memory] = []
    used = 0
    for memory, _score in memories:
        entry_tokens = estimate_tokens(_render_memory_entry(memory))
        # First entry has no preceding separator; subsequent ones do,
        # matching what `_render_packed_context` will actually emit.
        additional = entry_tokens + (separator_tokens if packed else 0)
        if used + additional > budget_tokens:
            continue
        packed.append(memory)
        used += additional
    return packed, used


def _render_memory_entry(memory: Memory) -> str:
    """Render a single memory as the line shape used in the packed block."""
    return f"- **{memory.key}**: {memory.value}"


def _memory_label(count: int) -> str:
    """Return the correctly pluralised label for a memory count."""
    return "memory" if count == 1 else "memories"


def _render_packed_context(topic: str, packed: list[Memory], used_tokens: int) -> str:
    """Render the full packed-context string the tool returns.

    Separated from the tool body so the formatting is unit-testable
    without any storage or auth plumbing.
    """
    count = len(packed)
    label = _memory_label(count)
    if not packed:
        return (
            f"## Context for {topic!r} (0 {label}, ~0 tokens)\n\n"
            "_No relevant memories fit within the token budget._"
        )
    header = f"## Context for {topic!r} ({count} {label}, ~{used_tokens} tokens)"
    body = "\n".join(_render_memory_entry(m) for m in packed)
    return f"{header}\n\n{body}"


def _render_empty_within_budget(topic: str, budget_tokens: int) -> str:
    """Render the best empty-state response that fits in the budget.

    Tries the full ``_render_packed_context(topic, [], 0)`` first
    (header + explanatory body). If that overshoots the budget, falls
    back to progressively shorter strings so the advertised budget
    contract holds even on the vector-error / no-index branches.
    """
    full = _render_packed_context(topic, [], 0)
    if estimate_tokens(full) <= budget_tokens:
        return full
    # Drop the explanatory body; header alone is usually well under 20 tokens.
    header_only = f"## Context for {topic!r} (0 memories, ~0 tokens)"
    if estimate_tokens(header_only) <= budget_tokens:
        return header_only
    # Last-resort terse fallback for single-digit budgets. Agents asking
    # for <5 tokens of context are doing something pathological, but we
    # still honour the contract.
    terse = "_no context_"
    if estimate_tokens(terse) <= budget_tokens:
        return terse
    return ""


@mcp.tool(
    title="Pack context",
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
async def pack_context(
    topic: Annotated[str, "Topic / query to retrieve context for"],
    budget_tokens: Annotated[
        int,
        "Maximum tokens in the returned context block (1–100000). Defaults to 2000.",
    ] = _PACK_CONTEXT_DEFAULT_BUDGET,
    ordering: Annotated[
        str,
        "How to rank candidates before packing: 'relevance' (pure semantic), "
        "'recency' (last-accessed decay, falling back to updated-at decay), or "
        "'relevance+recency' (blend, default).",
    ] = "relevance+recency",
    ctx: Context | None = None,
) -> str:
    """Retrieve as many relevant memories as fit within ``budget_tokens``.

    Unlike ``search_memories`` (fixed top-K) or ``list_memories`` (full
    tag slice), ``pack_context`` lets the agent ask for "fill my
    remaining context window with the most useful memories about X".
    The return is a markdown block ready to drop straight into a
    prompt — caller doesn't need to post-process JSON.
    """
    t0 = time.monotonic()
    storage, client_id = await _auth(ctx, required_scope=_MEMORIES_READ_SCOPE)
    budget = max(1, min(int(budget_tokens), _PACK_CONTEXT_MAX_BUDGET))
    mode = (
        ordering
        if ordering in {"relevance", "recency", "relevance+recency"}
        else ("relevance+recency")
    )

    try:
        pairs = _vector_store().search(topic, client_id, top_k=_PACK_CONTEXT_CANDIDATE_POOL)
    except VectorIndexNotFoundError:
        return _tool_result(_render_empty_within_budget(topic, budget), storage, client_id)
    except Exception:
        logger.warning("Vector search failed in pack_context (non-fatal)", exc_info=True)
        return _tool_result(_render_empty_within_budget(topic, budget), storage, client_id)

    hydrated = storage.hydrate_memory_ids(pairs)

    # Score every candidate through the standard blend pipeline so the
    # `relevance+recency` mode matches search_memories exactly.
    query_tokens = tokenize(topic)
    now = datetime.now(timezone.utc)
    scored: list[tuple[Memory, float]] = []
    for memory, sem in hydrated:
        if memory.is_redacted:
            continue
        kw = keyword_score(query_tokens, memory.value or "")
        rec = recency_score(memory, now=now)
        blended = blend_score(semantic=sem, keyword=kw, recency=rec)
        scored.append(
            (memory, _score_for_ordering(mode, semantic=sem, recency=rec, blended=blended))
        )

    # Sort descending by chosen score; `reverse=True` keeps the highest
    # scorer first for the greedy packer to fit first.
    scored.sort(key=lambda row: row[1], reverse=True)
    # Reserve budget for the header + trailing blank line so the total
    # rendered tokens stay under the advertised `budget`. Use the most
    # expensive possible header (assumes 5-digit `used_tokens` and
    # 3-digit count) so we never under-reserve.
    header_reserve = estimate_tokens(f"## Context for {topic!r} (000 memories, ~00000 tokens)\n\n")
    if budget <= header_reserve:
        # Tiny budget — can't even fit the header. Degrade straight
        # through the same fallback ladder as the vector-error branches.
        rendered = _render_empty_within_budget(topic, budget)
        packed: list[Memory] = []
        used_tokens = 0
    else:
        packed, used_tokens = pack_memories_within_budget(scored, budget - header_reserve)
        rendered = _render_packed_context(topic, packed, used_tokens)
        # Belt-and-braces: if our token estimate still overshoots the
        # rendered output (e.g. weird unicode the heuristic mis-counts),
        # collapse to the empty fallback so the contract holds.
        if estimate_tokens(rendered) > budget:
            rendered = _render_empty_within_budget(topic, budget)
            packed = []
            used_tokens = 0

    _log(
        storage,
        ActivityEvent(
            event_type=EventType.memory_searched,
            client_id=client_id,
            metadata={
                "tool": "pack_context",
                "topic": topic,
                "budget_tokens": budget,
                "ordering": mode,
                "packed_count": len(packed),
                "used_tokens": used_tokens,
            },
        ),
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "pack_context for '%s': %d memories in %d/%d tokens",
        topic,
        len(packed),
        used_tokens,
        budget,
        extra={
            "tool": "pack_context",
            "duration_ms": duration_ms,
            "status": "success",
        },
    )
    await emit_metric("ToolInvocations", operation="pack_context")
    await emit_metric(
        "StorageLatencyMs",
        value=float(duration_ms),
        unit="Milliseconds",
        operation="pack_context",
    )
    return _tool_result(rendered, storage, client_id)


# ---------------------------------------------------------------------------
# MCP Prompts (#447)
# ---------------------------------------------------------------------------
#
# MCP Prompts are pre-built, parameterised prompt templates that supported
# clients (e.g. Claude Code, Cursor) surface as slash commands. Each prompt
# returns a string; FastMCP wraps it as a single user-role message under the
# hood. The agent then executes the template by calling the named Hive tool.
#
# These prompts are pure templates — they do not hit DynamoDB, and
# deliberately do not require auth (the underlying tool call does). That
# keeps the prompt renderer cheap and means unauthenticated clients can
# still discover + inspect them.


@mcp.prompt(
    name="recall-context",
    title="Recall context",
    description=(
        "Recall everything Hive knows about a topic and use it as foreground "
        "context for the rest of the conversation."
    ),
)
def recall_context_prompt(
    topic: Annotated[str, "Topic to summarise memories about"],
) -> str:
    # `!r` renders the string as a Python repr so apostrophes, quotes,
    # and newlines in the user input don't produce an ambiguous
    # pseudo-call signature. The agent still interprets the instruction
    # in prose — `!r` just keeps the argument boundaries unambiguous.
    return (
        f"Use Hive to recall what I know about {topic!r}. Call the "
        f"`summarize_context` tool with topic={topic!r}, then treat the "
        "result as foreground context for the rest of this conversation. "
        "If the summary is empty, say so and ask what I'd like to remember."
    )


@mcp.prompt(
    name="what-do-you-know-about",
    title="What do you know about…",
    description=(
        "Semantic-search Hive's memories for a free-text query and weave the "
        "top results into the next response."
    ),
)
def what_do_you_know_about_prompt(
    query: Annotated[str, "Free-text query to search memories for"],
) -> str:
    return (
        f"Search Hive for {query!r}. Call `search_memories` with query={query!r} "
        "and top_k=10. Read the returned memories and incorporate them into "
        "your next response, citing each memory's key. If the returned items "
        "list is empty, say so plainly."
    )


@mcp.prompt(
    name="remember-this",
    title="Remember this",
    description=(
        "Store a memory in Hive under a given key, optionally tagged. Supply "
        "the value explicitly; tags may be omitted."
    ),
)
def remember_this_prompt(
    key: Annotated[str, "Unique key to store the memory under"],
    value: Annotated[str, "Content of the memory — pass the current selection"],
    tags: Annotated[
        str,
        "Optional comma-separated tags (e.g. 'work,roadmap'). Empty for none.",
    ] = "",
) -> str:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_clause = f" tags={tag_list!r}" if tag_list else " tags=[]"
    return (
        f"Store this in Hive. Call `remember` with key={key!r},{tag_clause}, "
        f"and value={value!r}. Confirm once the memory is written, quoting "
        "the returned memory_id."
    )


@mcp.prompt(
    name="forget-older-than",
    title="Forget older than…",
    description=(
        "Enumerate memories older than N days and interactively forget them. "
        "Pairs with the bulk-delete flow (#427) — agent must confirm each "
        "deletion with the user before calling `forget`."
    ),
)
def forget_older_than_prompt(
    days: Annotated[int, "Drop memories whose last access is older than this many days"],
) -> str:
    # Uses only tools Hive actually exposes. `list_memories` needs a
    # tag, so iterate `list_tags()` → `list_memories(tag)`. The tool
    # response surfaces `last_accessed_at` and `version` (a UTC ISO
    # timestamp that updates on every write); `version` is the
    # well-defined fallback when `last_accessed_at` is null (memory
    # written but never recalled).
    return (
        f"Help me prune stale memories. Call `list_tags` to discover my tag "
        f"namespace, then for each tag call `list_memories(tag)`. For every "
        f"memory whose `last_accessed_at` is more than {days} days ago — or "
        f"whose `last_accessed_at` is null and whose `version` timestamp is "
        f"more than {days} days ago — show me the key plus the timestamp "
        "you used (`last_accessed_at` or `version`) and ask 'forget this?' — "
        "only call `forget` when I reply yes. Do not batch-delete without "
        "confirmation."
    )


# ---------------------------------------------------------------------------
# MCP Resources (#446)
# ---------------------------------------------------------------------------
#
# Exposes the caller's memories as read-only MCP Resources in addition
# to the existing tool surface. Supported URIs:
#
#   memory://_index       — newline-separated list of memory:// URIs the
#                           authenticated client owns
#   memory://{key}        — the value of a single memory, addressable by
#                           key
#
# The leading underscore on `_index` puts it in a reserved namespace so
# a user can still store and read a memory whose key is literally
# `index` — otherwise the concrete URI would shadow the template.
#
# All reads are scoped to the authenticated OAuth client (client_id) and
# require the `memories:read` scope. Resources are intentionally read-
# only — writes still go through the `remember` tool so the quota + TTL
# + version machinery stays in one place.


_MEMORY_RESOURCE_LIST_LIMIT = 500


def _encode_memory_key(key: str) -> str:
    """Percent-encode a memory key for use in a ``memory://`` URI.

    Keys legally contain ``/``, ``:``, and other characters the URI
    grammar treats as structural (authority / path / query delimiters),
    so a naive ``f"memory://{key}"`` produces an ambiguous URI that
    clients can't parse back to the original key. Quote everything
    except ASCII alphanumerics and the unreserved-char set; the result
    round-trips losslessly via ``_decode_memory_key``.
    """
    # `safe=""` forces `/` + `:` to be encoded; alphanumerics and
    # unreserved chars (`-_.~`) pass through unchanged.
    return quote(key, safe="")


def _decode_memory_key(encoded: str) -> str:
    """Inverse of ``_encode_memory_key``."""
    return unquote(encoded)


def _resource_auth() -> tuple[HiveStorage, str]:
    """Resolve ``(storage, client_id)`` for an MCP Resource read.

    Resources don't receive a ``Context`` object the way tools do, so
    the token is pulled via ``get_access_token()`` — the
    ``RemoteAuthProvider`` on the ``FastMCP`` instance has already
    validated it by the time the handler runs.

    Applies the same per-client rate-limit the tool-side ``_auth()``
    uses: even though resource reads are cheap individually, the
    ``memory://index`` handler scans DynamoDB and a misbehaving client
    could run the account's rate-limit budget without it.

    Raises ``ValueError`` on missing token / insufficient scope / rate
    limit; the MCP framework surfaces that as an error response.
    """
    token = get_access_token()
    if token is None:
        raise ValueError("Unauthorized: no valid access token")
    scopes = set(token.scopes or [])
    if _MEMORIES_READ_SCOPE not in scopes:
        raise ValueError(f"Insufficient scope: '{_MEMORIES_READ_SCOPE}' required")
    storage = HiveStorage()
    try:
        check_rate_limit(token.client_id, storage)
    except RateLimitExceeded as exc:
        raise ValueError(f"Rate limit exceeded. Retry after {exc.retry_after}s.") from exc
    return storage, token.client_id


@mcp.resource(
    "memory://_index",
    name="Memory index",
    description=(
        "Newline-separated list of `memory://` URIs owned by the authenticated "
        "client. Read this first to discover what's available, then read "
        "individual memories via `memory://{key}`. Keys containing `/` or `:` "
        "are percent-encoded so each URI round-trips losslessly. The "
        "underscore-prefixed path is reserved so a memory with the literal "
        "key `index` can still be read via `memory://index`."
    ),
    mime_type="text/plain",
)
def list_memory_resources() -> str:
    storage, client_id = _resource_auth()
    memories, next_cursor = storage.list_all_memories(
        client_id=client_id, limit=_MEMORY_RESOURCE_LIST_LIMIT
    )
    # Skip both redacted and expired entries — otherwise the index can
    # advertise keys that `read_memory_resource` will later 404 on
    # (`get_memory_by_id` filters expired, `list_all_memories` doesn't).
    uris = sorted(
        f"memory://{_encode_memory_key(m.key)}"
        for m in memories
        if not m.is_redacted and not m.is_expired
    )
    body = "\n".join(uris)
    if next_cursor:
        # Flag that the index view is capped so the agent knows to
        # fall back to `list_memories(tag=…)` for narrower retrieval.
        # Redacted + expired items are filtered out of the body above,
        # so the visible URI count is often less than the cap — avoid
        # implying the body itself holds exactly _MEMORY_RESOURCE_LIST_LIMIT
        # entries.
        body += (
            f"\n\n_(Index capped at {_MEMORY_RESOURCE_LIST_LIMIT} entries; "
            "more results may exist. Use the `list_memories` tool with "
            "tags for targeted retrieval.)_"
        )
    return body


@mcp.resource(
    "memory://{key}",
    name="Memory content",
    description=(
        "Read the value of a single memory by its key. Scoped to the authenticated "
        "OAuth client. The `{key}` portion may be percent-encoded — keys with "
        "`/` or `:` work as long as they're quoted."
    ),
    mime_type="text/plain",
)
def read_memory_resource(key: str) -> str:
    storage, client_id = _resource_auth()
    # FastMCP passes the URI template parameter as the encoded substring;
    # decode back to the original key before hitting storage.
    decoded_key = _decode_memory_key(key)
    memory = storage.get_memory_by_key(decoded_key)
    # Tenant isolation: `get_memory_by_key` doesn't filter by owner, so
    # a client asking for another tenant's key would otherwise succeed.
    # Treat cross-tenant lookups as 404 to avoid leaking existence.
    # `!r` quotes the key in error messages so a client key containing
    # newlines / control chars can't forge fake log lines or break the
    # response envelope for clients that render the error verbatim.
    if memory is None or memory.owner_client_id != client_id:
        raise ValueError(f"Memory not found: {decoded_key!r}")
    if memory.is_redacted:
        raise ValueError(f"Memory has been redacted: {decoded_key!r}")
    if memory.value_type == "text-large":
        try:
            return storage.fetch_blob_value(memory)
        except Exception:
            logger.warning(
                "blob_fetch_failed for resource key='%s'",
                decoded_key,
                exc_info=True,
            )
            return f"[memory content unavailable — blob fetch failed for key {decoded_key!r}]"
    return memory.value or ""


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

# Module-level ASGI app — used by uvicorn for local dev:
#   uvicorn hive.server:asgi_app --port 8002
# Uvicorn manages lifespan correctly (startup once, shutdown once).
asgi_app = mcp.http_app(stateless_http=True, json_response=True)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:  # pragma: no cover
    """AWS Lambda + Function URL handler (HTTP mode).

    Creates a fresh ASGI app per Lambda container initialisation.
    FastMCP's StreamableHTTPSessionManager can only be started once per
    instance, so we cannot reuse the module-level asgi_app across warm
    Lambda invocations where Mangum re-runs the lifespan on each call.
    """
    try:
        from mangum import Mangum
    except ImportError as exc:
        raise RuntimeError("mangum is required for Lambda deployment") from exc

    _app = mcp.http_app(stateless_http=True, json_response=True)
    _app.add_middleware(_OriginVerifyMiddleware)
    handler = Mangum(_app, lifespan="on")
    return handler(event, context)  # type: ignore[arg-type]  # mangum stubs incomplete


if __name__ == "__main__":
    mcp.run(transport="stdio")
