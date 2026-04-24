# Copyright (c) 2026 John Carter. All rights reserved.
"""
Integration tests for the Hive management API.
Runs against DynamoDB Local (Docker) — set DYNAMODB_ENDPOINT env var.

Usage:
  docker run -p 8080:8000 amazon/dynamodb-local
  DYNAMODB_ENDPOINT=http://localhost:8080 pytest tests/integration/
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Point boto3 at DynamoDB Local if available, otherwise skip
DYNAMO_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")

pytestmark = pytest.mark.skipif(
    not DYNAMO_ENDPOINT,
    reason="DYNAMODB_ENDPOINT not set — skipping integration tests",
)


@pytest.fixture(scope="module")
def client():
    """Create a test client with a real (local) DynamoDB table."""
    import boto3

    # Create table in DynamoDB Local
    ddb = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMO_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    table_name = "hive-integration-test"
    import contextlib

    with contextlib.suppress(Exception):
        ddb.delete_table(TableName=table_name)

    ddb.create_table(
        TableName=table_name,
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
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    os.environ["HIVE_TABLE_NAME"] = table_name
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    from hive.api.main import app
    from hive.auth.tokens import issue_jwt
    from hive.storage import HiveStorage

    # Create a client + token for auth
    storage = HiveStorage(
        table_name=table_name,
        region="us-east-1",
        endpoint_url=DYNAMO_ENDPOINT,
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
    from datetime import datetime, timedelta, timezone

    from hive.models import OAuthClient, Token

    oauth_client = OAuthClient(client_name="Test Client")
    storage.put_client(oauth_client)

    now = datetime.now(timezone.utc)
    token = Token(
        client_id=oauth_client.client_id,
        scope="memories:read memories:write",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    storage.put_token(token)
    jwt = issue_jwt(token)

    tc = TestClient(app)
    tc.headers.update({"Authorization": f"Bearer {jwt}"})
    return tc


class TestMemoryEndpoints:
    def test_create_and_list(self, client):
        resp = client.post(
            "/api/memories", json={"key": "test-key", "value": "hello", "tags": ["x"]}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "test-key"

        resp2 = client.get("/api/memories")
        assert resp2.status_code == 200
        keys = [m["key"] for m in resp2.json()["items"]]
        assert "test-key" in keys

    def test_get_by_id(self, client):
        resp = client.post("/api/memories", json={"key": "get-test", "value": "v"})
        mid = resp.json()["memory_id"]

        resp2 = client.get(f"/api/memories/{mid}")
        assert resp2.status_code == 200
        assert resp2.json()["memory_id"] == mid

    def test_update(self, client):
        resp = client.post("/api/memories", json={"key": "update-test", "value": "old"})
        mid = resp.json()["memory_id"]

        resp2 = client.patch(f"/api/memories/{mid}", json={"value": "new"})
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "new"

    def test_delete(self, client):
        resp = client.post("/api/memories", json={"key": "del-test", "value": "bye"})
        mid = resp.json()["memory_id"]

        resp2 = client.delete(f"/api/memories/{mid}")
        assert resp2.status_code == 204

        resp3 = client.get(f"/api/memories/{mid}")
        assert resp3.status_code == 404

    def test_filter_by_tag(self, client):
        client.post("/api/memories", json={"key": "tagged-1", "value": "a", "tags": ["zz"]})
        client.post("/api/memories", json={"key": "tagged-2", "value": "b", "tags": ["zz"]})
        client.post("/api/memories", json={"key": "untagged", "value": "c", "tags": []})

        resp = client.get("/api/memories?tag=zz")
        assert resp.status_code == 200
        keys = [m["key"] for m in resp.json()["items"]]
        assert "tagged-1" in keys
        assert "tagged-2" in keys
        assert "untagged" not in keys

    def test_upsert_on_duplicate_key(self, client):
        resp1 = client.post(
            "/api/memories", json={"key": "upsert-key", "value": "v1", "tags": ["a"]}
        )
        assert resp1.status_code == 201
        mid = resp1.json()["memory_id"]

        resp2 = client.post(
            "/api/memories", json={"key": "upsert-key", "value": "v2", "tags": ["b"]}
        )
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "v2"
        assert resp2.json()["tags"] == ["b"]
        assert resp2.json()["memory_id"] == mid  # same item updated, not a new one
