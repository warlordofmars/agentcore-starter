# Copyright (c) 2026 John Carter. All rights reserved.
"""
OAuth 2.1 Authorization Server discovery endpoints.

Stateless well-known documents required by the OAuth 2.1 spec and MCP clients.
Add authorization, token, and revocation endpoints here once you have a
persistence layer (DynamoDB, RDS, etc.) wired up.

Endpoints:
  GET /.well-known/oauth-authorization-server  — RFC 8414 discovery document
  GET /.well-known/oauth-protected-resource    — RFC 9728 protected resource metadata
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from starter.auth.tokens import ISSUER

router = APIRouter(tags=["oauth"])


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_metadata(request: Request) -> JSONResponse:
    """RFC 8414 OAuth 2.0 Authorization Server Metadata."""
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
            "scopes_supported": ["read", "write"],
        }
    )


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def protected_resource_metadata() -> JSONResponse:
    """RFC 9728 OAuth 2.0 Protected Resource Metadata."""
    return JSONResponse(
        {
            "resource": ISSUER,
            "authorization_servers": [ISSUER],
            "scopes_supported": ["read", "write"],
            "bearer_methods_supported": ["header"],
        }
    )
