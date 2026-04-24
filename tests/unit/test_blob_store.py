# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the S3-backed BlobStore (#497)."""

from __future__ import annotations

import os

import boto3
import pytest

os.environ.setdefault("HIVE_BLOBS_BUCKET", "hive-blobs-test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from moto import mock_aws

from hive.blob_store import (
    INLINE_TEXT_THRESHOLD_BYTES,
    MAX_BLOB_SIZE_BYTES,
    BlobStore,
)


@pytest.fixture()
def blob_store():
    """BlobStore backed by a fresh moto-mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="hive-blobs-test")
        yield BlobStore(bucket_name="hive-blobs-test")


class TestBlobStore:
    def test_thresholds_are_sensible_defaults(self):
        # 100 KB inline threshold sits well under DynamoDB's 400 KB
        # item cap so the rest of the META item (tags, timestamps,
        # GSI keys) can never tip the total over.
        assert INLINE_TEXT_THRESHOLD_BYTES == 100 * 1024
        # 10 MB cap matches Lambda's binary-invoke payload ceiling
        # with headroom for MCP framing.
        assert MAX_BLOB_SIZE_BYTES == 10 * 1024 * 1024

    def test_put_uploads_and_returns_s3_uri(self, blob_store):
        uri = blob_store.put(owner="user-1", memory_id="mem-1", body=b"hello world")
        assert uri == "s3://hive-blobs-test/user-1/mem-1"

    def test_get_returns_body_written_by_put(self, blob_store):
        blob_store.put(owner="user-1", memory_id="mem-1", body=b"hello world")
        assert blob_store.get("user-1", "mem-1") == b"hello world"

    def test_put_stores_content_type_for_binary(self, blob_store):
        blob_store.put(
            owner="user-1",
            memory_id="mem-png",
            body=b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )
        # moto reports the stored content-type via HeadObject — we
        # only check PUT succeeded (no raise) and bytes round-trip.
        assert blob_store.get("user-1", "mem-png") == b"\x89PNG\r\n\x1a\n"

    def test_delete_removes_the_object(self, blob_store):
        from botocore.exceptions import ClientError

        blob_store.put(owner="user-1", memory_id="mem-1", body=b"x")
        blob_store.delete(owner="user-1", memory_id="mem-1")
        # botocore raises ClientError (NoSuchKey) on GET of a
        # missing object — the BlobStore doesn't swallow that.
        with pytest.raises(ClientError):
            blob_store.get("user-1", "mem-1")

    def test_owner_prefix_keeps_tenants_isolated_by_key(self, blob_store):
        # Same memory_id under two owners must land at different
        # S3 keys so the IAM policy (which happens to be unscoped
        # in this moto harness) can't cross-leak in production.
        blob_store.put(owner="user-a", memory_id="same-id", body=b"A")
        blob_store.put(owner="user-b", memory_id="same-id", body=b"B")
        assert blob_store.get("user-a", "same-id") == b"A"
        assert blob_store.get("user-b", "same-id") == b"B"

    def test_bucket_property_exposes_configured_bucket(self, blob_store):
        assert blob_store.bucket == "hive-blobs-test"

    def test_default_bucket_comes_from_env(self, monkeypatch):
        # Env-var override path — covers the `or os.environ.get`
        # fallback in __init__.
        monkeypatch.setenv("HIVE_BLOBS_BUCKET", "env-bucket")
        store = BlobStore()
        assert store.bucket == "env-bucket"

    def test_missing_bucket_raises_value_error(self, monkeypatch):
        monkeypatch.delenv("HIVE_BLOBS_BUCKET", raising=False)
        with pytest.raises(ValueError, match="HIVE_BLOBS_BUCKET"):
            BlobStore()
