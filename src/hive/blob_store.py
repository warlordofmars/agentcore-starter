# Copyright (c) 2026 John Carter. All rights reserved.
"""
Blob store for Hive — S3-backed storage for memories that exceed the
DynamoDB 400 KB item limit (or are non-text by construction).

DynamoDB is the authoritative index — every memory has a META item.
When the inline value would overflow DynamoDB, or the caller passes a
non-text ``value_type``, the content is stored in S3 under
``s3://{bucket}/{owner}/{memory_id}`` and a pointer is kept in the
META item as ``s3_uri``.

The 100 KB inline/S3 threshold sits well under DynamoDB's 400 KB
per-item cap so the headers, tag list, timestamps etc. never tip the
item over.

All operations are best-effort at the protocol level — they raise on
hard failures so the caller can surface a meaningful error rather
than silently losing data.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import boto3

from hive.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client

logger = get_logger("hive.blob_store")

# Above this size, text values get promoted from inline `value` to
# S3-backed `text-large`. Chosen well under DynamoDB's 400 KB item
# cap so the rest of the META item (key, tags, timestamps, GSI keys)
# never tips the total over.
INLINE_TEXT_THRESHOLD_BYTES = 100 * 1024

# Hard cap enforced by the ``remember_blob`` tool at upload time. 10
# MB matches Lambda's binary-invoke payload ceiling with headroom for
# MCP-protocol framing.
MAX_BLOB_SIZE_BYTES = 10 * 1024 * 1024


class BlobStore:
    """S3 wrapper for large-memory storage."""

    def __init__(
        self,
        bucket_name: str | None = None,
        region: str | None = None,
        _s3_client: Any = None,
    ) -> None:
        # Read env at call time so tests can override after import.
        resolved = bucket_name or os.environ.get("HIVE_BLOBS_BUCKET", "")
        if not resolved.strip():
            raise ValueError(
                "BlobStore requires a non-empty bucket name; pass `bucket_name` "
                "or set the HIVE_BLOBS_BUCKET environment variable."
            )
        self._bucket = resolved
        region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._s3: S3Client = _s3_client or boto3.client("s3", region_name=region)

    @property
    def bucket(self) -> str:
        return self._bucket

    def _key(self, owner: str, memory_id: str) -> str:
        """Object key layout: ``{owner}/{memory_id}``.

        ``owner`` is the workspace id once #482 lands; until then
        callers pass the user id (falling back to client id for
        pre-user-migration memories).
        """
        return f"{owner}/{memory_id}"

    def put(
        self,
        owner: str,
        memory_id: str,
        body: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> str:
        """Upload ``body`` and return the ``s3://`` URI."""
        key = self._key(owner, memory_id)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return f"s3://{self._bucket}/{key}"

    def get(self, owner: str, memory_id: str) -> bytes:
        """Fetch the body at ``{owner}/{memory_id}`` as bytes."""
        key = self._key(owner, memory_id)
        resp = self._s3.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def delete(self, owner: str, memory_id: str) -> None:
        """Delete the object at ``{owner}/{memory_id}``.

        Missing objects don't raise — S3 ``delete_object`` is
        idempotent and we already log the action for audit.
        """
        key = self._key(owner, memory_id)
        self._s3.delete_object(Bucket=self._bucket, Key=key)
        logger.info(
            "blob_delete",
            extra={"bucket": self._bucket, "key": key},
        )
