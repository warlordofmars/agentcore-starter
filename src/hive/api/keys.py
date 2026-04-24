# Copyright (c) 2026 John Carter. All rights reserved.
"""
API key management endpoints.

POST /api/keys           — create a new API key (returns plaintext once)
GET  /api/keys           — list API keys for the current user (metadata only)
DELETE /api/keys/{key_id} — revoke (delete) an API key
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hive.api._auth import require_mgmt_user
from hive.models import ApiKey, ApiKeyCreateResponse, ApiKeyResponse
from hive.storage import HiveStorage

router = APIRouter(tags=["api-keys"])

_KEY_PREFIX = "hive_sk_"
_KEY_RANDOM_BYTES = 32


def _storage() -> HiveStorage:
    return HiveStorage()


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and return (plaintext, sha256_hex_hash)."""
    random_part = secrets.token_urlsafe(_KEY_RANDOM_BYTES)
    plaintext = f"{_KEY_PREFIX}{random_part}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, key_hash


def hash_api_key(plaintext: str) -> str:
    """Return the SHA-256 hex digest of a plaintext API key."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


class CreateApiKeyRequest(BaseModel):
    name: str
    scope: str = "memories:read memories:write"


@router.post(
    "/keys",
    summary="Create an API key",
    description="Generate a new API key. The plaintext key is returned once and never stored.",
    status_code=201,
    responses={
        401: {"description": "Unauthorized"},
    },
)
async def create_api_key(
    body: CreateApiKeyRequest,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> ApiKeyCreateResponse:
    plaintext, key_hash = generate_api_key()
    key = ApiKey(
        owner_user_id=claims["sub"],
        name=body.name,
        key_hash=key_hash,
        scope=body.scope,
    )
    storage.put_api_key(key)
    return ApiKeyCreateResponse(
        key_id=key.key_id,
        owner_user_id=key.owner_user_id,
        name=key.name,
        scope=key.scope,
        created_at=key.created_at,
        expires_at=key.expires_at,
        revoked=key.revoked,
        plaintext_key=plaintext,
    )


@router.get(
    "/keys",
    summary="List API keys",
    description="Return metadata for all API keys belonging to the current user.",
    responses={
        401: {"description": "Unauthorized"},
    },
)
async def list_api_keys(
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> list[ApiKeyResponse]:
    keys = storage.list_api_keys_for_user(claims["sub"])
    return [ApiKeyResponse.from_api_key(k) for k in keys]


@router.delete(
    "/keys/{key_id}",
    summary="Revoke an API key",
    description="Permanently delete an API key by ID.",
    status_code=204,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Not the key owner"},
        404: {"description": "Key not found"},
    },
)
async def delete_api_key(
    key_id: str,
    claims: Annotated[dict[str, Any], Depends(require_mgmt_user)],
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> None:
    key = storage.get_api_key_by_id(key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.owner_user_id != claims["sub"]:
        raise HTTPException(status_code=403, detail="Not the key owner")
    storage.delete_api_key(key_id)
