# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for the storage layer using moto to mock DynamoDB.
"""

from __future__ import annotations

import os

import boto3
import pytest

# Must set env var before importing storage so TABLE_NAME picks it up
os.environ.setdefault("HIVE_TABLE_NAME", "hive-test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from moto import mock_aws

from hive.models import (
    ActivityEvent,
    ApiKey,
    EventType,
    Memory,
    OAuthClient,
    TokenType,
    User,
    UserResponse,
)
from hive.storage import HiveStorage


@pytest.fixture()
def storage():
    """Provide a HiveStorage backed by a fresh moto-mocked DynamoDB table."""
    with mock_aws():
        _create_table()
        yield HiveStorage(table_name="hive-test", region="us-east-1")


def _create_table():
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-test",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
            {"AttributeName": "GSI2PK", "AttributeType": "S"},
            {"AttributeName": "GSI2SK", "AttributeType": "S"},
            {"AttributeName": "GSI4PK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "KeyIndex",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "TagIndex",
                "KeySchema": [
                    {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "UserEmailIndex",
                "KeySchema": [
                    {"AttributeName": "GSI4PK", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


# ---------------------------------------------------------------------------
# Memory tests
# ---------------------------------------------------------------------------


class TestMemoryStorage:
    def test_put_and_get_by_key(self, storage):
        m = Memory(key="hello", value="world", owner_client_id="c1")
        storage.put_memory(m)
        result = storage.get_memory_by_key("hello")
        assert result is not None
        assert result.value == "world"

    def test_get_nonexistent_key(self, storage):
        assert storage.get_memory_by_key("no-such-key") is None

    def test_get_by_id(self, storage):
        m = Memory(key="k", value="v", owner_client_id="c1")
        storage.put_memory(m)
        result = storage.get_memory_by_id(m.memory_id)
        assert result is not None
        assert result.memory_id == m.memory_id

    def test_delete(self, storage):
        m = Memory(key="to-delete", value="bye", owner_client_id="c1")
        storage.put_memory(m)
        assert storage.delete_memory(m.memory_id)
        assert storage.get_memory_by_key("to-delete") is None

    def test_delete_nonexistent(self, storage):
        assert not storage.delete_memory("fake-id")

    def test_list_by_tag(self, storage):
        m1 = Memory(key="a", value="1", tags=["x", "y"], owner_client_id="c1")
        m2 = Memory(key="b", value="2", tags=["y", "z"], owner_client_id="c1")
        m3 = Memory(key="c", value="3", tags=["z"], owner_client_id="c1")
        for m in [m1, m2, m3]:
            storage.put_memory(m)

        tagged_y, _ = storage.list_memories_by_tag("y")
        keys = {m.key for m in tagged_y}
        assert keys == {"a", "b"}

        tagged_z, _ = storage.list_memories_by_tag("z")
        keys_z = {m.key for m in tagged_z}
        assert keys_z == {"b", "c"}

    def test_list_distinct_tags_returns_sorted_unique(self, storage):
        for m in [
            Memory(key="a", value="1", tags=["zebra", "alpha"], owner_client_id="c1"),
            Memory(key="b", value="2", tags=["alpha", "mango"], owner_client_id="c1"),
            Memory(key="c", value="3", tags=[], owner_client_id="c1"),
        ]:
            storage.put_memory(m)

        assert storage.list_distinct_tags("c1") == ["alpha", "mango", "zebra"]

    def test_list_distinct_tags_scoped_to_client(self, storage):
        storage.put_memory(Memory(key="a", value="1", tags=["mine"], owner_client_id="c1"))
        storage.put_memory(Memory(key="b", value="2", tags=["theirs"], owner_client_id="c2"))

        assert storage.list_distinct_tags("c1") == ["mine"]
        assert storage.list_distinct_tags("c2") == ["theirs"]

    def test_list_distinct_tags_empty_when_no_memories(self, storage):
        assert storage.list_distinct_tags("c1") == []

    def test_list_distinct_tags_follows_scan_pages(self, storage):
        from unittest.mock import patch

        responses = iter(
            [
                {"Items": [{"GSI2PK": "TAG#alpha"}], "LastEvaluatedKey": {"PK": "x"}},
                {"Items": [{"GSI2PK": "TAG#beta"}, {"GSI2PK": "NOT_A_TAG"}]},
            ]
        )
        with patch.object(storage.table, "scan", side_effect=lambda **_kw: next(responses)):
            result = storage.list_distinct_tags("c1")

        assert result == ["alpha", "beta"]

    def test_update_replaces_tags(self, storage):
        m = Memory(key="k", value="v", tags=["old"], owner_client_id="c1")
        storage.put_memory(m)

        m.tags = ["new"]
        storage.put_memory(m)

        old_tagged, _ = storage.list_memories_by_tag("old")
        assert old_tagged == []
        new_tagged, _ = storage.list_memories_by_tag("new")
        assert len(new_tagged) == 1

    def test_upsert_by_key(self, storage):
        m = Memory(key="upsert-key", value="v1", tags=["a"], owner_client_id="c1")
        storage.put_memory(m)

        m2 = storage.get_memory_by_key("upsert-key")
        assert m2 is not None
        m2.value = "v2"
        m2.tags = ["b"]
        storage.put_memory(m2)

        result = storage.get_memory_by_key("upsert-key")
        assert result is not None
        assert result.value == "v2"
        assert result.tags == ["b"]
        assert result.memory_id == m.memory_id  # same item, not a new one

    def test_put_memory_too_large_raises_value_error(self, storage):
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        oversized = Memory(key="big", value="x" * 1000, tags=[], owner_client_id="c1")
        error_response = {
            "Error": {
                "Code": "ValidationException",
                "Message": "Item size has exceeded the maximum allowed size",
            }
        }
        with patch.object(storage.table, "batch_writer") as mock_bw:
            mock_bw.return_value.__enter__.return_value.put_item.side_effect = ClientError(
                error_response, "PutItem"
            )
            with pytest.raises(ValueError, match="too large"):
                storage.put_memory(oversized)

    def test_put_memory_other_client_error_reraises(self, storage):
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        m = Memory(key="err", value="v", tags=[], owner_client_id="c1")
        error_response = {
            "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow"}
        }
        with patch.object(storage.table, "batch_writer") as mock_bw:
            mock_bw.return_value.__enter__.return_value.put_item.side_effect = ClientError(
                error_response, "PutItem"
            )
            with pytest.raises(ClientError):
                storage.put_memory(m)

    def test_put_memory_with_matching_version_succeeds(self, storage):
        """expected_version on put_memory matches stored updated_at → write succeeds."""
        from datetime import datetime, timezone

        # Tags are set so the conditional-write branch also rewrites tag items.
        m = Memory(key="ver-ok", value="v1", tags=["t1"], owner_client_id="c1")
        storage.put_memory(m)
        stored = storage.get_memory_by_id(m.memory_id)
        assert stored is not None

        stored.value = "v2"
        stored.tags = ["t1", "t2"]
        stored.updated_at = datetime.now(timezone.utc)  # mimics server.remember()
        storage.put_memory(stored, expected_version=m.version)
        result = storage.get_memory_by_id(m.memory_id)
        assert result.value == "v2"
        assert set(result.tags) == {"t1", "t2"}

    def test_put_memory_with_stale_version_raises(self, storage):
        from datetime import datetime, timedelta, timezone

        from hive.storage import VersionConflict

        m = Memory(key="ver-stale", value="v1", owner_client_id="c1")
        storage.put_memory(m)

        # Someone else writes first, moving the version forward (updated_at bumps).
        m2 = storage.get_memory_by_id(m.memory_id)
        m2.value = "v2"
        m2.updated_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        storage.put_memory(m2)

        # Now a write pinned to the *original* version is rejected.
        m.value = "stale"
        with pytest.raises(VersionConflict) as exc_info:
            storage.put_memory(m, expected_version=m.version)
        assert exc_info.value.current_value == "v2"
        assert exc_info.value.current_version != m.version

    def test_put_memory_with_version_but_no_existing_item_raises(self, storage):
        """Passing expected_version on a brand-new memory is a conflict (there's
        nothing to lock against)."""
        from hive.storage import VersionConflict

        m = Memory(key="ver-missing", value="v1", owner_client_id="c1")
        with pytest.raises(VersionConflict) as exc_info:
            storage.put_memory(m, expected_version="2024-01-01T00:00:00+00:00")
        assert exc_info.value.current_value is None
        assert exc_info.value.current_version is None

    def test_put_memory_conditional_check_failure_surfaces_as_version_conflict(self, storage):
        """If the conditional put race fires after the pre-read, we re-read
        and surface the real current state in VersionConflict."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        from hive.storage import VersionConflict

        m = Memory(key="ver-race", value="v1", owner_client_id="c1")
        storage.put_memory(m)
        stored = storage.get_memory_by_id(m.memory_id)

        stored.value = "v2"
        stored.updated_at = datetime.now(timezone.utc)

        # Only the conditional META put should fail; version-snapshot writes
        # (SK=VERSION#…) must still succeed so execution reaches the conditional.
        real_put = storage.table.put_item
        error_response = {
            "Error": {"Code": "ConditionalCheckFailedException", "Message": "mismatch"}
        }

        def selective(**kwargs):
            if "ConditionExpression" in kwargs:
                raise ClientError(error_response, "PutItem")
            return real_put(**kwargs)

        with (
            patch.object(storage.table, "put_item", side_effect=selective),
            pytest.raises(VersionConflict),
        ):
            storage.put_memory(stored, expected_version=m.version)

    def test_put_and_get_memory_with_ttl(self, storage):
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        m = Memory(key="ttl-key", value="ttl-val", owner_client_id="c1", expires_at=expires_at)
        storage.put_memory(m)
        result = storage.get_memory_by_id(m.memory_id)
        assert result is not None
        assert result.expires_at is not None
        assert abs((result.expires_at - expires_at).total_seconds()) < 1

    def test_get_expired_memory_returns_none(self, storage):
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        m = Memory(key="expired-key", value="gone", owner_client_id="c1", expires_at=past)
        storage.put_memory(m)
        # DynamoDB TTL is eventually consistent; filter client-side
        result = storage.get_memory_by_id(m.memory_id)
        assert result is None

    def test_get_memory_by_key_expired_returns_none(self, storage):
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        m = Memory(key="expired-key2", value="gone", owner_client_id="c1", expires_at=past)
        storage.put_memory(m)
        result = storage.get_memory_by_key("expired-key2")
        assert result is None

    def test_record_recall_increments_count_and_sets_timestamp(self, storage):
        m = Memory(key="recall-k", value="v", owner_client_id="c1")
        storage.put_memory(m)

        first = storage.record_recall("recall-k")
        assert first is not None
        assert first.recall_count == 1
        assert first.last_accessed_at is not None

        second = storage.record_recall("recall-k")
        assert second is not None
        assert second.recall_count == 2
        assert second.last_accessed_at is not None
        assert second.last_accessed_at >= first.last_accessed_at

    def test_record_recall_returns_none_for_missing_key(self, storage):
        assert storage.record_recall("does-not-exist") is None

    def test_record_recall_returns_none_for_expired_memory(self, storage):
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        storage.put_memory(
            Memory(key="expired-recall", value="v", owner_client_id="c1", expires_at=past)
        )
        # update_item still runs, but record_recall returns None because the
        # memory is past its TTL (matches get_memory_by_key behaviour).
        assert storage.record_recall("expired-recall") is None

    def test_memory_serialise_ttl_in_dynamo(self):
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        m = Memory(key="k", value="v", owner_client_id="c1", expires_at=expires_at)
        item = m.to_dynamo_meta()
        assert "expires_at" in item
        assert "ttl" in item
        assert item["ttl"] == int(expires_at.timestamp())

    def test_memory_deserialise_ttl_from_dynamo(self):
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        m = Memory(key="k", value="v", owner_client_id="c1", expires_at=expires_at)
        item = m.to_dynamo_meta()
        restored = Memory.from_dynamo(item)
        assert restored.expires_at is not None
        assert abs((restored.expires_at - expires_at).total_seconds()) < 1

    def test_memory_is_expired_false_when_no_ttl(self):
        m = Memory(key="k", value="v", owner_client_id="c1")
        assert not m.is_expired

    def test_memory_is_expired_true_when_past(self):
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        m = Memory(key="k", value="v", owner_client_id="c1", expires_at=past)
        assert m.is_expired

    def test_put_memory_saves_version_on_update(self, storage):
        """Updating an existing memory should create a version snapshot."""
        m = Memory(key="v-key", value="v1", owner_client_id="c1")
        storage.put_memory(m)
        m.value = "v2"
        storage.put_memory(m)
        versions = storage.list_memory_versions(m.memory_id)
        assert len(versions) == 1
        assert versions[0].value == "v1"

    def test_put_new_memory_does_not_create_version(self, storage):
        """Creating a brand-new memory should NOT create a version snapshot."""
        m = Memory(key="fresh", value="x", owner_client_id="c1")
        storage.put_memory(m)
        assert storage.list_memory_versions(m.memory_id) == []


# ---------------------------------------------------------------------------
# Large-memory routing tests (#497)
# ---------------------------------------------------------------------------


class _FakeBlobStore:
    """In-memory stand-in for BlobStore — records put/get/delete."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.content_types: dict[tuple[str, str], str] = {}

    def put(self, owner, memory_id, body, content_type="text/plain; charset=utf-8"):
        self.objects[(owner, memory_id)] = body
        self.content_types[(owner, memory_id)] = content_type
        return f"s3://fake-bucket/{owner}/{memory_id}"

    def get(self, owner, memory_id):
        return self.objects[(owner, memory_id)]

    def delete(self, owner, memory_id):
        self.objects.pop((owner, memory_id), None)


@pytest.fixture()
def storage_with_blob_store(storage):
    """Storage fixture with a fake BlobStore wired in."""
    fake = _FakeBlobStore()
    storage._blob_store_override = fake
    return storage, fake


class TestLargeMemoryRouting:
    """#497 — oversized text values get offloaded to the blob store."""

    def test_small_text_memory_stays_inline(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        m = Memory(key="small", value="hello", owner_client_id="c1")
        storage.put_memory(m)

        # No S3 object — stayed inline in DynamoDB.
        assert fake.objects == {}

        stored = storage.get_memory_by_key("small")
        assert stored is not None
        assert stored.value == "hello"
        assert stored.value_type == "text"
        assert stored.s3_uri is None
        # size_bytes gets set for future quota rollups (#500) even
        # on the inline path.
        assert stored.size_bytes == 5

    def test_large_text_memory_routes_to_s3(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        # 500 KB > 100 KB threshold → gets promoted to text-large.
        big_value = "x" * (500 * 1024)
        m = Memory(
            key="big-doc",
            value=big_value,
            owner_client_id="c1",
            owner_user_id="u-1",
        )
        storage.put_memory(m)

        # Exactly one S3 object stored under owner_user_id / memory_id.
        assert list(fake.objects.keys()) == [("u-1", m.memory_id)]
        assert fake.objects[("u-1", m.memory_id)] == big_value.encode("utf-8")

        stored = storage.get_memory_by_key("big-doc")
        assert stored is not None
        assert stored.value_type == "text-large"
        assert stored.s3_uri == f"s3://fake-bucket/u-1/{m.memory_id}"
        assert stored.size_bytes == 500 * 1024
        assert stored.content_type == "text/plain; charset=utf-8"
        # Inline DynamoDB value is empty — authoritative bytes live in S3.
        assert stored.value == ""

    def test_owner_prefix_falls_back_to_client_when_user_missing(self, storage_with_blob_store):
        # Pre-user-migration memories (#482 pending) don't carry
        # owner_user_id. The routing uses owner_client_id so those
        # memories still land in a tenant-scoped prefix.
        storage, fake = storage_with_blob_store
        big_value = "y" * (200 * 1024)
        m = Memory(key="pre-user", value=big_value, owner_client_id="legacy-client")
        storage.put_memory(m)
        assert ("legacy-client", m.memory_id) in fake.objects

    def test_non_text_value_type_skips_the_router(self, storage_with_blob_store):
        # #499's remember_blob path supplies an image/blob with its
        # own s3_uri already set — the transparent-text router must
        # leave those alone.
        storage, fake = storage_with_blob_store
        m = Memory(
            key="img",
            value="",
            value_type="image",
            s3_uri="s3://some/other/path",
            content_type="image/png",
            size_bytes=1234,
            owner_client_id="c1",
        )
        storage.put_memory(m)
        # Router did not upload anything — binary upload is the
        # caller's responsibility for non-text types.
        assert fake.objects == {}

        stored = storage.get_memory_by_key("img")
        assert stored is not None
        assert stored.value_type == "image"
        assert stored.s3_uri == "s3://some/other/path"
        assert stored.content_type == "image/png"
        assert stored.size_bytes == 1234

    def test_value_type_text_with_none_value_skips_upload(self, storage_with_blob_store):
        # Defensive — Pydantic would coerce this to the default
        # empty string, but an explicit None must not crash the
        # router.
        storage, fake = storage_with_blob_store
        m = Memory(key="edge", owner_client_id="c1")
        m.value = None  # bypass pydantic default
        storage.put_memory(m)
        assert fake.objects == {}

    def test_value_exceeding_max_blob_size_raises(self, storage_with_blob_store):
        from hive.blob_store import INLINE_TEXT_THRESHOLD_BYTES, MAX_BLOB_SIZE_BYTES

        storage, _ = storage_with_blob_store
        big_value = "x" * (MAX_BLOB_SIZE_BYTES + 1)
        m = Memory(key="too-big", value=big_value, owner_client_id="c1")
        with pytest.raises(ValueError, match="exceeds the maximum"):
            storage._route_large_value(m)
        # Inline-threshold check must still pass before the size guard triggers.
        assert len(big_value.encode("utf-8")) > INLINE_TEXT_THRESHOLD_BYTES

    def test_blob_store_property_lazy_instantiates_real_blob_store(self, storage, monkeypatch):
        # Covers the lazy-init path (lines 147-151) when no override
        # is injected — the real BlobStore is constructed on first
        # access and cached for subsequent calls.
        monkeypatch.setenv("HIVE_BLOBS_BUCKET", "lazy-init-bucket")
        from hive.blob_store import BlobStore

        first = storage.blob_store
        assert isinstance(first, BlobStore)
        assert storage.blob_store is first  # cached — not re-created

    def test_delete_memory_removes_s3_blob(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        big_value = "x" * (200 * 1024)
        m = Memory(key="big", value=big_value, owner_user_id="u1", owner_client_id="c1")
        storage.put_memory(m)
        assert ("u1", m.memory_id) in fake.objects

        storage.delete_memory(m.memory_id)
        assert ("u1", m.memory_id) not in fake.objects

    def test_delete_memory_s3_failure_is_nonfatal(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        big_value = "x" * (200 * 1024)
        m = Memory(key="big2", value=big_value, owner_user_id="u1", owner_client_id="c1")
        storage.put_memory(m)

        def _raise(owner, memory_id):
            raise RuntimeError("S3 unavailable")

        fake.delete = _raise
        # Should not raise — DynamoDB item is gone; S3 failure is logged
        assert storage.delete_memory(m.memory_id)
        assert storage.get_memory_by_key("big2") is None

    def test_delete_memories_by_tag_removes_blobs(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        big_value = "x" * (200 * 1024)
        m = Memory(
            key="bulk-big",
            value=big_value,
            tags=["bulk"],
            owner_user_id="u1",
            owner_client_id="c1",
        )
        storage.put_memory(m)
        assert ("u1", m.memory_id) in fake.objects

        storage.delete_memories_by_tag("bulk")
        assert ("u1", m.memory_id) not in fake.objects

    def test_update_text_large_memory_re_uploads_new_value(self, storage_with_blob_store):
        # Updating a text-large memory's value re-uploads to S3, overwriting
        # the old blob at the same key.
        storage, fake = storage_with_blob_store
        big_value = "x" * (200 * 1024)
        m = Memory(key="re-upload", value=big_value, owner_user_id="u1", owner_client_id="c1")
        storage.put_memory(m)
        assert ("u1", m.memory_id) in fake.objects
        assert fake.objects[("u1", m.memory_id)] == big_value.encode()

        updated_big = "y" * (200 * 1024)
        m.value = updated_big
        storage.put_memory(m)
        assert fake.objects[("u1", m.memory_id)] == updated_big.encode()

    def test_update_text_large_empty_value_skips_routing(self, storage_with_blob_store):
        # A text-large memory fetched from DynamoDB (value="") goes through
        # put_memory for metadata-only updates (e.g. tag changes). The router
        # must leave it untouched — the blob is already in S3.
        storage, fake = storage_with_blob_store
        big_value = "z" * (200 * 1024)
        m = Memory(
            key="skip-reupload",
            value=big_value,
            tags=["old"],
            owner_user_id="u1",
            owner_client_id="c1",
        )
        storage.put_memory(m)
        initial_calls = dict(fake.objects)

        # Simulate a tag-only update: fetch the memory (value="" in DynamoDB),
        # change tags, then put again. The router must not re-upload the blob.
        fetched = storage.get_memory_by_key("skip-reupload")
        assert fetched.value == ""  # inline value is empty for text-large
        fetched.tags = ["new"]
        storage.put_memory(fetched)
        # The S3 object is unchanged — the router skipped the empty-value memory
        assert fake.objects == initial_calls

    def test_fetch_blob_value_returns_full_text(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        big_value = "hello blob " * 10_000
        m = Memory(key="fetch-test", value=big_value, owner_user_id="u1", owner_client_id="c1")
        storage.put_memory(m)
        assert m.value_type == "text-large"

        fetched = storage.fetch_blob_value(m)
        assert fetched == big_value

    def test_fetch_blob_value_propagates_s3_error(self, storage_with_blob_store):
        storage, fake = storage_with_blob_store
        big_value = "x" * (200 * 1024)
        m = Memory(key="fetch-fail", value=big_value, owner_user_id="u1", owner_client_id="c1")
        storage.put_memory(m)

        def _raise(owner, memory_id):
            raise RuntimeError("S3 unavailable")

        fake.get = _raise
        with pytest.raises(RuntimeError, match="S3 unavailable"):
            storage.fetch_blob_value(m)


class TestMemoryVersionStorage:
    def test_list_versions_newest_first(self, storage):

        m = Memory(key="hist", value="v1", owner_client_id="c1")
        storage.put_memory(m)
        # two updates → two version snapshots
        m.value = "v2"
        storage.put_memory(m)
        m.value = "v3"
        storage.put_memory(m)
        versions = storage.list_memory_versions(m.memory_id)
        assert len(versions) == 2
        # newest first (ScanIndexForward=False)
        assert versions[0].value == "v2"
        assert versions[1].value == "v1"

    def test_get_memory_version_found(self, storage):
        m = Memory(key="gv", value="original", owner_client_id="c1")
        storage.put_memory(m)
        m.value = "updated"
        storage.put_memory(m)
        versions = storage.list_memory_versions(m.memory_id)
        assert len(versions) == 1
        fetched = storage.get_memory_version(m.memory_id, versions[0].version_timestamp)
        assert fetched is not None
        assert fetched.value == "original"

    def test_get_memory_version_not_found(self, storage):
        m = Memory(key="missing-v", value="v", owner_client_id="c1")
        storage.put_memory(m)
        result = storage.get_memory_version(m.memory_id, "nonexistent-ts")
        assert result is None

    def test_version_serialise_deserialise(self):
        from hive.models import MemoryVersion

        m = Memory(key="ser", value="old-val", tags=["t1"], owner_client_id="c1")
        v = MemoryVersion.from_memory(m)
        item = v.to_dynamo()
        restored = MemoryVersion.from_dynamo(item)
        assert restored.memory_id == v.memory_id
        assert restored.value == "old-val"
        assert restored.tags == ["t1"]

    def test_version_response_from_version(self):
        from hive.models import MemoryVersion, MemoryVersionResponse

        m = Memory(key="resp", value="v", tags=[], owner_client_id="c1")
        v = MemoryVersion.from_memory(m)
        resp = MemoryVersionResponse.from_version(v)
        assert resp.memory_id == v.memory_id
        assert resp.version_timestamp == v.version_timestamp
        assert resp.value == "v"


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestClientStorage:
    def test_put_and_get(self, storage):
        c = OAuthClient(client_name="Test")
        storage.put_client(c)
        result = storage.get_client(c.client_id)
        assert result is not None
        assert result.client_name == "Test"

    def test_delete(self, storage):
        c = OAuthClient(client_name="Delete Me")
        storage.put_client(c)
        assert storage.delete_client(c.client_id)
        assert storage.get_client(c.client_id) is None

    def test_delete_nonexistent_returns_false(self, storage):
        """Covers storage.py delete_client early-return False when item not found."""
        assert storage.delete_client("no-such-client") is False

    def test_list(self, storage):
        for i in range(3):
            storage.put_client(OAuthClient(client_name=f"App {i}"))
        clients, _ = storage.list_clients()
        assert len(clients) == 3

    def test_list_clients_with_cursor(self, storage):
        """Covers storage.py:220 — list_clients pagination cursor."""
        for i in range(4):
            storage.put_client(OAuthClient(client_name=f"PagApp {i}"))
        page1, cursor1 = storage.list_clients(limit=2)
        assert len(page1) == 2
        assert cursor1 is not None
        page2, cursor2 = storage.list_clients(limit=2, cursor=cursor1)
        assert len(page2) == 2


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


class TestTokenStorage:
    def test_create_and_get(self, storage):
        access, refresh = storage.create_token_pair("c1", "memories:read")
        fetched = storage.get_token(access.jti)
        assert fetched is not None
        assert fetched.client_id == "c1"
        assert fetched.token_type == TokenType.access

    def test_revoke(self, storage):
        access, _ = storage.create_token_pair("c1", "s")
        storage.revoke_token(access.jti)
        fetched = storage.get_token(access.jti)
        assert fetched is not None
        assert fetched.revoked


class TestAuthCodeAtomicRedemption:
    """#584 — OAuth authorization codes are single-use (RFC 6749 §10.5).

    `mark_auth_code_used` is the commit point of the redemption
    pipeline; it uses a conditional UpdateItem so concurrent
    redemptions of the same code can't both succeed.
    """

    def _create_code(self, storage) -> str:
        auth_code = storage.create_auth_code(
            client_id="c1",
            redirect_uri="https://app.example.com/cb",
            scope="memories:read",
            code_challenge="challenge",
        )
        return auth_code.code

    def test_first_redemption_flips_used(self, storage):
        from hive.storage import AuthCodeAlreadyUsed

        code = self._create_code(storage)
        storage.mark_auth_code_used(code)

        fetched = storage.get_auth_code(code)
        assert fetched is not None
        assert fetched.used is True

        # Sequential second call raises — the conditional write rejects
        # because `used = true` no longer matches the expected `false`.
        with pytest.raises(AuthCodeAlreadyUsed):
            storage.mark_auth_code_used(code)

    def test_missing_code_raises_already_used(self, storage):
        from hive.storage import AuthCodeAlreadyUsed

        # `attribute_exists(PK)` in the ConditionExpression guards
        # against forged codes — a caller cannot spin up new tokens
        # by passing a code that was never issued.
        with pytest.raises(AuthCodeAlreadyUsed):
            storage.mark_auth_code_used("never-issued-code")

    def test_update_uses_conditional_write_on_unused_state(self, storage):
        """The TOCTOU fix hinges on the conditional write — two
        redemptions that both read `used=False` can't both commit.

        Rather than spawning threads (moto's mock backend isn't a
        reliable concurrency harness), assert the wire-level contract:
        `mark_auth_code_used` issues an `UpdateItem` whose
        `ConditionExpression` requires `used = false` AND the item
        exists. DynamoDB's server-side serialisation of conditional
        writes is what actually enforces single-use; this test pins
        the condition so a future refactor can't silently drop it.
        """
        from unittest.mock import MagicMock

        code = self._create_code(storage)
        captured: dict[str, object] = {}

        original = storage.table.update_item

        def _spy(**kwargs: object) -> object:
            captured.update(kwargs)
            return original(**kwargs)

        storage.table = MagicMock(wraps=storage.table)
        storage.table.update_item.side_effect = _spy

        storage.mark_auth_code_used(code)

        assert "ConditionExpression" in captured
        cond = captured["ConditionExpression"]
        assert "attribute_exists(PK)" in cond
        assert "#u = :f" in cond
        assert captured["ExpressionAttributeNames"] == {"#u": "used"}
        assert captured["ExpressionAttributeValues"] == {":t": True, ":f": False}

    def test_unexpected_client_error_reraises(self, storage):
        """Only ConditionalCheckFailedException is translated to
        AuthCodeAlreadyUsed — every other ClientError bubbles up
        verbatim so accidental swallowing can't mask genuine AWS
        failures."""
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        throttled = ClientError(
            error_response={"Error": {"Code": "ProvisionedThroughputExceededException"}},
            operation_name="UpdateItem",
        )
        with (
            patch.object(storage.table, "update_item", side_effect=throttled),
            pytest.raises(ClientError),
        ):
            storage.mark_auth_code_used("any-code")


# ---------------------------------------------------------------------------
# Activity log tests
# ---------------------------------------------------------------------------


class TestActivityLog:
    def test_log_and_query(self, storage):
        event = ActivityEvent(
            event_type=EventType.memory_created,
            client_id="c1",
            metadata={"key": "x"},
        )
        storage.log_event(event)

        date_str = event.timestamp.strftime("%Y-%m-%d")
        events = storage.get_events_for_date(date_str)
        assert len(events) == 1
        assert events[0].event_id == event.event_id


class TestAuditLog:
    def test_log_audit_event_sets_ttl_from_retention_env(self, storage):
        from datetime import datetime, timezone

        event = ActivityEvent(
            event_type=EventType.memory_created,
            client_id="c1",
            metadata={"key": "k1"},
            timestamp=datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc),
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("HIVE_AUDIT_RETENTION_DAYS", "30")
            storage.log_audit_event(event)

        # Re-read the raw item to verify TTL was written.
        date_hour_str = event.timestamp.strftime("%Y-%m-%d#%H")
        resp = storage.table.get_item(
            Key={
                "PK": f"AUDIT#{date_hour_str}",
                "SK": f"{event.timestamp.isoformat()}#{event.event_id}",
            }
        )
        item = resp["Item"]
        assert "ttl" in item
        assert int(item["ttl"]) == int(event.timestamp.timestamp()) + 30 * 86400

    def test_audit_events_separate_from_activity_events(self, storage):
        """Writing to the audit log must not leak into the activity log."""
        event = ActivityEvent(
            event_type=EventType.memory_created,
            client_id="c1",
            metadata={},
        )
        storage.log_audit_event(event)
        # No activity log entry should exist
        assert storage.get_events_for_date(event.timestamp.strftime("%Y-%m-%d")) == []

    def test_get_audit_events_filters_by_client_id_and_event_type(self, storage):
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc)
        events = [
            ActivityEvent(event_type=EventType.memory_created, client_id="c1", timestamp=ts),
            ActivityEvent(event_type=EventType.memory_deleted, client_id="c1", timestamp=ts),
            ActivityEvent(event_type=EventType.memory_created, client_id="c2", timestamp=ts),
        ]
        for e in events:
            storage.log_audit_event(e)

        dates = [ts.strftime("%Y-%m-%d")]

        all_events = storage.get_audit_events_for_dates(dates)
        assert len(all_events) == 3

        c1_only = storage.get_audit_events_for_dates(dates, client_id="c1")
        assert {e.client_id for e in c1_only} == {"c1"}

        created_only = storage.get_audit_events_for_dates(dates, event_type="memory_created")
        assert {e.event_type.value for e in created_only} == {"memory_created"}

        combined = storage.get_audit_events_for_dates(
            dates, client_id="c1", event_type="memory_created"
        )
        assert len(combined) == 1
        assert combined[0].client_id == "c1"
        assert combined[0].event_type == EventType.memory_created

    def test_get_audit_events_limit_and_sort(self, storage):
        from datetime import datetime, timedelta, timezone

        base = datetime.now(timezone.utc).replace(microsecond=0)
        for i in range(5):
            e = ActivityEvent(
                event_type=EventType.memory_created,
                client_id="c",
                timestamp=base - timedelta(seconds=i),
            )
            storage.log_audit_event(e)

        dates = [base.strftime("%Y-%m-%d")]
        events = storage.get_audit_events_for_dates(dates, limit=3)
        assert len(events) == 3
        # Newest-first
        assert events[0].timestamp > events[1].timestamp > events[2].timestamp

    def test_hour_sharded_pk(self, storage):
        """Events must be written to LOG#{date}#{hour} partitions."""
        event = ActivityEvent(
            event_type=EventType.memory_recalled,
            client_id="c1",
            metadata={},
        )
        storage.log_event(event)

        item = storage.table.get_item(
            Key={
                "PK": f"LOG#{event.timestamp.strftime('%Y-%m-%d#%H')}",
                "SK": f"{event.timestamp.isoformat()}#{event.event_id}",
            }
        ).get("Item")
        assert item is not None
        assert item["event_id"] == event.event_id

    def test_get_events_for_dates(self, storage):
        """get_events_for_dates aggregates across multiple days."""
        from datetime import timedelta

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        for days_ago in range(3):
            ts = now - timedelta(days=days_ago)
            storage.log_event(
                ActivityEvent(
                    event_type=EventType.memory_created,
                    client_id="c1",
                    metadata={},
                    timestamp=ts,
                )
            )
        dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
        events = storage.get_events_for_dates(dates)
        assert len(events) == 3
        # Results are sorted newest-first
        assert events[0].timestamp >= events[-1].timestamp


# ---------------------------------------------------------------------------
# list_all_memories and count helpers
# ---------------------------------------------------------------------------


class TestListAllAndCounts:
    def test_list_all_memories(self, storage):
        storage.put_memory(Memory(key="x", value="1", owner_client_id="c1"))
        storage.put_memory(Memory(key="y", value="2", owner_client_id="c2"))
        all_mems, _ = storage.list_all_memories()
        keys = {m.key for m in all_mems}
        assert {"x", "y"}.issubset(keys)

    def test_list_all_memories_filtered_by_client(self, storage):
        storage.put_memory(Memory(key="a", value="1", owner_client_id="client-a"))
        storage.put_memory(Memory(key="b", value="2", owner_client_id="client-b"))
        mems, _ = storage.list_all_memories(client_id="client-a")
        assert all(m.owner_client_id == "client-a" for m in mems)
        assert any(m.key == "a" for m in mems)

    def test_count_memories(self, storage):
        assert storage.count_memories() == 0
        storage.put_memory(Memory(key="k1", value="v", owner_client_id="c1"))
        storage.put_memory(Memory(key="k2", value="v", owner_client_id="c1"))
        assert storage.count_memories() == 2

    def test_count_clients(self, storage):
        assert storage.count_clients() == 0
        from hive.models import OAuthClient

        storage.put_client(OAuthClient(client_name="A"))
        storage.put_client(OAuthClient(client_name="B"))
        assert storage.count_clients() == 2

    def test_count_users(self, storage):
        assert storage.count_users() == 0
        from hive.models import User

        storage.put_user(User(email="a@x.com", display_name="A"))
        storage.put_user(User(email="b@x.com", display_name="B"))
        assert storage.count_users() == 2

    def test_sum_storage_bytes_empty(self, storage):
        assert storage.sum_storage_bytes() == 0

    def test_sum_storage_bytes_sums_all(self, storage):
        # put_memory calls _route_large_value which sets size_bytes = len(encoded)
        m1 = Memory(key="s1", value="hi", owner_client_id="c1")  # 2 bytes
        m2 = Memory(key="s2", value="bye", owner_client_id="c1")  # 3 bytes
        storage.put_memory(m1)
        storage.put_memory(m2)
        assert storage.sum_storage_bytes() == 5

    def test_sum_storage_bytes_filtered_by_user(self, storage):
        m1 = Memory(key="su1", value="ab", owner_client_id="c1", owner_user_id="user-1")  # 2 bytes
        m2 = Memory(key="su2", value="xyz", owner_client_id="c1", owner_user_id="user-2")  # 3 bytes
        storage.put_memory(m1)
        storage.put_memory(m2)
        assert storage.sum_storage_bytes(owner_user_id="user-1") == 2
        assert storage.sum_storage_bytes() == 5

    def test_sum_storage_bytes_treats_missing_size_bytes_as_zero(self, storage):
        # Insert a legacy item directly (no size_bytes attribute) to simulate pre-migration data.
        storage.table.put_item(
            Item={
                "PK": "MEMORY#legacy-test",
                "SK": "META",
                "memory_id": "legacy-test",
                "owner_client_id": "c1",
                "key": "legacy-key",
                "value": "v",
                "value_type": "text",
                "tags": [],
            }
        )
        assert storage.sum_storage_bytes() == 0

    def test_sum_storage_bytes_paginates(self, storage):
        from unittest.mock import patch

        page1 = {
            "Items": [{"size_bytes": 10}],
            "LastEvaluatedKey": {"PK": "MEMORY#x", "SK": "META"},
        }
        page2 = {"Items": [{"size_bytes": 20}]}
        with patch.object(storage.table, "scan", side_effect=[page1, page2]) as mock_scan:
            total = storage.sum_storage_bytes()
        assert total == 30
        assert mock_scan.call_count == 2


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_list_all_memories_cursor(self, storage):
        for i in range(5):
            storage.put_memory(Memory(key=f"pg-{i}", value="v", owner_client_id="c1"))

        page1, cursor1 = storage.list_all_memories(limit=3)
        assert len(page1) == 3
        assert cursor1 is not None

        page2, cursor2 = storage.list_all_memories(limit=3, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is None

        all_keys = {m.key for m in page1 + page2}
        assert all_keys == {f"pg-{i}" for i in range(5)}

    def test_list_memories_by_tag_cursor(self, storage):
        for i in range(4):
            storage.put_memory(
                Memory(key=f"tpg-{i}", value="v", tags=["page"], owner_client_id="c1")
            )

        page1, cursor1 = storage.list_memories_by_tag("page", limit=2)
        assert len(page1) == 2
        assert cursor1 is not None

        page2, cursor2 = storage.list_memories_by_tag("page", limit=2, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is None

    def test_list_memories_by_tag_owner_user_id_filters_cross_user(self, storage):
        """Cross-user memories sharing a tag must not be returned when owner_user_id is set."""
        from hive.models import OAuthClient

        client_a = OAuthClient(client_name="User-A Client", owner_user_id="user-a")
        client_b = OAuthClient(client_name="User-B Client", owner_user_id="user-b")
        storage.put_client(client_a)
        storage.put_client(client_b)

        storage.put_memory(
            Memory(
                key="a-mem",
                value="user-a value",
                tags=["shared"],
                owner_client_id=client_a.client_id,
                owner_user_id="user-a",
            )
        )
        storage.put_memory(
            Memory(
                key="b-mem",
                value="user-b value",
                tags=["shared"],
                owner_client_id=client_b.client_id,
                owner_user_id="user-b",
            )
        )

        # User A only sees their own memory
        mems_a, _ = storage.list_memories_by_tag("shared", owner_user_id="user-a")
        assert [m.key for m in mems_a] == ["a-mem"]

        # User B only sees their own memory
        mems_b, _ = storage.list_memories_by_tag("shared", owner_user_id="user-b")
        assert [m.key for m in mems_b] == ["b-mem"]

    def test_list_memories_by_tag_owner_user_id_cross_client_within_user(self, storage):
        """Within-user cross-client sharing: both clients of the same user see all memories."""
        from hive.models import OAuthClient

        client_1 = OAuthClient(client_name="User-A Client-1", owner_user_id="user-a")
        client_2 = OAuthClient(client_name="User-A Client-2", owner_user_id="user-a")
        storage.put_client(client_1)
        storage.put_client(client_2)

        storage.put_memory(
            Memory(
                key="from-c1",
                value="v1",
                tags=["work"],
                owner_client_id=client_1.client_id,
                owner_user_id="user-a",
            )
        )
        storage.put_memory(
            Memory(
                key="from-c2",
                value="v2",
                tags=["work"],
                owner_client_id=client_2.client_id,
                owner_user_id="user-a",
            )
        )

        mems, _ = storage.list_memories_by_tag("work", owner_user_id="user-a")
        assert {m.key for m in mems} == {"from-c1", "from-c2"}

    def test_list_memories_by_tag_no_owner_filter_returns_all(self, storage):
        """When owner_user_id is None, all memories matching the tag are returned."""
        storage.put_memory(
            Memory(
                key="xa", value="v", tags=["open"], owner_client_id="c-x", owner_user_id="user-x"
            )
        )
        storage.put_memory(
            Memory(
                key="ya", value="v", tags=["open"], owner_client_id="c-y", owner_user_id="user-y"
            )
        )

        mems, _ = storage.list_memories_by_tag("open")
        assert {m.key for m in mems} == {"xa", "ya"}

    def test_invalid_cursor_raises(self, storage):
        with pytest.raises(ValueError, match="Invalid pagination cursor"):
            storage.list_all_memories(cursor="not-valid-base64!!!")

    def test_list_all_memories_follows_scan_pages(self, storage):
        """Covers the scan-loop continuation path when DynamoDB returns LastEvaluatedKey."""
        from unittest.mock import patch

        mems = [Memory(key=f"paged-{i}", value="v", owner_client_id="c1") for i in range(3)]
        for m in mems:
            storage.put_memory(m)

        fake_lek = {"PK": f"MEMORY#{mems[0].memory_id}", "SK": "META"}
        page1_items = [mems[0].to_dynamo_meta()]
        page2_items = [mems[1].to_dynamo_meta(), mems[2].to_dynamo_meta()]
        responses = iter(
            [
                {"Items": page1_items, "LastEvaluatedKey": fake_lek},
                {"Items": page2_items},
            ]
        )

        with patch.object(storage.table, "scan", side_effect=lambda **_kw: next(responses)):
            result, cursor = storage.list_all_memories(limit=5)

        assert len(result) == 3
        assert cursor is None

    def test_list_clients_follows_scan_pages(self, storage):
        """Covers the scan-loop continuation path in list_clients."""
        from unittest.mock import patch

        from hive.models import OAuthClient

        clients = [OAuthClient(client_name=f"C{i}") for i in range(3)]
        for c in clients:
            storage.put_client(c)

        fake_lek = {"PK": f"CLIENT#{clients[0].client_id}", "SK": "META"}
        page1_items = [clients[0].to_dynamo()]
        page2_items = [clients[1].to_dynamo(), clients[2].to_dynamo()]
        responses = iter(
            [
                {"Items": page1_items, "LastEvaluatedKey": fake_lek},
                {"Items": page2_items},
            ]
        )

        with patch.object(storage.table, "scan", side_effect=lambda **_kw: next(responses)):
            result, cursor = storage.list_clients(limit=5)

        assert len(result) == 3
        assert cursor is None

    def test_activity_limit_respected(self, storage):
        from datetime import date

        from hive.models import ActivityEvent, EventType

        today = date.today().isoformat()
        for _i in range(10):
            storage.log_event(
                ActivityEvent(event_type=EventType.memory_recalled, client_id="c1", metadata={})
            )
        events = storage.get_events_for_dates([today], limit=5)
        assert len(events) <= 5


# ---------------------------------------------------------------------------
# Pending auth tests
# ---------------------------------------------------------------------------


class TestPendingAuthStorage:
    def test_create_and_get(self, storage):
        pending = storage.create_pending_auth(
            client_id="c1",
            redirect_uri="https://app.example.com/cb",
            scope="memories:read",
            code_challenge="abc123",
            code_challenge_method="S256",
            original_state="xyz",
        )
        assert pending.state
        fetched = storage.get_pending_auth(pending.state)
        assert fetched is not None
        assert fetched.client_id == "c1"
        assert fetched.scope == "memories:read"
        assert fetched.original_state == "xyz"

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_pending_auth("no-such-state") is None

    def test_delete_pending_auth(self, storage):
        pending = storage.create_pending_auth(
            client_id="c1",
            redirect_uri="https://app.example.com/cb",
            scope="memories:read",
            code_challenge="abc",
            code_challenge_method="S256",
            original_state="",
        )
        storage.delete_pending_auth(pending.state)
        assert storage.get_pending_auth(pending.state) is None


# ---------------------------------------------------------------------------
# User storage
# ---------------------------------------------------------------------------


class TestUserStorage:
    def _user(self, email: str = "alice@example.com", role: str = "user") -> User:
        return User(email=email, display_name="Alice", role=role)

    def test_put_and_get_by_id(self, storage):
        u = self._user()
        storage.put_user(u)
        fetched = storage.get_user_by_id(u.user_id)
        assert fetched is not None
        assert fetched.email == u.email
        assert fetched.role == u.role

    def test_get_nonexistent_by_id_returns_none(self, storage):
        assert storage.get_user_by_id("no-such-id") is None

    def test_get_by_email(self, storage):
        u = self._user(email="bob@example.com")
        storage.put_user(u)
        fetched = storage.get_user_by_email("bob@example.com")
        assert fetched is not None
        assert fetched.user_id == u.user_id

    def test_get_nonexistent_by_email_returns_none(self, storage):
        assert storage.get_user_by_email("nobody@example.com") is None

    def test_delete(self, storage):
        u = self._user()
        storage.put_user(u)
        assert storage.delete_user(u.user_id) is True
        assert storage.get_user_by_id(u.user_id) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_user("no-such-id") is False

    def test_update_user_role(self, storage):
        u = self._user()
        u.role = "user"
        storage.put_user(u)
        assert storage.update_user_role(u.user_id, "admin") is True
        assert storage.get_user_by_id(u.user_id).role == "admin"

    def test_update_user_role_nonexistent_returns_false(self, storage):
        assert storage.update_user_role("no-such-id", "admin") is False

    def test_update_user_limits_sets_both_fields(self, storage):
        u = self._user()
        storage.put_user(u)
        assert storage.update_user_limits(u.user_id, 100, 5 * 1024 * 1024) is True
        fetched = storage.get_user_by_id(u.user_id)
        assert fetched.memory_limit == 100
        assert fetched.storage_bytes_limit == 5 * 1024 * 1024

    def test_update_user_limits_clears_fields_when_none(self, storage):
        u = User(
            email="limtest@example.com", display_name="L", memory_limit=50, storage_bytes_limit=999
        )
        storage.put_user(u)
        assert storage.update_user_limits(u.user_id, None, None) is True
        fetched = storage.get_user_by_id(u.user_id)
        assert fetched.memory_limit is None
        assert fetched.storage_bytes_limit is None

    def test_update_user_limits_nonexistent_returns_false(self, storage):
        assert storage.update_user_limits("no-such-id", 100, None) is False

    def test_update_user_limits_conditional_check_failure_returns_false(self, storage):
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        u = self._user()
        storage.put_user(u)
        error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}}, "UpdateItem"
        )
        with patch.object(storage.table, "update_item", side_effect=error):
            assert storage.update_user_limits(u.user_id, 50, None) is False

    def test_update_user_limits_unexpected_client_error_propagates(self, storage):
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        u = self._user()
        storage.put_user(u)
        error = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": ""}},
            "UpdateItem",
        )
        with (
            patch.object(storage.table, "update_item", side_effect=error),
            pytest.raises(ClientError),
        ):
            storage.update_user_limits(u.user_id, 50, None)

    def test_list_users(self, storage):
        storage.put_user(self._user("a@example.com"))
        storage.put_user(self._user("b@example.com"))
        users, cursor = storage.list_users()
        emails = {u.email for u in users}
        assert {"a@example.com", "b@example.com"}.issubset(emails)
        assert cursor is None

    def test_list_users_pagination(self, storage):
        for i in range(5):
            storage.put_user(self._user(f"user{i}@example.com"))
        page1, cursor1 = storage.list_users(limit=3)
        assert len(page1) == 3
        assert cursor1 is not None
        page2, cursor2 = storage.list_users(limit=3, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is None

    def test_list_users_follows_scan_pages(self, storage):
        """Covers the scan-loop continuation path in list_users."""
        from unittest.mock import patch

        users = [User(email=f"u{i}@example.com", display_name=f"U{i}") for i in range(3)]
        for u in users:
            storage.put_user(u)

        fake_lek = {"PK": f"USER#{users[0].user_id}", "SK": "META"}
        page1_items = [users[0].to_dynamo()]
        page2_items = [users[1].to_dynamo(), users[2].to_dynamo()]
        responses = iter(
            [
                {"Items": page1_items, "LastEvaluatedKey": fake_lek},
                {"Items": page2_items},
            ]
        )

        with patch.object(storage.table, "scan", side_effect=lambda **_kw: next(responses)):
            result, cursor = storage.list_users(limit=5)

        assert len(result) == 3
        assert cursor is None

    def test_user_response_from_user(self):
        u = User(email="x@example.com", display_name="X", role="admin")
        resp = UserResponse.from_user(u)
        assert resp.user_id == u.user_id
        assert resp.email == u.email
        assert resp.display_name == u.display_name
        assert resp.role == "admin"


# ---------------------------------------------------------------------------
# MgmtPendingState storage
# ---------------------------------------------------------------------------


class TestMgmtPendingStateStorage:
    def test_create_and_get(self, storage):
        pending = storage.create_mgmt_pending_state()
        assert pending.state
        fetched = storage.get_mgmt_pending_state(pending.state)
        assert fetched is not None
        assert fetched.state == pending.state

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_mgmt_pending_state("no-such-state") is None

    def test_delete(self, storage):
        pending = storage.create_mgmt_pending_state()
        storage.delete_mgmt_pending_state(pending.state)
        assert storage.get_mgmt_pending_state(pending.state) is None


# ---------------------------------------------------------------------------
# owner_user_id filtering
# ---------------------------------------------------------------------------


class TestOwnerUserIdFiltering:
    def test_list_all_memories_filtered_by_user(self, storage):
        storage.put_memory(Memory(key="a", value="1", owner_client_id="c1", owner_user_id="user-1"))
        storage.put_memory(Memory(key="b", value="2", owner_client_id="c2", owner_user_id="user-2"))
        mems, _ = storage.list_all_memories(owner_user_id="user-1")
        assert len(mems) == 1
        assert mems[0].key == "a"

    def test_list_clients_filtered_by_user(self, storage):
        storage.put_client(OAuthClient(client_name="A", owner_user_id="user-1"))
        storage.put_client(OAuthClient(client_name="B", owner_user_id="user-2"))
        clients, _ = storage.list_clients(owner_user_id="user-1")
        assert len(clients) == 1
        assert clients[0].client_name == "A"

    def test_count_memories_filtered_by_user(self, storage):
        storage.put_memory(Memory(key="x", value="v", owner_client_id="c1", owner_user_id="user-1"))
        storage.put_memory(Memory(key="y", value="v", owner_client_id="c1", owner_user_id="user-2"))
        assert storage.count_memories(owner_user_id="user-1") == 1
        assert storage.count_memories() == 2

    def test_count_clients_filtered_by_user(self, storage):
        storage.put_client(OAuthClient(client_name="C1", owner_user_id="user-1"))
        storage.put_client(OAuthClient(client_name="C2", owner_user_id="user-2"))
        assert storage.count_clients(owner_user_id="user-1") == 1
        assert storage.count_clients() == 2


# ---------------------------------------------------------------------------
# hydrate_memory_ids
# ---------------------------------------------------------------------------


class TestHydrateMemoryIds:
    def test_returns_memory_and_score_pairs(self, storage):
        m = Memory(key="h1", value="v1", owner_client_id="c1")
        storage.put_memory(m)
        pairs = [(m.memory_id, 0.95)]
        result = storage.hydrate_memory_ids(pairs)
        assert len(result) == 1
        mem, score = result[0]
        assert mem.key == "h1"
        assert score == 0.95

    def test_skips_missing_memory_ids(self, storage):
        m = Memory(key="h2", value="v2", owner_client_id="c1")
        storage.put_memory(m)
        pairs = [("nonexistent-id", 0.8), (m.memory_id, 0.7)]
        result = storage.hydrate_memory_ids(pairs)
        assert len(result) == 1
        assert result[0][1] == 0.7

    def test_returns_empty_for_empty_input(self, storage):
        assert storage.hydrate_memory_ids([]) == []

    def test_preserves_order(self, storage):
        m1 = Memory(key="ord-a", value="v", owner_client_id="c")
        m2 = Memory(key="ord-b", value="v", owner_client_id="c")
        storage.put_memory(m1)
        storage.put_memory(m2)
        pairs = [(m1.memory_id, 0.9), (m2.memory_id, 0.5)]
        result = storage.hydrate_memory_ids(pairs)
        assert result[0][0].key == "ord-a"
        assert result[1][0].key == "ord-b"


# ---------------------------------------------------------------------------
# API Key storage
# ---------------------------------------------------------------------------


class TestApiKeyStorage:
    def _key(self, owner_user_id: str = "u1", name: str = "test") -> ApiKey:
        return ApiKey(owner_user_id=owner_user_id, name=name, key_hash="hash-" + name)

    def test_put_and_get_by_id(self, storage):
        k = self._key()
        storage.put_api_key(k)
        fetched = storage.get_api_key_by_id(k.key_id)
        assert fetched is not None
        assert fetched.key_id == k.key_id
        assert fetched.name == "test"

    def test_get_by_id_not_found(self, storage):
        assert storage.get_api_key_by_id("no-such-key") is None

    def test_get_by_hash(self, storage):
        k = self._key()
        storage.put_api_key(k)
        found = storage.get_api_key_by_hash("hash-test")
        assert found is not None
        assert found.key_id == k.key_id

    def test_get_by_hash_not_found(self, storage):
        assert storage.get_api_key_by_hash("nonexistent-hash") is None

    def test_list_for_user(self, storage):
        k1 = self._key("u1", "key1")
        k2 = self._key("u1", "key2")
        k3 = self._key("u2", "other")
        for k in (k1, k2, k3):
            storage.put_api_key(k)
        result = storage.list_api_keys_for_user("u1")
        names = {k.name for k in result}
        assert "key1" in names
        assert "key2" in names
        assert "other" not in names

    def test_list_for_user_empty(self, storage):
        assert storage.list_api_keys_for_user("no-such-user") == []

    def test_delete(self, storage):
        k = self._key()
        storage.put_api_key(k)
        assert storage.delete_api_key(k.key_id) is True
        assert storage.get_api_key_by_id(k.key_id) is None

    def test_delete_nonexistent(self, storage):
        assert storage.delete_api_key("no-such-key") is False


# ---------------------------------------------------------------------------
# Bulk memory operations
# ---------------------------------------------------------------------------


class TestBulkMemoryOperations:
    def test_delete_memories_by_tag_returns_count(self, storage):
        m1 = Memory(key="a", value="1", tags=["bulk"], owner_client_id="c1", owner_user_id="u1")
        m2 = Memory(key="b", value="2", tags=["bulk"], owner_client_id="c1", owner_user_id="u1")
        m3 = Memory(key="c", value="3", tags=["other"], owner_client_id="c1", owner_user_id="u1")
        for m in [m1, m2, m3]:
            storage.put_memory(m)
        deleted = storage.delete_memories_by_tag("bulk")
        assert deleted == 2
        assert storage.get_memory_by_key("a") is None
        assert storage.get_memory_by_key("b") is None
        assert storage.get_memory_by_key("c") is not None

    def test_delete_memories_by_tag_with_owner_filter(self, storage):
        m1 = Memory(key="x", value="1", tags=["t"], owner_client_id="c1", owner_user_id="u1")
        m2 = Memory(key="y", value="2", tags=["t"], owner_client_id="c2", owner_user_id="u2")
        for m in [m1, m2]:
            storage.put_memory(m)
        deleted = storage.delete_memories_by_tag("t", owner_user_id="u1")
        assert deleted == 1
        assert storage.get_memory_by_key("x") is None
        assert storage.get_memory_by_key("y") is not None

    def test_delete_memories_by_tag_empty(self, storage):
        assert storage.delete_memories_by_tag("no-such-tag") == 0

    def test_iter_all_memories_no_filter(self, storage):
        for i in range(3):
            storage.put_memory(Memory(key=f"k{i}", value=f"v{i}", owner_client_id="c1"))
        result = list(storage.iter_all_memories())
        assert len(result) == 3

    def test_iter_all_memories_with_tag(self, storage):
        m1 = Memory(key="tagged", value="1", tags=["export"], owner_client_id="c1")
        m2 = Memory(key="untagged", value="2", tags=[], owner_client_id="c1")
        storage.put_memory(m1)
        storage.put_memory(m2)
        result = list(storage.iter_all_memories(tag="export"))
        assert len(result) == 1
        assert result[0].key == "tagged"

    def test_iter_all_memories_with_owner_filter(self, storage):
        m1 = Memory(key="mine", value="1", owner_client_id="c1", owner_user_id="u1")
        m2 = Memory(key="theirs", value="2", owner_client_id="c2", owner_user_id="u2")
        storage.put_memory(m1)
        storage.put_memory(m2)
        result = list(storage.iter_all_memories(owner_user_id="u1"))
        assert len(result) == 1
        assert result[0].key == "mine"

    def test_iter_all_memories_tag_and_owner_filter(self, storage):
        m1 = Memory(key="a", value="1", tags=["t"], owner_client_id="c1", owner_user_id="u1")
        m2 = Memory(key="b", value="2", tags=["t"], owner_client_id="c2", owner_user_id="u2")
        storage.put_memory(m1)
        storage.put_memory(m2)
        result = list(storage.iter_all_memories(tag="t", owner_user_id="u2"))
        assert len(result) == 1
        assert result[0].key == "b"

    def test_iter_all_memories_follows_scan_pages(self, storage):
        """iter_all_memories should follow DynamoDB scan pages via ExclusiveStartKey."""

        memories = [Memory(key=f"page-{i}", value=f"v{i}", owner_client_id="c1") for i in range(3)]
        for m in memories:
            storage.put_memory(m)

        # Capture calls to prove pagination works by using real storage
        # (moto handles pagination internally, so just verify all items returned)
        result = list(storage.iter_all_memories())
        assert len(result) == 3

    def test_iter_all_memories_multi_page(self, storage):
        """iter_all_memories handles scan responses with ExclusiveStartKey."""
        from unittest.mock import patch

        from hive.models import Memory as _Memory

        m1 = _Memory(key="page1", value="v1", owner_client_id="c1")
        m1_item = m1.to_dynamo_meta()

        page1_resp = {
            "Items": [m1_item],
            "LastEvaluatedKey": {"PK": "MEMORY#page1", "SK": "META"},
        }
        m2 = _Memory(key="page2", value="v2", owner_client_id="c1")
        m2_item = m2.to_dynamo_meta()
        page2_resp = {"Items": [m2_item]}

        with patch.object(storage.table, "scan", side_effect=[page1_resp, page2_resp]):
            result = list(storage.iter_all_memories())

        assert len(result) == 2
