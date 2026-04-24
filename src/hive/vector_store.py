# Copyright (c) 2026 John Carter. All rights reserved.
"""
Vector store for Hive — S3 Vectors + Bedrock Titan Embeddings V2.

One S3 Vectors index per OAuth client (``client-{client_id}``), lazy-created
on first write.  All operations are best-effort: errors are logged but never
propagate to callers so that DynamoDB (the authoritative store) is unaffected
by vector-layer failures.

Embedding model: amazon.titan-embed-text-v2:0
  - 1024 dimensions, cosine distance, normalised vectors
  - Input text: "{key}: {value}" (key + value gives richer semantic coverage)
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Literal

import boto3

from hive.logging_config import get_logger
from hive.models import Memory

if TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
    from mypy_boto3_s3vectors import S3VectorsClient

logger = get_logger("hive.vector_store")

_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
_DIMENSIONS = 1024
_DISTANCE_METRIC: Literal["cosine", "euclidean"] = "cosine"


class VectorIndexNotFoundError(Exception):
    """Raised when querying a client that has never written a memory."""


class VectorStore:
    """Thin wrapper around S3 Vectors + Bedrock Titan Embeddings V2."""

    def __init__(
        self,
        bucket_name: str | None = None,
        region: str | None = None,
        bedrock_region: str | None = None,
        _s3v_client: Any = None,
        _bedrock_client: Any = None,
    ) -> None:
        self._bucket = bucket_name or os.environ["HIVE_VECTORS_BUCKET"]
        region = region or os.environ.get("AWS_REGION", "us-east-1")
        bedrock_region = bedrock_region or os.environ.get("BEDROCK_REGION", region)
        # Allow injection of mock clients in tests
        self._s3v: S3VectorsClient = _s3v_client or boto3.client("s3vectors", region_name=region)
        self._bedrock: BedrockRuntimeClient = _bedrock_client or boto3.client(
            "bedrock-runtime", region_name=bedrock_region
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _index_name(self, client_id: str) -> str:
        return f"client-{client_id}"

    def _embed(self, text: str) -> list[float]:
        """Call Bedrock Titan V2 and return a 1024-dim normalised embedding."""
        body = json.dumps({"inputText": text, "dimensions": _DIMENSIONS, "normalize": True})
        resp = self._bedrock.invoke_model(
            modelId=_EMBEDDING_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(resp["body"].read())["embedding"]

    def _ensure_index(self, client_id: str) -> str:
        """Return the index name, creating it if it doesn't exist yet."""
        index_name = self._index_name(client_id)
        try:
            self._s3v.create_index(
                vectorBucketName=self._bucket,
                indexName=index_name,
                dataType="float32",
                dimension=_DIMENSIONS,
                distanceMetric=_DISTANCE_METRIC,
            )
            logger.info("Created vector index '%s'", index_name)
        except self._s3v.exceptions.ConflictException:
            pass  # Index already exists — expected after first write
        return index_name

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def upsert_memory(self, memory: Memory) -> None:
        """Write (or overwrite) a memory vector.  Best-effort — never raises."""
        try:
            index_name = self._ensure_index(memory.owner_client_id)
            text = f"{memory.key}: {memory.value}"
            embedding = self._embed(text)
            self._s3v.put_vectors(
                vectorBucketName=self._bucket,
                indexName=index_name,
                vectors=[
                    {
                        "key": memory.memory_id,
                        "data": {"float32": embedding},
                        "metadata": {
                            "memory_key": memory.key,
                            "tags": json.dumps(memory.tags),
                        },
                    }
                ],
            )
        except Exception:
            logger.warning(
                "Vector upsert failed for memory '%s' (client %s)",
                memory.key,
                memory.owner_client_id,
                exc_info=True,
            )

    def delete_memory(self, memory_id: str, client_id: str) -> None:
        """Remove a memory vector.  Best-effort — never raises."""
        try:
            self._s3v.delete_vectors(
                vectorBucketName=self._bucket,
                indexName=self._index_name(client_id),
                keys=[memory_id],
            )
        except Exception:
            logger.warning(  # NOSONAR — memory_id and client_id are internal identifiers, not user content
                "Vector delete failed for memory_id '%s' (client %s)",
                memory_id,
                client_id,
                exc_info=True,
            )

    def search(
        self,
        query: str,
        client_id: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Return ``(memory_id, score)`` pairs ranked by cosine similarity.

        ``score`` is ``1.0 - distance`` so higher = more relevant.

        Raises ``VectorIndexNotFoundError`` when the client has never written
        a memory (index does not exist yet).
        """
        index_name = self._index_name(client_id)
        try:
            embedding = self._embed(query)
            resp = self._s3v.query_vectors(
                vectorBucketName=self._bucket,
                indexName=index_name,
                queryVector={"float32": embedding},
                topK=min(top_k, 100),
                returnDistance=True,
                returnMetadata=False,
            )
        except self._s3v.exceptions.NotFoundException as exc:
            raise VectorIndexNotFoundError(
                f"No vector index for client '{client_id}' — no memories indexed yet."
            ) from exc
        return [(v["key"], round(1.0 - v["distance"], 6)) for v in resp.get("vectors", [])]
