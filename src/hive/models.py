# Copyright (c) 2026 John Carter. All rights reserved.
"""
Data models for Hive — shared persistent memory MCP server.

DynamoDB single-table design:
  Memory items:  PK=MEMORY#{memory_id}   SK=TAG#{tag}
                 PK=MEMORY#{memory_id}   SK=META          (canonical item)
  OAuth clients: PK=CLIENT#{client_id}   SK=META
  Token items:   PK=TOKEN#{jti}          SK=META          (TTL enabled)
  Activity log:  PK=LOG#{date}#{hour}     SK={timestamp}#{event_id}  (hour sharding)
  User items:    PK=USER#{user_id}        SK=META
  Mgmt state:    PK=MGMT_STATE#{state}    SK=META          (TTL enabled)
  API key items: PK=APIKEY#{key_id}       SK=META

GSIs:
  TagIndex:       PK=tag, SK=memory_id    — for list_memories(tag)
  ClientIdIndex:  PK=client_id            — for client lookups by client_id
  UserEmailIndex: PK=EMAIL#{email}        — for user lookups by email
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

_DEFAULT_SCOPE = "memories:read memories:write"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class Memory(BaseModel):
    """A stored memory entry."""

    memory_id: str = Field(default_factory=_new_id)
    key: str
    value: str | None = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    owner_client_id: str  # which OAuth client owns this memory
    owner_user_id: str | None = None  # which user owns this memory (None for pre-migration items)
    expires_at: datetime | None = None  # optional TTL; None means never expires
    recall_count: int = 0  # incremented on every successful recall
    last_accessed_at: datetime | None = None  # set on every successful recall
    redacted_at: datetime | None = None  # when redact_memory tombstoned the value (#400)
    # Large-memory foundation (#497). "text" remains the default and
    # keeps the inline-value path unchanged. "text-large" offloads
    # oversized text to S3 with ``value`` cleared and ``s3_uri`` set.
    # "image" / "blob" are reserved for the binary remember_blob
    # path that lands in #499.
    value_type: Literal["text", "text-large", "image", "blob"] = "text"
    s3_uri: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None

    # ------------------------------------------------------------------
    # DynamoDB serialisation
    # ------------------------------------------------------------------

    def to_dynamo_meta(self) -> dict[str, Any]:
        """Canonical META item (PK=MEMORY#{id}, SK=META)."""
        item: dict[str, Any] = {
            "PK": f"MEMORY#{self.memory_id}",
            "SK": "META",
            "memory_id": self.memory_id,
            "key": self.key,
            # Inline ``value`` stores text up to the 100 KB threshold.
            # For "text-large"/"image"/"blob" the body lives in S3 and
            # we persist an empty string so legacy readers that expect
            # a str keep working. Authoritative content pointer is
            # ``s3_uri``.
            "value": self.value if self.value is not None else "",
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner_client_id": self.owner_client_id,
            "recall_count": self.recall_count,
            # GSI: look up by key across all memories
            "GSI1PK": f"KEY#{self.key}",
            "GSI1SK": self.memory_id,
        }
        if self.owner_user_id is not None:
            item["owner_user_id"] = self.owner_user_id
        if self.expires_at is not None:
            item["expires_at"] = self.expires_at.isoformat()
            item["ttl"] = int(self.expires_at.timestamp())
        if self.last_accessed_at is not None:
            item["last_accessed_at"] = self.last_accessed_at.isoformat()
        if self.redacted_at is not None:
            item["redacted_at"] = self.redacted_at.isoformat()
        # Only serialise non-default large-memory fields so legacy
        # items (all "text", all inline) round-trip byte-identical.
        if self.value_type != "text":
            item["value_type"] = self.value_type
        if self.s3_uri is not None:
            item["s3_uri"] = self.s3_uri
        if self.content_type is not None:
            item["content_type"] = self.content_type
        if self.size_bytes is not None:
            item["size_bytes"] = self.size_bytes
        return item

    def to_dynamo_tag_items(self) -> list[dict[str, Any]]:
        """One TAG item per tag for the TagIndex GSI."""
        items = []
        for tag in self.tags:
            items.append(
                {
                    "PK": f"MEMORY#{self.memory_id}",
                    "SK": f"TAG#{tag}",
                    "memory_id": self.memory_id,
                    "key": self.key,
                    "owner_client_id": self.owner_client_id,
                    # GSI: query by tag
                    "GSI2PK": f"TAG#{tag}",
                    "GSI2SK": self.memory_id,
                }
            )
        return items

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> Memory:
        expires_at = None
        if ea := item.get("expires_at"):
            expires_at = datetime.fromisoformat(ea)
        last_accessed_at = None
        if la := item.get("last_accessed_at"):
            last_accessed_at = datetime.fromisoformat(la)
        redacted_at = None
        if ra := item.get("redacted_at"):
            redacted_at = datetime.fromisoformat(ra)
        # Legacy items predate #497 — default value_type to "text"
        # so the unchanged inline-value path keeps working.
        return cls(
            memory_id=item["memory_id"],
            key=item["key"],
            value=item["value"],
            tags=item.get("tags", []),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            owner_client_id=item["owner_client_id"],
            owner_user_id=item.get("owner_user_id"),
            expires_at=expires_at,
            recall_count=int(item.get("recall_count", 0) or 0),
            last_accessed_at=last_accessed_at,
            redacted_at=redacted_at,
            value_type=item.get("value_type", "text"),
            s3_uri=item.get("s3_uri"),
            content_type=item.get("content_type"),
            size_bytes=int(item["size_bytes"]) if item.get("size_bytes") is not None else None,
        )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and _now_utc() >= self.expires_at

    @property
    def is_redacted(self) -> bool:
        """True when ``redact_memory`` has tombstoned this memory (#400)."""
        return self.redacted_at is not None

    @property
    def version(self) -> str:
        """Opaque version token for optimistic locking (#391).

        Derived from ``updated_at`` so every write produces a fresh value.
        Agents pass this back to ``remember(key, ..., version=...)`` to
        detect concurrent-write conflicts.
        """
        return self.updated_at.isoformat()


# ---------------------------------------------------------------------------
# OAuth Client (RFC 7591 Dynamic Client Registration)
# ---------------------------------------------------------------------------


class OAuthClientType(str, Enum):
    confidential = "confidential"
    public = "public"


class OAuthClient(BaseModel):
    """An OAuth 2.1 registered client."""

    client_id: str = Field(default_factory=_new_id)
    client_secret: str | None = None  # None for public clients
    client_name: str
    client_type: OAuthClientType = OAuthClientType.public
    redirect_uris: list[str] = Field(default_factory=list)
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code"])
    response_types: list[str] = Field(default_factory=lambda: ["code"])
    scope: str = _DEFAULT_SCOPE
    token_endpoint_auth_method: str = (
        "none"  # public clients: none; confidential: client_secret_post
    )
    created_at: datetime = Field(default_factory=_now_utc)
    owner_user_id: str | None = (
        None  # which user registered this client (None for pre-migration items)
    )

    # ------------------------------------------------------------------
    # DynamoDB serialisation
    # ------------------------------------------------------------------

    def to_dynamo(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": f"CLIENT#{self.client_id}",
            "SK": "META",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "client_name": self.client_name,
            "client_type": self.client_type.value,
            "redirect_uris": self.redirect_uris,
            "grant_types": self.grant_types,
            "response_types": self.response_types,
            "scope": self.scope,
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
            "created_at": self.created_at.isoformat(),
            # GSI: look up client by client_id (partition key already unique,
            # but GSI allows cross-entity queries if needed)
            "GSI3PK": f"CLIENT#{self.client_id}",
        }
        if self.owner_user_id is not None:
            item["owner_user_id"] = self.owner_user_id
        return item

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> OAuthClient:
        return cls(
            client_id=item["client_id"],
            client_secret=item.get("client_secret"),
            client_name=item["client_name"],
            client_type=OAuthClientType(item["client_type"]),
            redirect_uris=item.get("redirect_uris", []),
            grant_types=item.get("grant_types", ["authorization_code"]),
            response_types=item.get("response_types", ["code"]),
            scope=item.get("scope", _DEFAULT_SCOPE),
            token_endpoint_auth_method=item.get("token_endpoint_auth_method", "none"),
            created_at=datetime.fromisoformat(item["created_at"]),
            owner_user_id=item.get("owner_user_id"),
        )


# ---------------------------------------------------------------------------
# Pending Auth (stores PKCE state while user authenticates with Google)
# ---------------------------------------------------------------------------


class PendingAuth(BaseModel):
    """Temporary record that holds PKCE state while the user authenticates with Google."""

    state: str = Field(default_factory=_new_id)  # random nonce, used as DynamoDB key
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str
    code_challenge_method: str = "S256"
    original_state: str = ""  # the `state` param from the original /oauth/authorize request
    expires_at: datetime

    def to_dynamo(self) -> dict[str, Any]:
        return {
            "PK": f"PENDING#{self.state}",
            "SK": "META",
            "state": self.state,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "code_challenge": self.code_challenge,
            "code_challenge_method": self.code_challenge_method,
            "original_state": self.original_state,
            "expires_at": self.expires_at.isoformat(),
            "ttl": int(self.expires_at.timestamp()),
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> PendingAuth:
        return cls(
            state=item["state"],
            client_id=item["client_id"],
            redirect_uri=item["redirect_uri"],
            scope=item["scope"],
            code_challenge=item["code_challenge"],
            code_challenge_method=item.get("code_challenge_method", "S256"),
            original_state=item.get("original_state", ""),
            expires_at=datetime.fromisoformat(item["expires_at"]),
        )


# ---------------------------------------------------------------------------
# User (management UI identity)
# ---------------------------------------------------------------------------


class User(BaseModel):
    """A human user of the management UI, authenticated via Google OAuth."""

    user_id: str = Field(default_factory=_new_id)
    email: str
    display_name: str
    role: str = "user"  # "admin" or "user"
    created_at: datetime = Field(default_factory=_now_utc)
    last_login_at: datetime = Field(default_factory=_now_utc)
    # Per-user quota overrides set by admins; None = use system default.
    memory_limit: int | None = None
    storage_bytes_limit: int | None = None

    def to_dynamo(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": f"USER#{self.user_id}",
            "SK": "META",
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat(),
            # GSI: look up user by email
            "GSI4PK": f"EMAIL#{self.email}",
        }
        if self.memory_limit is not None:
            item["memory_limit"] = self.memory_limit
        if self.storage_bytes_limit is not None:
            item["storage_bytes_limit"] = self.storage_bytes_limit
        return item

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> User:
        return cls(
            user_id=item["user_id"],
            email=item["email"],
            display_name=item["display_name"],
            role=item.get("role", "user"),
            created_at=datetime.fromisoformat(item["created_at"]),
            last_login_at=datetime.fromisoformat(item["last_login_at"]),
            memory_limit=item.get("memory_limit"),
            storage_bytes_limit=item.get("storage_bytes_limit"),
        )


# ---------------------------------------------------------------------------
# MgmtPendingState (nonce stored during management UI Google login)
# ---------------------------------------------------------------------------


class MgmtPendingState(BaseModel):
    """Temporary nonce stored while the management UI user authenticates with Google."""

    state: str = Field(default_factory=_new_id)
    expires_at: datetime

    def to_dynamo(self) -> dict[str, Any]:
        return {
            "PK": f"MGMT_STATE#{self.state}",
            "SK": "META",
            "state": self.state,
            "expires_at": self.expires_at.isoformat(),
            "ttl": int(self.expires_at.timestamp()),
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> MgmtPendingState:
        return cls(
            state=item["state"],
            expires_at=datetime.fromisoformat(item["expires_at"]),
        )


# ---------------------------------------------------------------------------
# OAuth Authorization Code (PKCE)
# ---------------------------------------------------------------------------


class AuthorizationCode(BaseModel):
    """Short-lived authorization code created during OAuth flow."""

    code: str = Field(default_factory=_new_id)
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str  # S256 PKCE challenge
    code_challenge_method: str = "S256"
    expires_at: datetime
    used: bool = False

    def to_dynamo(self) -> dict[str, Any]:
        return {
            "PK": f"AUTHCODE#{self.code}",
            "SK": "META",
            "code": self.code,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "code_challenge": self.code_challenge,
            "code_challenge_method": self.code_challenge_method,
            "expires_at": self.expires_at.isoformat(),
            "used": self.used,
            # TTL: DynamoDB will auto-expire these
            "ttl": int(self.expires_at.timestamp()),
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> AuthorizationCode:
        return cls(
            code=item["code"],
            client_id=item["client_id"],
            redirect_uri=item["redirect_uri"],
            scope=item["scope"],
            code_challenge=item["code_challenge"],
            code_challenge_method=item.get("code_challenge_method", "S256"),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            used=item.get("used", False),
        )


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


class TokenType(str, Enum):
    access = "access"
    refresh = "refresh"


class Token(BaseModel):
    """An issued OAuth token."""

    jti: str = Field(default_factory=_new_id)  # JWT ID / opaque token ID
    token_type: TokenType = TokenType.access
    client_id: str
    scope: str
    issued_at: datetime = Field(default_factory=_now_utc)
    expires_at: datetime
    revoked: bool = False

    def to_dynamo(self) -> dict[str, Any]:
        return {
            "PK": f"TOKEN#{self.jti}",
            "SK": "META",
            "jti": self.jti,
            "token_type": self.token_type.value,
            "client_id": self.client_id,
            "scope": self.scope,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "revoked": self.revoked,
            # DynamoDB TTL attribute
            "ttl": int(self.expires_at.timestamp()),
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> Token:
        return cls(
            jti=item["jti"],
            token_type=TokenType(item["token_type"]),
            client_id=item["client_id"],
            scope=item["scope"],
            issued_at=datetime.fromisoformat(item["issued_at"]),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            revoked=item.get("revoked", False),
        )

    @property
    def is_expired(self) -> bool:
        return _now_utc() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired


# ---------------------------------------------------------------------------
# Activity Log
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    memory_created = "memory_created"
    memory_updated = "memory_updated"
    memory_deleted = "memory_deleted"
    memory_redacted = "memory_redacted"
    memory_recalled = "memory_recalled"
    memory_listed = "memory_listed"
    memory_searched = "memory_searched"
    context_summarized = "context_summarized"
    token_issued = "token_issued"
    token_revoked = "token_revoked"
    client_registered = "client_registered"
    client_deleted = "client_deleted"
    account_deleted = "account_deleted"


class ActivityEvent(BaseModel):
    """An activity log entry."""

    event_id: str = Field(default_factory=_new_id)
    event_type: EventType
    client_id: str
    timestamp: datetime = Field(default_factory=_now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dynamo(self) -> dict[str, Any]:
        # Hour-sharded PK: spreads writes across 24 partitions per day,
        # avoiding DynamoDB hot-partition throttling under heavy write load.
        date_hour_str = self.timestamp.strftime("%Y-%m-%d#%H")
        ts_str = self.timestamp.isoformat()
        return {
            "PK": f"LOG#{date_hour_str}",
            "SK": f"{ts_str}#{self.event_id}",
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "client_id": self.client_id,
            "timestamp": ts_str,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> ActivityEvent:
        return cls(
            event_id=item["event_id"],
            event_type=EventType(item["event_type"]),
            client_id=item["client_id"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            metadata=item.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Memory version (snapshot of a memory value before overwrite)
# ---------------------------------------------------------------------------


class MemoryVersion(BaseModel):
    """A point-in-time snapshot of a memory, written before an overwrite."""

    memory_id: str
    version_timestamp: str  # ISO-formatted UTC timestamp used as SK
    key: str
    value: str
    tags: list[str]
    recorded_at: datetime

    def to_dynamo(self) -> dict[str, Any]:
        return {
            "PK": f"MEMORY#{self.memory_id}",
            "SK": f"VERSION#{self.version_timestamp}",
            "memory_id": self.memory_id,
            "version_timestamp": self.version_timestamp,
            "key": self.key,
            "value": self.value,
            "tags": self.tags,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> MemoryVersion:
        return cls(
            memory_id=item["memory_id"],
            version_timestamp=item["version_timestamp"],
            key=item["key"],
            value=item["value"],
            tags=item.get("tags", []),
            recorded_at=datetime.fromisoformat(item["recorded_at"]),
        )

    @classmethod
    def from_memory(cls, memory: Memory) -> MemoryVersion:
        """Snapshot the current state of a memory."""
        now = _now_utc()
        return cls(
            memory_id=memory.memory_id,
            version_timestamp=now.strftime("%Y%m%dT%H%M%S%f"),
            key=memory.key,
            value=memory.value,
            tags=memory.tags,
            recorded_at=now,
        )


# ---------------------------------------------------------------------------
# API request / response schemas (used by FastAPI routes)
# ---------------------------------------------------------------------------


class MemoryCreate(BaseModel):
    key: str
    value: str
    tags: list[str] = Field(default_factory=list)
    ttl_seconds: int | None = Field(
        default=None, ge=1, description="Seconds until expiry. None = never expires."
    )


class MemoryUpdate(BaseModel):
    value: str | None = None
    tags: list[str] | None = None
    ttl_seconds: int | None = Field(
        default=None, ge=0, description="Seconds until expiry. 0 = clear TTL. None = no change."
    )


class MemoryResponse(BaseModel):
    memory_id: str
    key: str
    value: str
    value_type: Literal["text", "text-large", "image", "blob"] = "text"
    content_type: str | None = None
    size_bytes: int | None = None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    recall_count: int = 0
    last_accessed_at: datetime | None = None

    @classmethod
    def from_memory(cls, m: Memory) -> MemoryResponse:
        return cls(
            memory_id=m.memory_id,
            key=m.key,
            value=m.value or "",
            value_type=m.value_type,
            content_type=m.content_type,
            size_bytes=m.size_bytes,
            tags=m.tags,
            created_at=m.created_at,
            updated_at=m.updated_at,
            expires_at=m.expires_at,
            recall_count=m.recall_count,
            last_accessed_at=m.last_accessed_at,
        )


class MemoryVersionResponse(BaseModel):
    memory_id: str
    version_timestamp: str
    key: str
    value: str
    tags: list[str]
    recorded_at: datetime

    @classmethod
    def from_version(cls, v: MemoryVersion) -> MemoryVersionResponse:
        return cls(
            memory_id=v.memory_id,
            version_timestamp=v.version_timestamp,
            key=v.key,
            value=v.value,
            tags=v.tags,
            recorded_at=v.recorded_at,
        )


class ClientRegistrationRequest(BaseModel):
    """RFC 7591 dynamic client registration request."""

    client_name: str
    redirect_uris: list[str] = Field(default_factory=list)
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code"])
    response_types: list[str] = Field(default_factory=lambda: ["code"])
    scope: str = _DEFAULT_SCOPE
    token_endpoint_auth_method: str = "none"


class ClientRegistrationResponse(BaseModel):
    """RFC 7591 dynamic client registration response.

    ``client_secret`` is omitted entirely for public clients (RFC 7591 §3.2.1)
    rather than serialised as ``null``, which breaks strict Zod schemas in
    clients such as mcp-remote.
    """

    client_id: str
    client_secret: str | None = None
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    scope: str
    token_endpoint_auth_method: str
    client_id_issued_at: int  # Unix timestamp

    @model_serializer(mode="wrap")
    def _drop_null_secret(self, handler: Any) -> dict:  # type: ignore[override]
        data = handler(self)
        if data.get("client_secret") is None:
            data.pop("client_secret", None)
        return data

    @classmethod
    def from_client(cls, c: OAuthClient) -> ClientRegistrationResponse:
        return cls(
            client_id=c.client_id,
            client_secret=c.client_secret,
            client_name=c.client_name,
            redirect_uris=c.redirect_uris,
            grant_types=c.grant_types,
            response_types=c.response_types,
            scope=c.scope,
            token_endpoint_auth_method=c.token_endpoint_auth_method,
            client_id_issued_at=int(c.created_at.timestamp()),
        )


class TokenResponse(BaseModel):
    """OAuth 2.1 token endpoint response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str


class StatsResponse(BaseModel):
    total_memories: int
    total_clients: int
    total_users: int | None = None  # admin only
    events_today: int
    events_last_7_days: int
    memory_limit: int | None = None  # None = unlimited (admin or exempt)
    client_limit: int | None = None  # None = unlimited (admin or exempt)
    total_storage_bytes: int = 0
    storage_bytes_limit: int | None = None  # None = unlimited (admin or exempt)


class PagedResponse(BaseModel):
    """Generic paginated response envelope."""

    items: list
    count: int
    has_more: bool
    next_cursor: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    created_at: datetime
    last_login_at: datetime

    @classmethod
    def from_user(cls, u: User) -> UserResponse:
        return cls(
            user_id=u.user_id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )


# ---------------------------------------------------------------------------
# API Keys (long-lived auth alternative to OAuth)
# ---------------------------------------------------------------------------


class ApiKey(BaseModel):
    """A long-lived API key for server-to-server authentication."""

    key_id: str = Field(default_factory=_new_id)
    owner_user_id: str
    name: str
    key_hash: str  # SHA-256 hex digest — never store plaintext
    scope: str = "memories:read memories:write"
    created_at: datetime = Field(default_factory=_now_utc)
    expires_at: datetime | None = None
    revoked: bool = False

    def to_dynamo(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": f"APIKEY#{self.key_id}",
            "SK": "META",
            "key_id": self.key_id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "key_hash": self.key_hash,
            "scope": self.scope,
            "created_at": self.created_at.isoformat(),
            "revoked": self.revoked,
        }
        if self.expires_at is not None:
            item["expires_at"] = self.expires_at.isoformat()
            item["ttl"] = int(self.expires_at.timestamp())
        return item

    @classmethod
    def from_dynamo(cls, item: dict[str, Any]) -> ApiKey:
        expires_at = None
        if ea := item.get("expires_at"):
            expires_at = datetime.fromisoformat(ea)
        return cls(
            key_id=item["key_id"],
            owner_user_id=item["owner_user_id"],
            name=item["name"],
            key_hash=item["key_hash"],
            scope=item.get("scope", "memories:read memories:write"),
            created_at=datetime.fromisoformat(item["created_at"]),
            expires_at=expires_at,
            revoked=item.get("revoked", False),
        )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and _now_utc() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired


class ApiKeyResponse(BaseModel):
    """Public metadata for an API key — never includes the plaintext key or hash."""

    key_id: str
    owner_user_id: str
    name: str
    scope: str
    created_at: datetime
    expires_at: datetime | None = None
    revoked: bool

    @classmethod
    def from_api_key(cls, k: ApiKey) -> ApiKeyResponse:
        return cls(
            key_id=k.key_id,
            owner_user_id=k.owner_user_id,
            name=k.name,
            scope=k.scope,
            created_at=k.created_at,
            expires_at=k.expires_at,
            revoked=k.revoked,
        )


class ApiKeyCreateResponse(ApiKeyResponse):
    """Returned only on key creation — includes the plaintext key (shown once)."""

    plaintext_key: str


class MemorySearchResult(BaseModel):
    """A memory returned by search, with its blended relevance score.

    ``score`` is the final blended value on [0, 1]. The per-signal sub-scores
    (``semantic_score`` / ``keyword_score`` / ``recency_score``) are included
    for debugging and agent-side re-ranking when hybrid mode is on (#481).
    """

    memory_id: str
    key: str
    value: str
    tags: list[str]
    owner_client_id: str | None
    score: float  # blended score (0.0–1.0); higher = more relevant
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    recency_score: float = 0.0
    created_at: datetime
    updated_at: datetime
    recall_count: int = 0
    last_accessed_at: datetime | None = None

    @classmethod
    def from_memory_and_score(
        cls,
        m: Memory,
        score: float,
        *,
        semantic_score: float = 0.0,
        keyword_score: float = 0.0,
        recency_score: float = 0.0,
    ) -> MemorySearchResult:
        return cls(
            memory_id=m.memory_id,
            key=m.key,
            value=m.value,
            tags=m.tags,
            owner_client_id=m.owner_client_id,
            score=score,
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            recency_score=recency_score,
            created_at=m.created_at,
            updated_at=m.updated_at,
            recall_count=m.recall_count,
            last_accessed_at=m.last_accessed_at,
        )
