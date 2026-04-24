# Copyright (c) 2026 John Carter. All rights reserved.
"""
Dynamic Client Registration (RFC 7591) for Hive OAuth 2.1.

POST /oauth/register  — register a new client (no auth required per spec)
"""

from __future__ import annotations

import secrets

from hive.models import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    OAuthClient,
    OAuthClientType,
)
from hive.storage import HiveStorage

SUPPORTED_GRANT_TYPES = {"authorization_code", "refresh_token"}
SUPPORTED_RESPONSE_TYPES = {"code"}
SUPPORTED_AUTH_METHODS = {"none", "client_secret_post", "client_secret_basic"}
ALLOWED_SCOPES = frozenset({"memories:read", "memories:write", "clients:read", "clients:write"})


def register_client(
    req: ClientRegistrationRequest, storage: HiveStorage
) -> ClientRegistrationResponse:
    """
    Validate a DCR request and persist the new client.

    Raises ValueError for invalid requests.
    """
    # Validate grant types
    unsupported_grants = set(req.grant_types) - SUPPORTED_GRANT_TYPES
    if unsupported_grants:
        raise ValueError(f"Unsupported grant_types: {unsupported_grants}")

    # Validate response types
    unsupported_responses = set(req.response_types) - SUPPORTED_RESPONSE_TYPES
    if unsupported_responses:
        raise ValueError(f"Unsupported response_types: {unsupported_responses}")

    # Validate auth method
    if req.token_endpoint_auth_method not in SUPPORTED_AUTH_METHODS:
        raise ValueError(
            f"Unsupported token_endpoint_auth_method: {req.token_endpoint_auth_method}"
        )

    # Validate requested scopes against the allowed set
    requested_scopes = set(req.scope.split())
    unknown_scopes = requested_scopes - ALLOWED_SCOPES
    if unknown_scopes:
        raise ValueError(f"Unknown scope(s): {unknown_scopes}")

    # Determine client type
    is_confidential = req.token_endpoint_auth_method in {
        "client_secret_post",
        "client_secret_basic",
    }
    client_type = OAuthClientType.confidential if is_confidential else OAuthClientType.public
    client_secret = secrets.token_urlsafe(32) if is_confidential else None

    client = OAuthClient(
        client_name=req.client_name,
        client_type=client_type,
        client_secret=client_secret,
        redirect_uris=req.redirect_uris,
        grant_types=req.grant_types,
        response_types=req.response_types,
        scope=req.scope,
        token_endpoint_auth_method=req.token_endpoint_auth_method,
    )

    storage.put_client(client)
    return ClientRegistrationResponse.from_client(client)
