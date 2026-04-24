# Copyright (c) 2026 John Carter. All rights reserved.
"""
Integration tests for the FastMCP tools against DynamoDB Local.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

DYNAMO_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")

pytestmark = pytest.mark.skipif(
    not DYNAMO_ENDPOINT,
    reason="DYNAMODB_ENDPOINT not set — skipping integration tests",
)


def _make_context(token_str: str):
    """Build a minimal MCP Context with an Authorization header."""
    ctx = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.meta = {"Authorization": f"Bearer {token_str}"}
    return ctx


def _text(r) -> str:
    """Extract text payload from a ToolResult."""
    return r.content[0].text


def _body(r) -> dict:
    """Extract structured content from a ToolResult."""
    return r.structured_content


@pytest.fixture(scope="module")
def setup():
    """Set up DynamoDB Local table + a valid token for MCP tool calls."""
    from datetime import datetime, timedelta, timezone

    import boto3

    from hive.auth.tokens import issue_jwt
    from hive.models import OAuthClient, Token

    table_name = "hive-mcp-integration"
    ddb = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMO_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
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
    from hive.storage import HiveStorage

    storage = HiveStorage(
        table_name=table_name,
        region="us-east-1",
        endpoint_url=DYNAMO_ENDPOINT,
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    oauth_client = OAuthClient(client_name="MCP Test Client", owner_user_id="integration-test-user")
    storage.put_client(oauth_client)

    now = datetime.now(timezone.utc)
    token = Token(
        client_id=oauth_client.client_id,
        scope="memories:read memories:write",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    storage.put_token(token)
    jwt_str = issue_jwt(token)
    return jwt_str


@pytest.mark.asyncio
class TestMCPTools:
    async def test_remember_and_recall(self, setup):
        from hive.server import recall, remember

        jwt = setup
        ctx = _make_context(jwt)
        result = await remember(key="greeting", value="Hello, Hive!", tags=["test"], ctx=ctx)
        assert "greeting" in _text(result)

        recalled = await recall(key="greeting", ctx=ctx)
        assert _text(recalled) == "Hello, Hive!"

    async def test_forget(self, setup):
        from fastmcp.exceptions import ToolError

        from hive.server import forget, recall, remember

        jwt = setup
        ctx = _make_context(jwt)
        await remember(key="temp", value="ephemeral", ctx=ctx)
        result = await forget(key="temp", ctx=ctx)
        assert "temp" in _text(result)

        with pytest.raises(ToolError):
            await recall(key="temp", ctx=ctx)

    async def test_list_memories(self, setup):
        from hive.server import list_memories, remember

        jwt = setup
        ctx = _make_context(jwt)
        await remember(key="list-a", value="A", tags=["listtest"], ctx=ctx)
        await remember(key="list-b", value="B", tags=["listtest"], ctx=ctx)

        result = await list_memories(tag="listtest", ctx=ctx)
        keys = [m["key"] for m in _body(result)["items"]]
        assert "list-a" in keys
        assert "list-b" in keys

    async def test_summarize_context(self, setup):
        from hive.server import remember, summarize_context

        jwt = setup
        ctx = _make_context(jwt)
        await remember(key="s1", value="Summary value 1", tags=["summary"], ctx=ctx)
        await remember(key="s2", value="Summary value 2", tags=["summary"], ctx=ctx)

        result = await summarize_context(topic="summary", ctx=ctx)
        text = _text(result)
        assert "summary" in text.lower()
        assert "s1" in text or "s2" in text


def _make_user_token(storage, owner_user_id: str) -> str:
    """Create an OAuth client + token for ``owner_user_id`` and return a JWT."""
    from datetime import datetime, timedelta, timezone

    from hive.auth.tokens import issue_jwt
    from hive.models import OAuthClient, Token

    client = OAuthClient(
        client_name=f"Integration User {owner_user_id}", owner_user_id=owner_user_id
    )
    storage.put_client(client)
    now = datetime.now(timezone.utc)
    token = Token(
        client_id=client.client_id,
        scope="memories:read memories:write",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    storage.put_token(token)
    return issue_jwt(token)


@pytest.fixture(scope="module")
def two_user_setup():
    """Set up DynamoDB Local table + two users for cross-user isolation tests."""
    import contextlib

    import boto3

    table_name = "hive-mcp-cross-user"
    ddb = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMO_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
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

    previous_table_name = os.environ.get("HIVE_TABLE_NAME")
    os.environ["HIVE_TABLE_NAME"] = table_name
    try:
        from hive.storage import HiveStorage

        storage = HiveStorage(
            table_name=table_name,
            region="us-east-1",
            endpoint_url=DYNAMO_ENDPOINT,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )

        jwt_a = _make_user_token(storage, "integration-user-a")
        jwt_b = _make_user_token(storage, "integration-user-b")
        yield jwt_a, jwt_b
    finally:
        if previous_table_name is None:
            os.environ.pop("HIVE_TABLE_NAME", None)
        else:
            os.environ["HIVE_TABLE_NAME"] = previous_table_name


@pytest.mark.asyncio
class TestCrossUserIsolation:
    """Regression tests for the cross-user memory leak fixed in #587."""

    async def test_list_memories_cross_user_isolation(self, two_user_setup):
        """list_memories must not expose User A's memories to User B."""
        from hive.server import list_memories, remember

        jwt_a, jwt_b = two_user_setup
        ctx_a = _make_context(jwt_a)
        ctx_b = _make_context(jwt_b)

        await remember(key="leak-a", value="sensitive-a", tags=["cross-user-tag"], ctx=ctx_a)
        await remember(key="leak-b", value="sensitive-b", tags=["cross-user-tag"], ctx=ctx_b)

        result_a = await list_memories(tag="cross-user-tag", ctx=ctx_a)
        keys_a = [m["key"] for m in _body(result_a)["items"]]
        assert "leak-a" in keys_a
        assert "leak-b" not in keys_a, "User B's memory must not appear in User A's list"

        result_b = await list_memories(tag="cross-user-tag", ctx=ctx_b)
        keys_b = [m["key"] for m in _body(result_b)["items"]]
        assert "leak-b" in keys_b
        assert "leak-a" not in keys_b, "User A's memory must not appear in User B's list"

    async def test_summarize_context_cross_user_isolation(self, two_user_setup):
        """summarize_context must not include memories from a different user."""
        from hive.server import remember, summarize_context

        jwt_a, jwt_b = two_user_setup
        ctx_a = _make_context(jwt_a)
        ctx_b = _make_context(jwt_b)

        await remember(key="sum-a", value="user-a-private", tags=["cross-sum-tag"], ctx=ctx_a)
        await remember(key="sum-b", value="user-b-private", tags=["cross-sum-tag"], ctx=ctx_b)

        result_a = await summarize_context(topic="cross-sum-tag", ctx=ctx_a)
        text_a = _text(result_a)
        assert "user-a-private" in text_a
        assert "user-b-private" not in text_a, "User B's value must not appear in User A's summary"
