# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for GET /api/admin/logs.

CloudWatch Logs boto3 calls are mocked via unittest.mock so tests run
without any AWS credentials.
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-logs")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)

_ADMIN_CLAIMS = {"sub": "admin-001", "role": "admin", "email": "admin@example.com"}
_USER_CLAIMS = {"sub": "user-001", "role": "user", "email": "user@example.com"}

_NOW_MS = int(time.time() * 1000)

_SAMPLE_EVENT = {
    "timestamp": _NOW_MS - 5000,
    "message": '{"level": "INFO", "message": "tool called", "tool": "remember"}',
    "logStreamName": "2026/04/11/[$LATEST]abc123",
    "eventId": "evt-001",
}


def _create_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-unit-logs",
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
                "IndexName": "ClientIdIndex",
                "KeySchema": [{"AttributeName": "GSI4PK", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def admin_tc():
    with mock_aws():
        _create_table()
        from hive.api import _auth as auth_mod
        from hive.api.main import app

        app.dependency_overrides[auth_mod.require_mgmt_user] = lambda: _ADMIN_CLAIMS
        yield TestClient(app)
        app.dependency_overrides.clear()


@pytest.fixture()
def user_tc():
    with mock_aws():
        _create_table()
        from hive.api import _auth as auth_mod
        from hive.api.main import app

        app.dependency_overrides[auth_mod.require_mgmt_user] = lambda: _USER_CLAIMS
        yield TestClient(app)
        app.dependency_overrides.clear()


def _mock_logs_client(events=None, next_token=None):
    """Return a mock boto3 logs client that returns given events."""
    mock_client = MagicMock()
    mock_client.filter_log_events.return_value = {
        "events": events or [],
        **({"nextToken": next_token} if next_token else {}),
    }
    return mock_client


class TestGetLogs:
    def test_requires_admin(self, user_tc):
        resp = user_tc.get("/api/admin/logs")
        assert resp.status_code == 403

    def test_returns_empty_events_when_no_logs(self, admin_tc):
        mock_client = _mock_logs_client(events=[])
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["next_token"] is None

    def test_returns_log_events_for_mcp_group(self, admin_tc):
        mock_client = _mock_logs_client(events=[_SAMPLE_EVENT])
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=mcp")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["message"] == _SAMPLE_EVENT["message"]
        assert events[0]["log_stream"] == _SAMPLE_EVENT["logStreamName"]
        assert events[0]["event_id"] == _SAMPLE_EVENT["eventId"]
        assert "log_group" in events[0]
        assert "mcp" in events[0]["log_group"]

    def test_returns_events_from_both_groups_for_all(self, admin_tc):
        mcp_event = {**_SAMPLE_EVENT, "eventId": "evt-mcp", "timestamp": _NOW_MS - 2000}
        api_event = {**_SAMPLE_EVENT, "eventId": "evt-api", "timestamp": _NOW_MS - 1000}
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if "mcp" in kwargs["logGroupName"]:
                return {"events": [mcp_event]}
            return {"events": [api_event]}

        mock_client = MagicMock()
        mock_client.filter_log_events.side_effect = side_effect
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=all")
        assert resp.status_code == 200
        events = resp.json()["events"]
        # Both groups queried
        assert call_count == 2
        assert len(events) == 2
        # Newest first
        assert events[0]["event_id"] == "evt-api"
        assert events[1]["event_id"] == "evt-mcp"

    def test_events_sorted_newest_first(self, admin_tc):
        older = {**_SAMPLE_EVENT, "eventId": "old", "timestamp": _NOW_MS - 10000}
        newer = {**_SAMPLE_EVENT, "eventId": "new", "timestamp": _NOW_MS - 1000}
        mock_client = _mock_logs_client(events=[older, newer])
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=mcp")
        events = resp.json()["events"]
        assert events[0]["event_id"] == "new"
        assert events[1]["event_id"] == "old"

    def test_passes_filter_pattern(self, admin_tc):
        mock_client = _mock_logs_client()
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            admin_tc.get("/api/admin/logs?group=mcp&filter=ERROR")
        call_kwargs = mock_client.filter_log_events.call_args[1]
        assert call_kwargs["filterPattern"] == "ERROR"

    def test_no_filter_pattern_when_empty(self, admin_tc):
        mock_client = _mock_logs_client()
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            admin_tc.get("/api/admin/logs?group=mcp")
        call_kwargs = mock_client.filter_log_events.call_args[1]
        assert "filterPattern" not in call_kwargs

    def test_passes_next_token(self, admin_tc):
        mock_client = _mock_logs_client()
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            admin_tc.get("/api/admin/logs?group=mcp&next_token=abc123")
        call_kwargs = mock_client.filter_log_events.call_args[1]
        assert call_kwargs["nextToken"] == "abc123"

    def test_returns_next_token_from_response(self, admin_tc):
        mock_client = _mock_logs_client(next_token="page2token")
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=mcp")
        assert resp.json()["next_token"] == "page2token"

    def test_window_parameter_accepted(self, admin_tc):
        mock_client = _mock_logs_client()
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            for w in ("15m", "1h", "3h", "24h"):
                resp = admin_tc.get(f"/api/admin/logs?group=mcp&window={w}")
                assert resp.status_code == 200

    def test_invalid_window_rejected(self, admin_tc):
        resp = admin_tc.get("/api/admin/logs?window=99h")
        assert resp.status_code == 422

    def test_invalid_group_rejected(self, admin_tc):
        resp = admin_tc.get("/api/admin/logs?group=unknown")
        assert resp.status_code == 422

    def test_resource_not_found_skips_group(self, admin_tc):
        """Log group doesn't exist yet — should return empty, not 502."""
        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "group not found"}
        }
        mock_client = MagicMock()
        mock_client.filter_log_events.side_effect = ClientError(error_response, "FilterLogEvents")
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=mcp")
        assert resp.status_code == 200
        assert resp.json()["events"] == []

    def test_unexpected_aws_error_returns_502(self, admin_tc):
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "throttled"}}
        mock_client = MagicMock()
        mock_client.filter_log_events.side_effect = ClientError(error_response, "FilterLogEvents")
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            resp = admin_tc.get("/api/admin/logs?group=mcp")
        assert resp.status_code == 502
        assert "ThrottlingException" in resp.json()["detail"]

    def test_log_group_names_for_all(self, admin_tc):
        """Both log groups are queried when group=all."""
        queried_groups: list[str] = []

        def capture(**kwargs):
            queried_groups.append(kwargs["logGroupName"])
            return {"events": []}

        mock_client = MagicMock()
        mock_client.filter_log_events.side_effect = capture
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            admin_tc.get("/api/admin/logs?group=all")
        assert any("mcp" in g for g in queried_groups)
        assert any("api" in g for g in queried_groups)

    def test_log_group_names_for_api_only(self, admin_tc):
        queried_groups: list[str] = []

        def capture(**kwargs):
            queried_groups.append(kwargs["logGroupName"])
            return {"events": []}

        mock_client = MagicMock()
        mock_client.filter_log_events.side_effect = capture
        with patch("hive.api.logs.boto3.client", return_value=mock_client):
            admin_tc.get("/api/admin/logs?group=api")
        assert len(queried_groups) == 1
        assert "api" in queried_groups[0]
