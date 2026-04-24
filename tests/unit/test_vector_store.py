# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for the VectorStore class.

All AWS calls are mocked via unittest.mock — no real S3 Vectors or Bedrock
clients are created.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("HIVE_VECTORS_BUCKET", "test-bucket")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from hive.models import Memory
from hive.vector_store import VectorIndexNotFoundError, VectorStore


def _make_bedrock_client(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock Bedrock client that returns the given embedding."""
    if embedding is None:
        embedding = [0.1] * 1024
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({"embedding": embedding}).encode()
    client = MagicMock()
    client.invoke_model.return_value = {"body": body_mock}
    return client


def _make_s3v_client() -> MagicMock:
    """Return a mock S3 Vectors client with standard exception classes."""
    client = MagicMock()
    # Attach exception classes as attributes (boto3 style)
    client.exceptions.ConflictException = type("ConflictException", (Exception,), {})
    client.exceptions.NotFoundException = type("NotFoundException", (Exception,), {})
    return client


def _make_memory(**kwargs) -> Memory:
    defaults = {
        "key": "test-key",
        "value": "test value",
        "tags": ["t1"],
        "owner_client_id": "client-abc",
    }
    defaults.update(kwargs)
    return Memory(**defaults)


# ---------------------------------------------------------------------------
# VectorStore._embed
# ---------------------------------------------------------------------------


class TestEmbed:
    def test_calls_bedrock_with_correct_payload(self):
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=MagicMock(), _bedrock_client=bedrock)
        result = vs._embed("hello world")
        call_kwargs = bedrock.invoke_model.call_args
        body = json.loads(call_kwargs.kwargs["body"])
        assert body["inputText"] == "hello world"
        assert body["dimensions"] == 1024
        assert body["normalize"] is True
        assert len(result) == 1024

    def test_returns_embedding_list(self):
        embedding = [float(i) / 1024 for i in range(1024)]
        bedrock = _make_bedrock_client(embedding)
        vs = VectorStore(bucket_name="b", _s3v_client=MagicMock(), _bedrock_client=bedrock)
        assert vs._embed("text") == embedding


# ---------------------------------------------------------------------------
# VectorStore._ensure_index
# ---------------------------------------------------------------------------


class TestEnsureIndex:
    def test_creates_index_on_first_call(self):
        s3v = _make_s3v_client()
        vs = VectorStore(bucket_name="mybucket", _s3v_client=s3v, _bedrock_client=MagicMock())
        name = vs._ensure_index("client-123")
        assert name == "client-client-123"
        s3v.create_index.assert_called_once_with(
            vectorBucketName="mybucket",
            indexName="client-client-123",
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
        )

    def test_swallows_conflict_exception(self):
        s3v = _make_s3v_client()
        s3v.create_index.side_effect = s3v.exceptions.ConflictException("already exists")
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=MagicMock())
        # Must not raise
        name = vs._ensure_index("abc")
        assert name == "client-abc"


# ---------------------------------------------------------------------------
# VectorStore.upsert_memory
# ---------------------------------------------------------------------------


class TestUpsertMemory:
    def test_calls_put_vectors(self):
        s3v = _make_s3v_client()
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="bkt", _s3v_client=s3v, _bedrock_client=bedrock)
        m = _make_memory()
        vs.upsert_memory(m)
        s3v.put_vectors.assert_called_once()
        call_kwargs = s3v.put_vectors.call_args.kwargs
        assert call_kwargs["vectorBucketName"] == "bkt"
        assert call_kwargs["indexName"] == f"client-{m.owner_client_id}"
        vectors = call_kwargs["vectors"]
        assert len(vectors) == 1
        assert vectors[0]["key"] == m.memory_id

    def test_text_includes_key_and_value(self):
        s3v = _make_s3v_client()
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=bedrock)
        m = _make_memory(key="mykey", value="myvalue")
        vs.upsert_memory(m)
        embedded_text = bedrock.invoke_model.call_args.kwargs["body"]
        assert "mykey" in embedded_text
        assert "myvalue" in embedded_text

    def test_swallows_exceptions_best_effort(self):
        s3v = _make_s3v_client()
        s3v.put_vectors.side_effect = RuntimeError("network error")
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=bedrock)
        # Must not raise
        vs.upsert_memory(_make_memory())


# ---------------------------------------------------------------------------
# VectorStore.delete_memory
# ---------------------------------------------------------------------------


class TestDeleteMemory:
    def test_calls_delete_vectors(self):
        s3v = _make_s3v_client()
        vs = VectorStore(bucket_name="bkt", _s3v_client=s3v, _bedrock_client=MagicMock())
        vs.delete_memory("mem-id-123", "client-xyz")
        s3v.delete_vectors.assert_called_once_with(
            vectorBucketName="bkt",
            indexName="client-client-xyz",
            keys=["mem-id-123"],
        )

    def test_swallows_exceptions_best_effort(self):
        s3v = _make_s3v_client()
        s3v.delete_vectors.side_effect = RuntimeError("gone")
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=MagicMock())
        # Must not raise
        vs.delete_memory("id", "client")


# ---------------------------------------------------------------------------
# VectorStore.search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_returns_id_score_pairs(self):
        s3v = _make_s3v_client()
        s3v.query_vectors.return_value = {
            "vectors": [
                {"key": "mem-a", "distance": 0.1},
                {"key": "mem-b", "distance": 0.4},
            ]
        }
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=bedrock)
        results = vs.search("query text", "client-1", top_k=5)
        assert results == [("mem-a", round(0.9, 6)), ("mem-b", round(0.6, 6))]

    def test_calls_query_vectors_with_correct_args(self):
        s3v = _make_s3v_client()
        s3v.query_vectors.return_value = {"vectors": []}
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="mybucket", _s3v_client=s3v, _bedrock_client=bedrock)
        vs.search("hello", "myclient", top_k=7)
        call_kwargs = s3v.query_vectors.call_args.kwargs
        assert call_kwargs["vectorBucketName"] == "mybucket"
        assert call_kwargs["indexName"] == "client-myclient"
        assert call_kwargs["topK"] == 7
        assert call_kwargs["returnDistance"] is True
        assert call_kwargs["returnMetadata"] is False

    def test_raises_vector_index_not_found_on_not_found(self):
        s3v = _make_s3v_client()
        s3v.query_vectors.side_effect = s3v.exceptions.NotFoundException("no index")
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=bedrock)
        with pytest.raises(VectorIndexNotFoundError):
            vs.search("query", "client-never-wrote")

    def test_caps_top_k_at_100(self):
        s3v = _make_s3v_client()
        s3v.query_vectors.return_value = {"vectors": []}
        bedrock = _make_bedrock_client()
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=bedrock)
        vs.search("q", "c", top_k=999)
        assert s3v.query_vectors.call_args.kwargs["topK"] == 100

    def test_returns_empty_list_when_no_vectors(self):
        s3v = _make_s3v_client()
        s3v.query_vectors.return_value = {"vectors": []}
        vs = VectorStore(bucket_name="b", _s3v_client=s3v, _bedrock_client=_make_bedrock_client())
        assert vs.search("q", "c") == []
