# Copyright (c) 2026 John Carter. All rights reserved.
"""
DynamoDB storage layer for Hive.

Single-table design — all entities share one table.
Table name is read from the HIVE_TABLE_NAME environment variable.

GSIs:
  TagIndex    — GSI2PK (TAG#{tag}), GSI2SK (memory_id)  → list_memories(tag)
  ClientIndex — GSI3PK (CLIENT#{client_id})              → client lookups
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from hive.logging_config import get_logger
from hive.models import (
    ActivityEvent,
    ApiKey,
    AuthorizationCode,
    Memory,
    MemoryVersion,
    MgmtPendingState,
    OAuthClient,
    PendingAuth,
    Token,
    TokenType,
    User,
)

logger = get_logger("hive.storage")

TABLE_NAME = os.environ.get("HIVE_TABLE_NAME", "hive")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")

# Reusable DynamoDB filter expression fragments
_UID_FILTER = " AND owner_user_id = :uid"
_PK_PREFIX_KEY = ":prefix"
_SK_PK_PREFIX_EXPR = "SK = :sk AND begins_with(PK, :prefix)"

# Version retention
_VERSION_RETENTION_DAYS = int(os.environ.get("HIVE_VERSION_RETENTION_DAYS", "30"))

# Token lifetimes
ACCESS_TOKEN_TTL_SECONDS = 3600  # 1 hour
REFRESH_TOKEN_TTL_SECONDS = 86400 * 30  # 30 days
AUTH_CODE_TTL_SECONDS = 300  # 5 minutes
PENDING_AUTH_TTL_SECONDS = 600  # 10 minutes (enough for Google login flow)
MGMT_PENDING_STATE_TTL_SECONDS = 600  # 10 minutes (enough for Google login flow)


class VersionConflict(Exception):
    """Raised by put_memory when an optimistic-lock version check fails (#391).

    Carries the state the caller needs to compare-and-retry without an
    extra round-trip: the attempted version, the actual current value,
    and the actual current version.
    """

    def __init__(
        self,
        attempted_version: str,
        current_value: str | None,
        current_version: str | None,
    ) -> None:
        self.attempted_version = attempted_version
        self.current_value = current_value
        self.current_version = current_version
        super().__init__(f"Memory was updated since version {attempted_version!r}")


class AuthCodeAlreadyUsed(Exception):
    """Raised by ``mark_auth_code_used`` when the conditional write is rejected.

    Two conditions trip the conditional ``UpdateItem``:

    1. Another redemption raced ahead and flipped ``used`` to ``true``
       (the RFC 6749 §10.5 single-use case this fix exists for).
    2. No AUTHCODE item exists under the supplied key — the
       ``attribute_exists(PK)`` guard rejects forged / never-issued
       codes so callers can't mint tokens from arbitrary strings.

    Both are indistinguishable from the client's perspective: the
    token endpoint maps either to ``400 "Invalid or already-used
    code"``. The name stays narrow because concurrent redemption is
    the motivating case; the forged-code path is a defensive
    side-effect of the same condition.
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_cursor(last_evaluated_key: dict[str, Any]) -> str:
    """Encode a DynamoDB LastEvaluatedKey as an opaque base64 cursor."""
    return base64.urlsafe_b64encode(json.dumps(last_evaluated_key).encode()).decode()


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a base64 cursor back to a DynamoDB ExclusiveStartKey."""
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except Exception as exc:
        raise ValueError(f"Invalid pagination cursor: {cursor!r}") from exc


class HiveStorage:
    """All DynamoDB read/write operations for Hive."""

    def __init__(
        self,
        table_name: str | None = None,
        region: str | None = None,
        blob_store: Any = None,
        **kwargs: Any,
    ) -> None:
        # Read env vars at call time so tests can override them after import
        table_name = table_name or os.environ.get("HIVE_TABLE_NAME", "hive")
        region = region or os.environ.get("AWS_REGION", "us-east-1")
        # Auto-use DYNAMODB_ENDPOINT for local dev / integration tests
        kwargs.setdefault("endpoint_url", os.environ.get("DYNAMODB_ENDPOINT"))
        dynamodb = boto3.resource("dynamodb", region_name=region, **kwargs)
        self.table = dynamodb.Table(table_name)
        # Lazily-instantiated BlobStore — we only need it on the
        # text-large / binary path so tests that never exercise that
        # branch can leave HIVE_BLOBS_BUCKET unset. Inject a mock via
        # the ``blob_store`` kwarg in tests.
        self._blob_store_override = blob_store
        self._blob_store: Any = None

    @property
    def blob_store(self) -> Any:
        """Lazy BlobStore handle — constructed on first use."""
        if self._blob_store_override is not None:
            return self._blob_store_override
        # Import inline to avoid circular-import risk at module load.
        if self._blob_store is None:
            from hive.blob_store import BlobStore

            self._blob_store = BlobStore()
        return self._blob_store

    # ------------------------------------------------------------------
    # Memory CRUD
    # ------------------------------------------------------------------

    def put_memory(self, memory: Memory, *, expected_version: str | None = None) -> None:
        """Write (create or replace) a memory and all its tag items.

        When replacing an existing memory, the previous state is snapshotted
        as a VERSION item so it can be retrieved via list_memory_versions.

        If ``expected_version`` is provided, the META item is written with a
        conditional expression requiring the stored ``updated_at`` to match
        — supporting optimistic locking (#391). Raises ``VersionConflict``
        if the stored version has moved on since the caller read it.

        Large-memory routing (#497): text values over the inline
        threshold are uploaded to S3 and the META item stores only
        ``s3_uri`` + ``size_bytes``. The routing happens in-place on
        the passed ``memory`` so callers always see the persisted
        shape.
        """
        self._route_large_value(memory)
        existing_raw = self._get_memory_meta(memory.memory_id)
        if expected_version is not None:
            if existing_raw is None:
                raise VersionConflict(
                    attempted_version=expected_version,
                    current_value=None,
                    current_version=None,
                )
            current = Memory.from_dynamo(existing_raw)
            if current.version != expected_version:
                raise VersionConflict(
                    attempted_version=expected_version,
                    current_value=current.value,
                    current_version=current.version,
                )

        if existing_raw:
            old = Memory.from_dynamo(existing_raw)
            self._delete_tag_items(old)
            self.save_memory_version(old)

        meta_item = memory.to_dynamo_meta()
        try:
            if expected_version is not None:
                # Conditional put on the META item to close the TOCTOU window
                # between the read above and the write below. Tag items get
                # rewritten unconditionally — they carry no value state and
                # are rebuilt from the memory's tag list on every put.
                self.table.put_item(
                    Item=meta_item,
                    ConditionExpression=Attr("updated_at").eq(expected_version),
                )
                with self.table.batch_writer() as batch:
                    for tag_item in memory.to_dynamo_tag_items():
                        batch.put_item(Item=tag_item)
            else:
                with self.table.batch_writer() as batch:
                    batch.put_item(Item=meta_item)
                    for tag_item in memory.to_dynamo_tag_items():
                        batch.put_item(Item=tag_item)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            msg = exc.response["Error"]["Message"]
            if code == "ConditionalCheckFailedException":
                latest = self._get_memory_meta(memory.memory_id)
                latest_mem = Memory.from_dynamo(latest) if latest else None
                raise VersionConflict(
                    attempted_version=expected_version or "",
                    current_value=latest_mem.value if latest_mem else None,
                    current_version=latest_mem.version if latest_mem else None,
                ) from exc
            if code == "ValidationException" and "size" in msg.lower():
                raise ValueError(
                    "Memory value is too large to store (DynamoDB 400 KB item limit exceeded)."
                ) from exc
            raise

    def _route_large_value(self, memory: Memory) -> None:
        """Offload oversized text to S3, leaving a pointer in DynamoDB.

        Handles both initial writes and updates for text and text-large
        memories. Binary types (image/blob, arriving via #499) are expected
        to already carry an ``s3_uri`` — this router only handles the
        transparent-text path where a caller hands us a string and expects
        the right backend to be chosen automatically.
        """
        from hive.blob_store import INLINE_TEXT_THRESHOLD_BYTES, MAX_BLOB_SIZE_BYTES

        # Binary paths (image, blob) have their own upload lifecycle (#499).
        if memory.value_type not in ("text", "text-large"):
            return

        # A text-large memory fetched from DynamoDB has value="" (blob already
        # in S3). Re-route only when the caller has provided a new value (the
        # remember-update path). An empty value means the existing S3 object
        # is unchanged.
        if memory.value_type == "text-large":
            if not memory.value:
                return
            memory.value_type = "text"

        if memory.value is None:
            return

        encoded = memory.value.encode("utf-8")
        if len(encoded) > MAX_BLOB_SIZE_BYTES:
            raise ValueError(
                f"Value size {len(encoded)} bytes exceeds the maximum of "
                f"{MAX_BLOB_SIZE_BYTES} bytes."
            )
        if len(encoded) <= INLINE_TEXT_THRESHOLD_BYTES:
            # Inline path: unchanged. Capture size_bytes for the
            # forthcoming two-dimension quota (#500) even on the
            # small path so rollups are consistent.
            memory.size_bytes = len(encoded)
            return

        # Promote to text-large — write body to S3 under the
        # workspace-equivalent prefix (user id today, workspace id
        # post-#482).
        owner = memory.owner_user_id or memory.owner_client_id
        s3_uri = self.blob_store.put(
            owner=owner,
            memory_id=memory.memory_id,
            body=encoded,
            content_type="text/plain; charset=utf-8",
        )
        memory.value_type = "text-large"
        memory.s3_uri = s3_uri
        memory.size_bytes = len(encoded)
        memory.content_type = "text/plain; charset=utf-8"
        # Drop the inline value — DynamoDB only keeps the pointer.
        memory.value = ""

    def get_memory_by_id(self, memory_id: str) -> Memory | None:
        item = self._get_memory_meta(memory_id)
        if item is None:
            return None
        memory = Memory.from_dynamo(item)
        if memory.is_expired:
            return None
        return memory

    def get_memory_by_key(self, key: str) -> Memory | None:
        """Look up a memory by its human-readable key using GSI1."""
        resp = self.table.query(
            IndexName="KeyIndex",
            KeyConditionExpression=Key("GSI1PK").eq(f"KEY#{key}"),
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        # GSI items don't carry value; fetch the META item
        memory_id = items[0]["memory_id"]
        return self.get_memory_by_id(memory_id)

    def record_recall(self, key: str) -> Memory | None:
        """Atomically increment ``recall_count`` and refresh ``last_accessed_at``
        on the memory with the given key, returning the updated Memory.

        Returns ``None`` if the key doesn't exist or the memory is expired.
        Does the work in a single DynamoDB ``update_item`` (with ``ALL_NEW``
        return values) so we don't pay two round-trips per recall.
        """
        resp = self.table.query(
            IndexName="KeyIndex",
            KeyConditionExpression=Key("GSI1PK").eq(f"KEY#{key}"),
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        memory_id = items[0]["memory_id"]
        now_iso = _now().isoformat()
        updated = self.table.update_item(
            Key={"PK": f"MEMORY#{memory_id}", "SK": "META"},
            UpdateExpression=("SET last_accessed_at = :now ADD recall_count :one"),
            ExpressionAttributeValues={":now": now_iso, ":one": Decimal("1")},
            ReturnValues="ALL_NEW",
        )
        # ALL_NEW always populates Attributes once the KeyIndex lookup above
        # has confirmed the item exists, so there's no "None" path to guard.
        memory = Memory.from_dynamo(updated["Attributes"])
        if memory.is_expired:
            return None
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory and all its tag items. Returns True if found."""
        existing = self._get_memory_meta(memory_id)
        if existing is None:
            return False
        memory = Memory.from_dynamo(existing)
        self._delete_tag_items(memory)
        self.table.delete_item(Key={"PK": f"MEMORY#{memory_id}", "SK": "META"})
        self._delete_blob_if_needed(memory)
        return True

    # ------------------------------------------------------------------
    # Memory version history
    # ------------------------------------------------------------------

    def save_memory_version(self, memory: Memory) -> MemoryVersion:
        """Snapshot the current state of a memory as a VERSION item."""
        version = MemoryVersion.from_memory(memory)
        item = version.to_dynamo()
        # Set TTL so old versions are auto-pruned
        expires = _now() + timedelta(days=_VERSION_RETENTION_DAYS)
        item["ttl"] = int(expires.timestamp())
        self.table.put_item(Item=item)
        return version

    def list_memory_versions(self, memory_id: str) -> list[MemoryVersion]:
        """Return all version snapshots for a memory, newest first."""
        resp = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"MEMORY#{memory_id}")
            & Key("SK").begins_with("VERSION#"),
            ScanIndexForward=False,
        )
        return [MemoryVersion.from_dynamo(item) for item in resp.get("Items", [])]

    def get_memory_version(self, memory_id: str, version_timestamp: str) -> MemoryVersion | None:
        """Fetch a specific version snapshot."""
        resp = self.table.get_item(
            Key={"PK": f"MEMORY#{memory_id}", "SK": f"VERSION#{version_timestamp}"}
        )
        item = resp.get("Item")
        if item is None:
            return None
        return MemoryVersion.from_dynamo(item)

    def hydrate_memory_ids(
        self, id_score_pairs: list[tuple[str, float]]
    ) -> list[tuple[Memory, float]]:
        """Fetch full Memory objects for a list of (memory_id, score) pairs.

        Pairs whose memory_id no longer exists in DynamoDB (deleted between the
        vector write and this lookup) are silently filtered out.  Result order
        mirrors the input order so relevance ranking is preserved.
        """
        results: list[tuple[Memory, float]] = []
        for memory_id, score in id_score_pairs:
            memory = self.get_memory_by_id(memory_id)
            if memory is not None:
                results.append((memory, score))
        return results

    def list_distinct_tags(self, client_id: str) -> list[str]:
        """Return the sorted set of distinct tags on memories owned by ``client_id``.

        Scans the TagIndex GSI (scope is limited to tag items — the base table
        is never scanned) filtering on ``owner_client_id`` and projecting only
        the ``GSI2PK`` attribute, which carries the ``TAG#{name}`` marker.
        """
        tags: set[str] = set()
        start_key: dict[str, Any] | None = None
        while True:
            kwargs: dict[str, Any] = {
                "IndexName": "TagIndex",
                "FilterExpression": "owner_client_id = :cid",
                "ExpressionAttributeValues": {":cid": client_id},
                "ProjectionExpression": "GSI2PK",
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = self.table.scan(**kwargs)
            for item in resp.get("Items", []):
                gsi_pk = item.get("GSI2PK", "")
                if gsi_pk.startswith("TAG#"):
                    tags.add(gsi_pk[len("TAG#") :])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        return sorted(tags)

    def list_memories_by_tag(
        self,
        tag: str,
        limit: int = 100,
        cursor: str | None = None,
        owner_user_id: str | None = None,
    ) -> tuple[list[Memory], str | None]:
        """Query TagIndex GSI to find memories with a given tag.

        When owner_user_id is provided, only memories belonging to that user
        are returned (within-user cross-client sharing is intentional product
        behaviour; cross-user isolation is enforced here).

        Returns (memories, next_cursor). next_cursor is None when exhausted.
        """
        kwargs: dict[str, Any] = {
            "IndexName": "TagIndex",
            "KeyConditionExpression": Key("GSI2PK").eq(f"TAG#{tag}"),
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)

        resp = self.table.query(**kwargs)
        memories: list[Memory] = []
        for item in resp.get("Items", []):
            m = self.get_memory_by_id(item["memory_id"])
            if m is not None and (owner_user_id is None or m.owner_user_id == owner_user_id):
                memories.append(m)

        lek = resp.get("LastEvaluatedKey")
        next_cursor = _encode_cursor(lek) if lek else None
        return memories, next_cursor

    def list_all_memories(
        self,
        client_id: str | None = None,
        owner_user_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Memory], str | None]:
        """Scan for all META memory items (optionally filtered by owner_client_id or owner_user_id).

        Returns (memories, next_cursor). Use sparingly — prefer tag-based queries.

        Iterates DynamoDB scan pages until *limit* matching items are collected,
        avoiding the "Limit evaluates N items before filter" footgun that causes
        misses in single-table designs with mixed item types.
        """
        filter_expr = "SK = :sk AND begins_with(PK, :pk_prefix)"
        expr_vals: dict[str, Any] = {":sk": "META", ":pk_prefix": "MEMORY#"}
        if client_id:
            filter_expr += " AND owner_client_id = :cid"
            expr_vals[":cid"] = client_id
        if owner_user_id:
            filter_expr += _UID_FILTER
            expr_vals[":uid"] = owner_user_id

        start_key = _decode_cursor(cursor) if cursor else None
        memories: list[Memory] = []

        while True:
            kwargs: dict[str, Any] = {
                "FilterExpression": filter_expr,
                "ExpressionAttributeValues": expr_vals,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key

            resp = self.table.scan(**kwargs)
            for item in resp.get("Items", []):
                memories.append(Memory.from_dynamo(item))
                if len(memories) >= limit:
                    break

            lek = resp.get("LastEvaluatedKey")
            if len(memories) >= limit:
                last = memories[limit - 1]
                next_key = {"PK": f"MEMORY#{last.memory_id}", "SK": "META"}
                return memories[:limit], _encode_cursor(next_key)
            if lek is None:
                return memories, None
            start_key = lek

    def delete_memories_by_tag(
        self,
        tag: str,
        owner_user_id: str | None = None,
    ) -> int:
        """Delete all memories with the given tag.

        If owner_user_id is provided, only memories owned by that user are deleted.
        Returns the count of memories deleted.
        """
        deleted = 0
        cursor: str | None = None
        while True:
            items, cursor = self.list_memories_by_tag(
                tag, limit=100, cursor=cursor, owner_user_id=owner_user_id
            )
            for memory in items:
                self._delete_tag_items(memory)
                self.table.delete_item(Key={"PK": f"MEMORY#{memory.memory_id}", "SK": "META"})
                self._delete_blob_if_needed(memory)
                deleted += 1
            if cursor is None:
                break
        return deleted

    def iter_all_memories(
        self,
        owner_user_id: str | None = None,
        tag: str | None = None,
    ) -> Iterator[Memory]:
        """Yield all memories, optionally filtered by owner or tag.

        For tag-filtered export, iterates TagIndex pages.
        For unfiltered export, scans all META items.
        This is a generator — use for streaming exports only.
        """
        if tag:
            cursor: str | None = None
            while True:
                items, cursor = self.list_memories_by_tag(
                    tag, limit=100, cursor=cursor, owner_user_id=owner_user_id
                )
                yield from items
                if cursor is None:
                    break
        else:
            filter_expr = "SK = :sk AND begins_with(PK, :pk_prefix)"
            expr_vals: dict[str, Any] = {":sk": "META", ":pk_prefix": "MEMORY#"}
            if owner_user_id:
                filter_expr += _UID_FILTER
                expr_vals[":uid"] = owner_user_id
            start_key: dict[str, Any] | None = None
            while True:
                kwargs: dict[str, Any] = {
                    "FilterExpression": filter_expr,
                    "ExpressionAttributeValues": expr_vals,
                }
                if start_key:
                    kwargs["ExclusiveStartKey"] = start_key
                resp = self.table.scan(**kwargs)
                for item in resp.get("Items", []):
                    yield Memory.from_dynamo(item)
                start_key = resp.get("LastEvaluatedKey")
                if start_key is None:
                    break

    # ------------------------------------------------------------------
    # OAuth Client management
    # ------------------------------------------------------------------

    def put_client(self, client: OAuthClient) -> None:
        self.table.put_item(Item=client.to_dynamo())

    def get_client(self, client_id: str) -> OAuthClient | None:
        resp = self.table.get_item(Key={"PK": f"CLIENT#{client_id}", "SK": "META"})
        item = resp.get("Item")
        return OAuthClient.from_dynamo(item) if item else None

    def delete_client(self, client_id: str) -> bool:
        resp = self.table.get_item(Key={"PK": f"CLIENT#{client_id}", "SK": "META"})
        if not resp.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"CLIENT#{client_id}", "SK": "META"})
        return True

    def list_clients(
        self,
        owner_user_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[OAuthClient], str | None]:
        filter_expr = "begins_with(PK, :prefix) AND SK = :sk"
        expr_vals: dict[str, Any] = {_PK_PREFIX_KEY: "CLIENT#", ":sk": "META"}
        if owner_user_id:
            filter_expr += _UID_FILTER
            expr_vals[":uid"] = owner_user_id

        start_key = _decode_cursor(cursor) if cursor else None
        clients: list[OAuthClient] = []

        while True:
            kwargs: dict[str, Any] = {
                "FilterExpression": filter_expr,
                "ExpressionAttributeValues": expr_vals,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key

            resp = self.table.scan(**kwargs)
            for item in resp.get("Items", []):
                clients.append(OAuthClient.from_dynamo(item))
                if len(clients) >= limit:
                    break

            lek = resp.get("LastEvaluatedKey")
            if len(clients) >= limit:
                last = clients[limit - 1]
                next_key = {"PK": f"CLIENT#{last.client_id}", "SK": "META"}
                return clients[:limit], _encode_cursor(next_key)
            if lek is None:
                return clients, None
            start_key = lek

    # ------------------------------------------------------------------
    # Authorization codes
    # ------------------------------------------------------------------

    def put_auth_code(self, code: AuthorizationCode) -> None:
        self.table.put_item(Item=code.to_dynamo())

    def get_auth_code(self, code: str) -> AuthorizationCode | None:
        resp = self.table.get_item(Key={"PK": f"AUTHCODE#{code}", "SK": "META"})
        item = resp.get("Item")
        return AuthorizationCode.from_dynamo(item) if item else None

    def mark_auth_code_used(self, code: str) -> None:
        """Atomically mark an OAuth authorization code as redeemed.

        RFC 6749 §10.5 requires authorization codes to be single-use.
        Two concurrent `POST /oauth/token` requests with the same `code`
        used to both pass the `auth_code.used` pre-check in
        ``oauth.py`` before either could write back — the classic
        read-check-write TOCTOU. This now enforces single-use at the
        DynamoDB layer via a conditional write on ``used = false``;
        exactly one concurrent redeemer succeeds, the other raises
        :class:`AuthCodeAlreadyUsed`.

        The caller should have already validated the code's existence,
        client binding, redirect URI, expiry, and PKCE; this call is
        the commit point of the redemption pipeline.
        """
        try:
            self.table.update_item(
                Key={"PK": f"AUTHCODE#{code}", "SK": "META"},
                UpdateExpression="SET #u = :t",
                ConditionExpression="attribute_exists(PK) AND #u = :f",
                ExpressionAttributeNames={"#u": "used"},
                ExpressionAttributeValues={":t": True, ":f": False},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AuthCodeAlreadyUsed(
                    "Authorization code has already been redeemed or does not exist"
                ) from exc
            raise

    # ------------------------------------------------------------------
    # Pending auth (PKCE state stored while user authenticates with Google)
    # ------------------------------------------------------------------

    def put_pending_auth(self, pending: PendingAuth) -> None:
        self.table.put_item(Item=pending.to_dynamo())

    def get_pending_auth(self, state: str) -> PendingAuth | None:
        resp = self.table.get_item(Key={"PK": f"PENDING#{state}", "SK": "META"})
        item = resp.get("Item")
        return PendingAuth.from_dynamo(item) if item else None

    def delete_pending_auth(self, state: str) -> None:
        self.table.delete_item(Key={"PK": f"PENDING#{state}", "SK": "META"})

    def create_pending_auth(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str,
        original_state: str,
    ) -> PendingAuth:
        pending = PendingAuth(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            original_state=original_state,
            expires_at=_now() + timedelta(seconds=PENDING_AUTH_TTL_SECONDS),
        )
        self.put_pending_auth(pending)
        return pending

    # ------------------------------------------------------------------
    # Tokens
    # ------------------------------------------------------------------

    def put_token(self, token: Token) -> None:
        self.table.put_item(Item=token.to_dynamo())

    def get_token(self, jti: str) -> Token | None:
        resp = self.table.get_item(Key={"PK": f"TOKEN#{jti}", "SK": "META"})
        item = resp.get("Item")
        return Token.from_dynamo(item) if item else None

    def revoke_token(self, jti: str) -> None:
        self.table.update_item(
            Key={"PK": f"TOKEN#{jti}", "SK": "META"},
            UpdateExpression="SET revoked = :t",
            ExpressionAttributeValues={":t": True},
        )

    def create_token_pair(self, client_id: str, scope: str) -> tuple[Token, Token]:
        """Issue a new (access_token, refresh_token) pair."""
        now = _now()
        access = Token(
            client_id=client_id,
            scope=scope,
            token_type=TokenType.access,
            issued_at=now,
            expires_at=now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS),
        )
        refresh = Token(
            client_id=client_id,
            scope=scope,
            token_type=TokenType.refresh,
            issued_at=now,
            expires_at=now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
        )
        self.put_token(access)
        self.put_token(refresh)
        return access, refresh

    def create_auth_code(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str = "S256",
    ) -> AuthorizationCode:
        now = _now()
        code = AuthorizationCode(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=now + timedelta(seconds=AUTH_CODE_TTL_SECONDS),
        )
        self.put_auth_code(code)
        return code

    # ------------------------------------------------------------------
    # Users (management UI identities)
    # ------------------------------------------------------------------

    def put_user(self, user: User) -> None:
        self.table.put_item(Item=user.to_dynamo())

    def get_user_by_id(self, user_id: str) -> User | None:
        resp = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
        item = resp.get("Item")
        return User.from_dynamo(item) if item else None

    def get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email using the UserEmailIndex GSI."""
        resp = self.table.query(
            IndexName="UserEmailIndex",
            KeyConditionExpression=Key("GSI4PK").eq(f"EMAIL#{email}"),
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        return self.get_user_by_id(items[0]["user_id"])

    def update_user_role(self, user_id: str, role: str) -> bool:
        resp = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
        if not resp.get("Item"):
            return False
        self.table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression="SET #r = :role",
            ExpressionAttributeNames={"#r": "role"},
            ExpressionAttributeValues={":role": role},
        )
        return True

    def delete_user(self, user_id: str) -> bool:
        resp = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
        if not resp.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
        return True

    def list_users(
        self,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[User], str | None]:
        filter_expr = "begins_with(PK, :prefix) AND SK = :sk"
        expr_vals: dict[str, Any] = {_PK_PREFIX_KEY: "USER#", ":sk": "META"}

        start_key = _decode_cursor(cursor) if cursor else None
        users: list[User] = []

        while True:
            kwargs: dict[str, Any] = {
                "FilterExpression": filter_expr,
                "ExpressionAttributeValues": expr_vals,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key

            resp = self.table.scan(**kwargs)
            for item in resp.get("Items", []):
                users.append(User.from_dynamo(item))
                if len(users) >= limit:
                    break

            lek = resp.get("LastEvaluatedKey")
            if len(users) >= limit:
                last = users[limit - 1]
                next_key = {"PK": f"USER#{last.user_id}", "SK": "META"}
                return users[:limit], _encode_cursor(next_key)
            if lek is None:
                return users, None
            start_key = lek

    # ------------------------------------------------------------------
    # Management pending state (nonce for management UI Google login)
    # ------------------------------------------------------------------

    def put_mgmt_pending_state(self, state: MgmtPendingState) -> None:
        self.table.put_item(Item=state.to_dynamo())

    def get_mgmt_pending_state(self, state: str) -> MgmtPendingState | None:
        resp = self.table.get_item(Key={"PK": f"MGMT_STATE#{state}", "SK": "META"})
        item = resp.get("Item")
        return MgmtPendingState.from_dynamo(item) if item else None

    def delete_mgmt_pending_state(self, state: str) -> None:
        self.table.delete_item(Key={"PK": f"MGMT_STATE#{state}", "SK": "META"})

    def create_mgmt_pending_state(self) -> MgmtPendingState:
        pending = MgmtPendingState(
            expires_at=_now() + timedelta(seconds=MGMT_PENDING_STATE_TTL_SECONDS),
        )
        self.put_mgmt_pending_state(pending)
        return pending

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------

    def log_event(self, event: ActivityEvent) -> None:
        self.table.put_item(Item=event.to_dynamo())

    def get_events_for_date(self, date: str) -> list[ActivityEvent]:
        """Query activity log for a specific date (YYYY-MM-DD).

        Queries all 24 hour-sharded partitions (LOG#{date}#{HH}) in parallel
        and merges results. Also queries the legacy LOG#{date} partition for
        backward compatibility with items written before the hour-sharding migration.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _query(pk: str) -> list[ActivityEvent]:
            resp = self.table.query(KeyConditionExpression=Key("PK").eq(pk))
            return [ActivityEvent.from_dynamo(i) for i in resp.get("Items", [])]

        # Build all partition keys: 24 hour shards + legacy unsharded key
        pks = [f"LOG#{date}#{hour:02d}" for hour in range(24)]
        pks.append(f"LOG#{date}")  # backward compat

        events: list[ActivityEvent] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_query, pk): pk for pk in pks}
            for future in as_completed(futures):
                events.extend(future.result())

        return events

    def get_events_for_dates(
        self,
        dates: list[str],
        limit: int = 100,
    ) -> list[ActivityEvent]:
        """Fetch events across multiple dates, sorted newest-first, capped at limit."""
        events: list[ActivityEvent] = []
        for d in dates:
            events.extend(self.get_events_for_date(d))
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count_memories(self, owner_user_id: str | None = None) -> int:
        filter_expr = "SK = :sk AND begins_with(PK, :prefix)"
        expr_vals: dict[str, Any] = {":sk": "META", _PK_PREFIX_KEY: "MEMORY#"}
        if owner_user_id:
            filter_expr += _UID_FILTER
            expr_vals[":uid"] = owner_user_id
        resp = self.table.scan(
            Select="COUNT",
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_vals,
        )
        return resp.get("Count", 0)

    def count_clients(self, owner_user_id: str | None = None) -> int:
        filter_expr = "SK = :sk AND begins_with(PK, :prefix)"
        expr_vals: dict[str, Any] = {":sk": "META", _PK_PREFIX_KEY: "CLIENT#"}
        if owner_user_id:
            filter_expr += _UID_FILTER
            expr_vals[":uid"] = owner_user_id
        resp = self.table.scan(
            Select="COUNT",
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_vals,
        )
        return resp.get("Count", 0)

    def count_users(self) -> int:
        resp = self.table.scan(
            Select="COUNT",
            FilterExpression="SK = :sk AND begins_with(PK, :prefix)",
            ExpressionAttributeValues={":sk": "META", _PK_PREFIX_KEY: "USER#"},
        )
        return resp.get("Count", 0)

    def sum_storage_bytes(self, owner_user_id: str | None = None) -> int:
        """Return the total stored bytes across all memories for the given user (or all users)."""
        filter_expr = "SK = :sk AND begins_with(PK, :prefix)"
        expr_vals: dict[str, Any] = {":sk": "META", _PK_PREFIX_KEY: "MEMORY#"}
        if owner_user_id:
            filter_expr += _UID_FILTER
            expr_vals[":uid"] = owner_user_id
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": filter_expr,
            "ExpressionAttributeValues": expr_vals,
            "ProjectionExpression": "#sb",
            "ExpressionAttributeNames": {"#sb": "size_bytes"},
        }
        total = 0
        resp = self.table.scan(**scan_kwargs)
        while True:
            total += sum(int(item.get("size_bytes", 0)) for item in resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if last_key is None:
                break
            resp = self.table.scan(**scan_kwargs, ExclusiveStartKey=last_key)
        return total

    def update_user_limits(
        self,
        user_id: str,
        memory_limit: int | None,
        storage_bytes_limit: int | None,
    ) -> bool:
        """Set per-user quota overrides. Pass None to remove an override (revert to system default)."""
        set_parts: list[str] = []
        remove_parts: list[str] = []
        expr_vals: dict[str, Any] = {}

        if memory_limit is not None:
            set_parts.append("memory_limit = :ml")
            expr_vals[":ml"] = memory_limit
        else:
            remove_parts.append("memory_limit")

        if storage_bytes_limit is not None:
            set_parts.append("storage_bytes_limit = :sbl")
            expr_vals[":sbl"] = storage_bytes_limit
        else:
            remove_parts.append("storage_bytes_limit")

        parts: list[str] = []
        if set_parts:
            parts.append("SET " + ", ".join(set_parts))
        if remove_parts:
            parts.append("REMOVE " + ", ".join(remove_parts))

        update_kwargs: dict[str, Any] = {
            "Key": {"PK": f"USER#{user_id}", "SK": "META"},
            "UpdateExpression": " ".join(parts),
            "ConditionExpression": "attribute_exists(PK)",
        }
        if expr_vals:
            update_kwargs["ExpressionAttributeValues"] = expr_vals

        try:
            self.table.update_item(**update_kwargs)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    # ------------------------------------------------------------------
    # API Keys
    # ------------------------------------------------------------------

    def put_api_key(self, key: ApiKey) -> None:
        self.table.put_item(Item=key.to_dynamo())

    def get_api_key_by_id(self, key_id: str) -> ApiKey | None:
        resp = self.table.get_item(Key={"PK": f"APIKEY#{key_id}", "SK": "META"})
        item = resp.get("Item")
        return ApiKey.from_dynamo(item) if item else None

    def get_api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        """Look up an API key by its SHA-256 hash (full table scan — keys are rare)."""
        resp = self.table.scan(
            FilterExpression="begins_with(PK, :prefix) AND SK = :sk AND key_hash = :hash",
            ExpressionAttributeValues={
                _PK_PREFIX_KEY: "APIKEY#",
                ":sk": "META",
                ":hash": key_hash,
            },
        )
        items = resp.get("Items", [])
        return ApiKey.from_dynamo(items[0]) if items else None

    def list_api_keys_for_user(self, owner_user_id: str) -> list[ApiKey]:
        resp = self.table.scan(
            FilterExpression="begins_with(PK, :prefix) AND SK = :sk AND owner_user_id = :uid",
            ExpressionAttributeValues={
                _PK_PREFIX_KEY: "APIKEY#",
                ":sk": "META",
                ":uid": owner_user_id,
            },
        )
        return [ApiKey.from_dynamo(item) for item in resp.get("Items", [])]

    def delete_api_key(self, key_id: str) -> bool:
        resp = self.table.get_item(Key={"PK": f"APIKEY#{key_id}", "SK": "META"})
        if not resp.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"APIKEY#{key_id}", "SK": "META"})
        return True

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def increment_rate_limit_counter(
        self, client_id: str, window_key: str, ttl_seconds: int
    ) -> int:
        """Atomically increment a rate limit counter and return the new value.

        The counter item is created on first access. TTL is set only on the
        first write (``if_not_exists``) so DynamoDB TTL can clean up expired
        counters automatically.

        Args:
            client_id:   The OAuth client being rate-limited.
            window_key:  Window identifier, e.g. ``min#2026-04-12T10:30``.
            ttl_seconds: Seconds from now after which the item should expire.
        """
        import time

        pk = f"RATELIMIT#{client_id}#{window_key}"
        ttl_epoch = int(time.time()) + ttl_seconds
        resp = self.table.update_item(
            Key={"PK": pk, "SK": "META"},
            UpdateExpression="SET #ttl = if_not_exists(#ttl, :ttl) ADD #c :one",
            ExpressionAttributeNames={"#c": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={":one": Decimal("1"), ":ttl": ttl_epoch},
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"]["count"])

    # ------------------------------------------------------------------
    # Audit log (separate from user activity log)
    # ------------------------------------------------------------------

    def log_audit_event(self, event: ActivityEvent) -> None:
        """Write an audit event to the immutable audit log (AUDIT# PK prefix).

        Audit events use a separate PK prefix from activity log events (LOG#)
        so they survive a user-requested activity-log purge. A DynamoDB TTL
        provides a hard retention horizon (``HIVE_AUDIT_RETENTION_DAYS``,
        default 365) so items age out automatically and we stay compliant
        with data-minimisation expectations.
        """
        item = event.to_dynamo()
        date_hour_str = event.timestamp.strftime("%Y-%m-%d#%H")
        item["PK"] = f"AUDIT#{date_hour_str}"
        retention_days = int(os.environ.get("HIVE_AUDIT_RETENTION_DAYS", "365"))
        item["ttl"] = int(event.timestamp.timestamp()) + retention_days * 86400
        self.table.put_item(Item=item)

    def get_audit_events_for_dates(
        self,
        dates: list[str],
        *,
        client_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[ActivityEvent]:
        """Fetch audit events across multiple dates, newest-first, capped at limit.

        Optional post-query filters on ``client_id`` and ``event_type`` keep
        the admin audit-log endpoint simple; the partition scan itself reads
        every hour-shard in parallel.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _query(pk: str) -> list[ActivityEvent]:
            resp = self.table.query(KeyConditionExpression=Key("PK").eq(pk))
            return [ActivityEvent.from_dynamo(i) for i in resp.get("Items", [])]

        pks = [f"AUDIT#{d}#{hour:02d}" for d in dates for hour in range(24)]
        events: list[ActivityEvent] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_query, pk): pk for pk in pks}
            for future in as_completed(futures):
                events.extend(future.result())

        if client_id is not None:
            events = [e for e in events if e.client_id == client_id]
        if event_type is not None:
            events = [e for e in events if e.event_type.value == event_type]

        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    # ------------------------------------------------------------------
    # Account deletion
    # ------------------------------------------------------------------

    def delete_user_data(self, user_id: str) -> dict[str, int]:
        """Delete all data owned by a user.

        Deletes all memories, OAuth clients, and the user record.
        Tokens are not explicitly revoked — they carry short TTLs and
        will expire naturally. Returns counts of deleted items.
        """
        deleted_memories = 0
        cursor: str | None = None
        while True:
            memories, cursor = self.list_all_memories(
                owner_user_id=user_id, limit=200, cursor=cursor
            )
            for memory in memories:
                self.delete_memory(memory.memory_id)
                deleted_memories += 1
            if cursor is None:
                break

        deleted_clients = 0
        cursor = None
        while True:
            clients, cursor = self.list_clients(owner_user_id=user_id, limit=200, cursor=cursor)
            for client in clients:
                self.delete_client(client.client_id)
                deleted_clients += 1
            if cursor is None:
                break

        self.delete_user(user_id)

        return {"deleted_memories": deleted_memories, "deleted_clients": deleted_clients}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delete_blob_if_needed(self, memory: Memory) -> None:
        """Delete the S3 blob for a memory if one exists.

        Called after the DynamoDB item is already removed. Failures are
        logged as warnings and swallowed — the memory is already gone from
        DynamoDB so it's inaccessible regardless. The configured S3
        lifecycle rule only aborts incomplete multipart uploads; it does
        not clean up orphaned objects left behind by failed deletes.
        """
        if memory.s3_uri is None:
            return
        owner = memory.owner_user_id or memory.owner_client_id or ""
        try:
            self.blob_store.delete(owner=owner, memory_id=memory.memory_id)
        except Exception:
            logger.warning(
                "blob_delete_failed memory_id=%s s3_uri=%s",
                memory.memory_id,
                memory.s3_uri,
                exc_info=True,
            )

    def fetch_blob_value(self, memory: Memory) -> str:
        """Fetch the full text content from S3 for a ``text-large`` memory.

        Raises whatever the underlying blob store raises so the caller can
        decide whether to propagate or surface a user-facing fallback.
        """
        owner = memory.owner_user_id or memory.owner_client_id or ""
        data = self.blob_store.get(owner=owner, memory_id=memory.memory_id)
        return data.decode("utf-8")

    def fetch_blob_bytes(self, memory: Memory) -> bytes:
        """Fetch raw binary content from S3 for an ``image`` or ``blob`` memory.

        Raises whatever the underlying blob store raises so the caller can
        decide whether to propagate or surface a user-facing fallback.
        """
        owner = memory.owner_user_id or memory.owner_client_id or ""
        return self.blob_store.get(owner=owner, memory_id=memory.memory_id)

    def _get_memory_meta(self, memory_id: str) -> dict[str, Any] | None:
        resp = self.table.get_item(Key={"PK": f"MEMORY#{memory_id}", "SK": "META"})
        item: dict[str, Any] | None = resp.get("Item")  # type: ignore[assignment]
        return item

    def _delete_tag_items(self, memory: Memory) -> None:
        with self.table.batch_writer() as batch:
            for tag in memory.tags:
                batch.delete_item(Key={"PK": f"MEMORY#{memory.memory_id}", "SK": f"TAG#{tag}"})
