# Copyright (c) 2026 John Carter. All rights reserved.
"""
OAuth 2.1 Authorization Server endpoints for Hive.

Endpoints (mounted at /oauth in FastAPI):
  GET  /oauth/authorize   — show consent / redirect with code
  POST /oauth/token       — exchange code or refresh token for tokens
  POST /oauth/revoke      — revoke a token
  GET  /oauth/jwks        — public key set (HS256 → symmetric, for info only)
  GET  /.well-known/oauth-authorization-server  — discovery document
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from hive.auth.dcr import register_client
from hive.auth.tokens import ISSUER, issue_jwt
from hive.metrics import emit_metric
from hive.models import (
    ActivityEvent,
    ClientRegistrationRequest,
    EventType,
    TokenResponse,
    User,
)
from hive.storage import AuthCodeAlreadyUsed, HiveStorage

# When set (non-prod environments only), /oauth/authorize issues auth codes
# directly without redirecting to Google.  This keeps e2e tests functional
# without needing a real Google account in the test environment.
_BYPASS_GOOGLE_AUTH = bool(os.environ.get("HIVE_BYPASS_GOOGLE_AUTH"))

router = APIRouter(tags=["oauth"])


# ---------------------------------------------------------------------------
# Dependency: shared storage instance
# ---------------------------------------------------------------------------


def get_storage() -> HiveStorage:  # noqa: D401
    return HiveStorage()


# ---------------------------------------------------------------------------
# Discovery document
# ---------------------------------------------------------------------------


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_metadata(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "issuer": ISSUER,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "revocation_endpoint": f"{base}/oauth/revoke",
            "registration_endpoint": f"{base}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": [
                "none",
                "client_secret_post",
                "client_secret_basic",
            ],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["memories:read", "memories:write"],
        }
    )


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def protected_resource_metadata() -> JSONResponse:
    """RFC 9728 protected resource metadata.

    Tells OAuth clients (e.g. Claude Desktop) which authorization server
    issues valid tokens for the Hive MCP server.  CloudFront routes
    /.well-known/* to this API Lambda, so the document must live here rather
    than on the MCP Lambda.
    """
    return JSONResponse(
        {
            "resource": f"{ISSUER}/mcp",
            "authorization_servers": [ISSUER],
            "scopes_supported": ["memories:read", "memories:write"],
            "bearer_methods_supported": ["header"],
        }
    )


# ---------------------------------------------------------------------------
# Dynamic Client Registration
# ---------------------------------------------------------------------------


@router.post(
    "/oauth/register",
    status_code=201,
    responses={400: {"description": "Invalid client registration request"}},
)
async def register(
    req: ClientRegistrationRequest,
    storage: Annotated[HiveStorage, Depends(get_storage)],
) -> JSONResponse:
    try:
        resp = register_client(req, storage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage.log_event(
        ActivityEvent(
            event_type=EventType.client_registered,
            client_id=resp.client_id,
            metadata={"client_name": resp.client_name},
        )
    )
    return JSONResponse(resp.model_dump(), status_code=201)


# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------


def _bypass_associate_user(storage: HiveStorage, client_id: str, email: str) -> None:
    """Upsert a test user and associate the DCR client with them.

    Only called in HIVE_BYPASS_GOOGLE_AUTH mode when test_email is supplied to
    /oauth/authorize.  This mirrors the production Google-callback path so that
    user-scoped MCP tools (list_memories, summarize_context) work in e2e tests.
    """
    from hive.auth.google import is_admin_email

    now = datetime.now(timezone.utc)
    display_name = email.split("@")[0]
    role = "admin" if is_admin_email(email) else "user"

    user = storage.get_user_by_email(email)
    if user is None:
        user = User(email=email, display_name=display_name, role=role, created_at=now)
    else:
        user.display_name = display_name
        user.role = role
    user.last_login_at = now
    storage.put_user(user)

    client = storage.get_client(client_id)
    if client is not None and client.owner_user_id is None:
        client.owner_user_id = user.user_id
        storage.put_client(client)


@router.get("/oauth/authorize", responses={400: {"description": "Invalid authorization request"}})
async def authorize(
    request: Request,
    storage: Annotated[HiveStorage, Depends(get_storage)],
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str = "",
    scope: str = "memories:read memories:write",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
) -> RedirectResponse:
    # Validate client
    client = storage.get_client(client_id)
    if client is None:
        raise HTTPException(status_code=400, detail="Unknown client_id")
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(status_code=400, detail="redirect_uri not registered")
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code is supported")
    if not code_challenge:
        raise HTTPException(status_code=400, detail="PKCE code_challenge is required")
    if code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Only code_challenge_method=S256 is supported")

    # Restrict requested scope to what the client is authorised for
    client_scopes = set(client.scope.split())
    requested_scopes = set(scope.split())
    effective_scope = " ".join(sorted(client_scopes & requested_scopes))
    if not effective_scope:
        raise HTTPException(
            status_code=400,
            detail="Requested scope has no overlap with client's registered scope",
        )

    # In bypass mode (non-prod / e2e testing), skip Google and issue code directly.
    if _BYPASS_GOOGLE_AUTH:
        from hive.auth.google import is_email_allowed

        # If test_email is provided, upsert the user and associate the client so
        # that user-scoped tools (list_memories, summarize_context) work in e2e.
        test_email = request.query_params.get("test_email", "").strip()
        if test_email:
            if not is_email_allowed(test_email):
                raise HTTPException(status_code=403, detail="test_email is not allowed")
            _bypass_associate_user(storage, client_id, test_email)
        auth_code = storage.create_auth_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=effective_scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        params: dict[str, str] = {"code": auth_code.code}
        if state:
            params["state"] = state
        return RedirectResponse(  # NOSONAR — redirect_uri validated above (line 126)
            f"{redirect_uri}?{urlencode(params)}", status_code=302
        )

    # Production: store PKCE state, then redirect to Google for identity verification.
    from hive.auth.google import google_authorization_url

    pending = storage.create_pending_auth(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=effective_scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        original_state=state,
    )
    google_callback_uri = f"{ISSUER}/oauth/google/callback"
    return RedirectResponse(
        google_authorization_url(pending.state, google_callback_uri), status_code=302
    )


# ---------------------------------------------------------------------------
# Google OAuth callback
# ---------------------------------------------------------------------------


@router.get(
    "/oauth/google/callback",
    responses={
        400: {"description": "Invalid or expired Google OAuth callback"},
        403: {"description": "Email not authorised"},
    },
)
async def google_callback(
    storage: Annotated[HiveStorage, Depends(get_storage)],
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Handle the redirect from Google after user authentication."""
    from hive.auth.google import exchange_google_code, is_email_allowed, verify_google_id_token

    if error:
        raise HTTPException(status_code=400, detail=f"Google auth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    pending = storage.get_pending_auth(state)
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if datetime.now(timezone.utc) > pending.expires_at:
        storage.delete_pending_auth(state)
        raise HTTPException(status_code=400, detail="State has expired — please try again")

    # Consume the pending auth (single use)
    storage.delete_pending_auth(state)

    google_callback_uri = f"{ISSUER}/oauth/google/callback"

    try:
        id_token = await exchange_google_code(code, google_callback_uri)
        claims = await verify_google_id_token(id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Google token verification failed: {exc}"
        ) from exc

    email = claims.get("email", "")
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google account email not verified")
    if not is_email_allowed(email):
        raise HTTPException(status_code=403, detail=f"Email {email!r} is not authorised")

    auth_code = storage.create_auth_code(
        client_id=pending.client_id,
        redirect_uri=pending.redirect_uri,
        scope=pending.scope,
        code_challenge=pending.code_challenge,
        code_challenge_method=pending.code_challenge_method,
    )

    storage.log_event(
        ActivityEvent(
            event_type=EventType.token_issued,
            client_id=pending.client_id,
            metadata={"email": email, "via": "google_oauth"},
        )
    )

    params: dict[str, str] = {"code": auth_code.code}
    if pending.original_state:
        params["state"] = pending.original_state
    return RedirectResponse(
        f"{pending.redirect_uri}?{urlencode(params)}", status_code=302
    )  # NOSONAR — redirect_uri validated at authorize


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------


def _verify_pkce(code_verifier: str, stored_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(computed, stored_challenge)


@router.post(
    "/oauth/token",
    responses={
        400: {"description": "Invalid grant request"},
        401: {"description": "Invalid client credentials"},
    },
)
async def token(  # NOSONAR — complexity inherent in OAuth grant type dispatch
    storage: Annotated[HiveStorage, Depends(get_storage)],
    grant_type: Annotated[str, Form(...)],
    code: Annotated[str | None, Form()] = None,
    redirect_uri: Annotated[str | None, Form()] = None,
    client_id: Annotated[str | None, Form()] = None,
    client_secret: Annotated[str | None, Form()] = None,
    code_verifier: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    request: Request = None,  # type: ignore[assignment]  # FastAPI injects this; None satisfies Python's default-after-default rule
) -> JSONResponse:
    # --- Client authentication ---
    # Try HTTP Basic first, then form params
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            basic_client_id, basic_secret = decoded.split(":", 1)
            client_id = client_id or basic_client_id
            client_secret = client_secret or basic_secret
        except Exception as exc:
            await emit_metric("TokenValidationFailures")
            raise HTTPException(status_code=401, detail="Invalid Basic auth header") from exc

    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    client = storage.get_client(client_id)
    if client is None:
        await emit_metric("TokenValidationFailures")
        raise HTTPException(status_code=401, detail="Unknown client")

    # Confidential clients must present their secret
    if client.client_secret and not secrets.compare_digest(
        client.client_secret, client_secret or ""
    ):
        await emit_metric("TokenValidationFailures")
        raise HTTPException(status_code=401, detail="Invalid client_secret")

    # --- Grant type dispatch ---
    if grant_type == "authorization_code":
        if not code or not code_verifier or not redirect_uri:
            raise HTTPException(
                status_code=400, detail="code, code_verifier and redirect_uri are required"
            )

        auth_code = storage.get_auth_code(code)
        # Missing / pre-observed-used codes still fail fast without
        # hitting the conditional write — the atomic path below is the
        # fix for the concurrent-redemption TOCTOU only.
        if auth_code is None or auth_code.used:
            raise HTTPException(status_code=400, detail="Invalid or already-used code")
        if auth_code.client_id != client_id:
            raise HTTPException(status_code=400, detail="code was not issued to this client")
        if auth_code.redirect_uri != redirect_uri:
            raise HTTPException(status_code=400, detail="redirect_uri mismatch")
        if datetime.now(timezone.utc) > auth_code.expires_at:
            raise HTTPException(status_code=400, detail="Authorization code has expired")
        if not _verify_pkce(code_verifier, auth_code.code_challenge):
            raise HTTPException(status_code=400, detail="PKCE verification failed")

        # `mark_auth_code_used` is the commit point. If a concurrent
        # redemption of the same code raced ahead of us, the
        # conditional write fails with `AuthCodeAlreadyUsed` and we
        # return the same 400 as the pre-check — RFC 6749 §10.5
        # requires the losing redeemer gets no token pair.
        try:
            storage.mark_auth_code_used(code)
        except AuthCodeAlreadyUsed as exc:
            raise HTTPException(status_code=400, detail="Invalid or already-used code") from exc
        access, refresh = storage.create_token_pair(client_id, auth_code.scope)

    elif grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token is required")

        # Refresh tokens are opaque JTIs stored in DynamoDB
        from jose import JWTError

        from hive.auth.tokens import decode_jwt

        try:
            claims = decode_jwt(refresh_token)
        except JWTError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid refresh_token: {exc}") from exc

        jti = claims.get("jti")
        stored = storage.get_token(jti) if jti else None
        if stored is None or not stored.is_valid or stored.token_type.value != "refresh":
            raise HTTPException(status_code=400, detail="Invalid or expired refresh_token")
        if stored.client_id != client_id:
            raise HTTPException(status_code=400, detail="refresh_token not issued to this client")

        # Rotate: revoke old refresh token, issue new pair
        # Re-intersect scope in case client's registered scope was narrowed since issuance
        effective_scope = (
            " ".join(sorted(set(stored.scope.split()) & set(client.scope.split()))) or stored.scope
        )
        assert jti is not None
        storage.revoke_token(jti)
        access, refresh = storage.create_token_pair(client_id, effective_scope)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")

    from hive.storage import ACCESS_TOKEN_TTL_SECONDS

    storage.log_event(
        ActivityEvent(
            event_type=EventType.token_issued,
            client_id=client_id,
            metadata={"grant_type": grant_type},
        )
    )
    await emit_metric("TokensIssued", grant_type=grant_type)

    return JSONResponse(
        TokenResponse(
            access_token=issue_jwt(access),
            refresh_token=issue_jwt(refresh),
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            scope=access.scope,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# Token revocation endpoint (RFC 7009)
# ---------------------------------------------------------------------------


@router.post("/oauth/revoke")
async def revoke(
    storage: Annotated[HiveStorage, Depends(get_storage)],
    token: Annotated[str, Form(...)],
) -> Response:
    from jose import JWTError

    from hive.auth.tokens import decode_jwt

    try:
        claims = decode_jwt(token)
        jti = claims.get("jti")
        if jti:
            storage.revoke_token(jti)
            stored = storage.get_token(jti)
            if stored:
                storage.log_event(
                    ActivityEvent(
                        event_type=EventType.token_revoked,
                        client_id=stored.client_id,
                        metadata={"jti": jti},
                    )
                )
    except JWTError:
        pass  # Per RFC 7009: always return 200 even for invalid tokens

    return Response(status_code=200)
