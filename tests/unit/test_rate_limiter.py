# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for per-client rate limiting.

Tests the rate_limiter module, the storage counter, and the 429 behaviour
wired into both the MCP server auth helper and the management API require_token
dependency.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-ratelimit")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)


def _create_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-unit-ratelimit",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


class TestIncrementRateLimitCounter:
    def test_first_call_returns_one(self):
        with mock_aws():
            _create_table()
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            count = storage.increment_rate_limit_counter("client-1", "min#2026-04-12T10:00", 120)
            assert count == 1

    def test_increments_on_repeated_calls(self):
        with mock_aws():
            _create_table()
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            storage.increment_rate_limit_counter("c1", "min#2026-04-12T10:00", 120)
            storage.increment_rate_limit_counter("c1", "min#2026-04-12T10:00", 120)
            count = storage.increment_rate_limit_counter("c1", "min#2026-04-12T10:00", 120)
            assert count == 3

    def test_different_windows_are_independent(self):
        with mock_aws():
            _create_table()
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            c1 = storage.increment_rate_limit_counter("c1", "min#2026-04-12T10:00", 120)
            c2 = storage.increment_rate_limit_counter("c1", "min#2026-04-12T10:01", 120)
            assert c1 == 1
            assert c2 == 1

    def test_different_clients_are_independent(self):
        with mock_aws():
            _create_table()
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            c1 = storage.increment_rate_limit_counter("client-A", "min#2026-04-12T10:00", 120)
            c2 = storage.increment_rate_limit_counter("client-B", "min#2026-04-12T10:00", 120)
            assert c1 == 1
            assert c2 == 1


class TestCheckRateLimit:
    def test_allows_request_under_limit(self):
        with mock_aws():
            _create_table()
            from hive.rate_limiter import check_rate_limit
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            with patch.dict(os.environ, {"HIVE_RATE_LIMIT_RPM": "5", "HIVE_RATE_LIMIT_RPD": "100"}):
                # Should not raise
                check_rate_limit("client-1", storage)

    def test_raises_when_rpm_exceeded(self):
        with mock_aws():
            _create_table()
            from hive.rate_limiter import RateLimitExceeded, check_rate_limit
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            with patch.dict(
                os.environ, {"HIVE_RATE_LIMIT_RPM": "2", "HIVE_RATE_LIMIT_RPD": "1000"}
            ):
                check_rate_limit("client-x", storage)
                check_rate_limit("client-x", storage)
                with pytest.raises(RateLimitExceeded) as exc_info:
                    check_rate_limit("client-x", storage)
                assert exc_info.value.retry_after > 0

    def test_raises_when_rpd_exceeded(self):
        with mock_aws():
            _create_table()
            from hive.rate_limiter import RateLimitExceeded, check_rate_limit
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            with patch.dict(
                os.environ, {"HIVE_RATE_LIMIT_RPM": "1000", "HIVE_RATE_LIMIT_RPD": "2"}
            ):
                check_rate_limit("client-y", storage)
                check_rate_limit("client-y", storage)
                with pytest.raises(RateLimitExceeded) as exc_info:
                    check_rate_limit("client-y", storage)
                assert exc_info.value.retry_after > 0

    def test_exempt_client_bypasses_limit(self):
        with mock_aws():
            _create_table()
            from hive.rate_limiter import check_rate_limit
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            with patch.dict(
                os.environ,
                {
                    "HIVE_RATE_LIMIT_RPM": "1",
                    "HIVE_RATE_LIMIT_RPD": "1",
                    "HIVE_RATE_LIMIT_EXEMPT_CLIENTS": "exempt-client",
                },
            ):
                for _ in range(10):
                    check_rate_limit("exempt-client", storage)

    def test_exempt_clients_list_multiple(self):
        with mock_aws():
            _create_table()
            from hive.rate_limiter import check_rate_limit
            from hive.storage import HiveStorage

            storage = HiveStorage(table_name="hive-unit-ratelimit", region="us-east-1")
            with patch.dict(
                os.environ,
                {
                    "HIVE_RATE_LIMIT_RPM": "1",
                    "HIVE_RATE_LIMIT_EXEMPT_CLIENTS": "a, b, c",
                },
            ):
                check_rate_limit("a", storage)
                check_rate_limit("b", storage)
                check_rate_limit("c", storage)

    def test_retry_after_is_positive_int(self):
        from hive.rate_limiter import RateLimitExceeded

        exc = RateLimitExceeded(retry_after=30)
        assert exc.retry_after == 30
        assert "30" in str(exc)


class TestMcpRateLimitIntegration:
    """Verify _auth() in server.py raises ToolError on rate limit exceeded."""

    async def test_mcp_auth_raises_tool_error_on_rate_limit(self):
        from fastmcp.exceptions import ToolError

        from hive.rate_limiter import RateLimitExceeded

        with (
            patch("hive.server.validate_bearer_token") as mock_validate,
            patch("hive.server.check_rate_limit") as mock_rl,
            patch("hive.server.HiveStorage"),
            patch("hive.server.get_http_request", side_effect=RuntimeError("no request")),
        ):
            mock_token = MagicMock()
            mock_token.client_id = "test-client"
            mock_token.scope = "memories:read"
            mock_validate.return_value = mock_token
            mock_rl.side_effect = RateLimitExceeded(retry_after=45)

            from hive.server import _auth

            with pytest.raises(ToolError) as exc_info:
                await _auth(None, required_scope="memories:read")
            assert "Rate limit exceeded" in str(exc_info.value)
            assert "45" in str(exc_info.value)


class TestApiRateLimitIntegration:
    """Verify require_token raises HTTP 429 on rate limit exceeded."""

    def test_require_token_returns_429_on_rate_limit(self):
        import asyncio
        from unittest.mock import AsyncMock

        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        from hive.rate_limiter import RateLimitExceeded

        mock_emit = AsyncMock()
        with (
            patch("hive.api._auth.validate_bearer_token") as mock_validate,
            patch("hive.api._auth.check_rate_limit") as mock_rl,
            patch("hive.api._auth.emit_metric", mock_emit),
        ):
            mock_token = MagicMock()
            mock_token.client_id = "test-client"
            mock_validate.return_value = mock_token
            mock_rl.side_effect = RateLimitExceeded(retry_after=30)

            from hive.api._auth import require_token
            from hive.storage import HiveStorage

            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake-token")
            storage = MagicMock(spec=HiveStorage)

            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(require_token(creds, storage))
            assert exc_info.value.status_code == 429
            assert exc_info.value.headers["Retry-After"] == "30"
            # #367 — RateLimitedRequests emitted twice: aggregate + drill-down.
            calls = [(c.args, c.kwargs) for c in mock_emit.call_args_list]
            assert (("RateLimitedRequests",), {}) in calls
            assert (
                ("RateLimitedRequests",),
                {"endpoint": "/api", "reason": "rate_limit"},
            ) in calls
