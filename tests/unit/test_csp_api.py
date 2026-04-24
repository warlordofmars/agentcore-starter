# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for the POST /api/csp-report browser CSP violation endpoint.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-csp")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)


def _create_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-unit-csp",
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
                "KeySchema": [{"AttributeName": "GSI4PK", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def client():
    with mock_aws():
        _create_table()
        from hive.api import csp as csp_mod
        from hive.api.main import app
        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-csp", region="us-east-1")
        app.dependency_overrides[csp_mod._storage] = lambda: storage
        yield TestClient(app), storage
        app.dependency_overrides.clear()


_LEGACY_REPORT = {
    "csp-report": {
        "document-uri": "https://example.com/app",
        "referrer": "",
        "violated-directive": "script-src-elem",
        "effective-directive": "script-src-elem",
        "original-policy": "default-src 'self'",
        "disposition": "report",
        "blocked-uri": "https://evil.example.net/tracker.js",
        "line-number": 12,
        "column-number": 3,
        "source-file": "https://example.com/app",
        "status-code": 0,
        "script-sample": "",
    }
}

_MODERN_REPORT = [
    {
        "type": "csp-violation",
        "url": "https://example.com/app",
        "user_agent": "Mozilla/5.0",
        "body": {
            "effectiveDirective": "img-src",
            "blockedURL": "https://cdn.other.example/img.png",
            "documentURL": "https://example.com/app",
            "disposition": "report",
            "lineNumber": 99,
            "columnNumber": 7,
            "sourceFile": "https://example.com/app/bundle.js",
        },
    }
]


class TestCspReport:
    def test_legacy_report_returns_204_and_logs(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post("/api/csp-report", json=_LEGACY_REPORT)
        assert resp.status_code == 204
        assert resp.content == b""
        # Two emits per violation: aggregate (Environment only) + drill-down
        assert mock_emit.await_count == 2
        assert mock_emit.await_args_list[0].args == ("CSPViolations",)
        drilldown = mock_emit.await_args_list[1]
        assert drilldown.args == ("CSPViolations",)
        assert drilldown.kwargs["directive"] == "script-src-elem"
        assert drilldown.kwargs["blocked_domain"] == "evil.example.net"

    def test_modern_report_returns_204_and_logs(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post("/api/csp-report", json=_MODERN_REPORT)
        assert resp.status_code == 204
        assert mock_emit.await_count == 2
        drilldown = mock_emit.await_args_list[1]
        assert drilldown.kwargs["directive"] == "img-src"
        assert drilldown.kwargs["blocked_domain"] == "cdn.other.example"

    def test_empty_body_returns_204_no_emit(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post("/api/csp-report", data="")
        assert resp.status_code == 204
        mock_emit.assert_not_awaited()

    def test_malformed_json_returns_204_no_emit(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post(
                "/api/csp-report",
                data="this is not json",
                headers={"Content-Type": "application/csp-report"},
            )
        assert resp.status_code == 204
        mock_emit.assert_not_awaited()

    def test_unknown_payload_shape_is_ignored(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            # Dict without "csp-report" key — not legacy, and not a list for modern
            resp = tc.post("/api/csp-report", json={"foo": "bar"})
        assert resp.status_code == 204
        mock_emit.assert_not_awaited()

    def test_modern_report_non_csp_type_ignored(self, client):
        tc, _ = client
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post(
                "/api/csp-report",
                json=[{"type": "deprecation", "body": {}}],
            )
        assert resp.status_code == 204
        mock_emit.assert_not_awaited()

    def test_rate_limit_per_ip(self, client):
        """After 60 reports/min from the same IP, subsequent reports get 429.

        The rate-limit bucket keys on the current minute (``strftime("%Y-%m-%dT%H:%M")``),
        so the 61st request can slip into a fresh bucket if the loop crosses a
        minute boundary. Freeze ``datetime.now`` inside the rate-limit check so
        every request lands in the same bucket.
        """
        from datetime import datetime, timezone

        tc, _ = client
        mock_emit = AsyncMock()
        frozen = datetime(2026, 4, 18, 12, 34, 0, tzinfo=timezone.utc)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen if tz is None else frozen.astimezone(tz)

        with (
            patch("hive.api.csp.emit_metric", mock_emit),
            patch("hive.api.csp.datetime", _FrozenDatetime),
        ):
            headers = {"x-forwarded-for": "203.0.113.42"}
            for _ in range(60):
                resp = tc.post("/api/csp-report", json=_LEGACY_REPORT, headers=headers)
                assert resp.status_code == 204
            over_limit = tc.post("/api/csp-report", json=_LEGACY_REPORT, headers=headers)
            assert over_limit.status_code == 429

    def test_ip_picked_from_cloudfront_header(self, client):
        """Behind CloudFront the viewer IP is in cloudfront-viewer-address as ip:port."""
        tc, storage = client
        mock_emit = AsyncMock()
        with (
            patch("hive.api.csp.emit_metric", mock_emit),
            patch.object(
                storage, "increment_rate_limit_counter", wraps=storage.increment_rate_limit_counter
            ) as spy,
        ):
            tc.post(
                "/api/csp-report",
                json=_LEGACY_REPORT,
                headers={"cloudfront-viewer-address": "198.51.100.7:12345"},
            )
        bucket = spy.call_args_list[0].args[1]
        assert "198.51.100.7" in bucket

    def test_ip_falls_back_to_xff(self, client):
        tc, storage = client
        with (
            patch("hive.api.csp.emit_metric", AsyncMock()),
            patch.object(
                storage,
                "increment_rate_limit_counter",
                wraps=storage.increment_rate_limit_counter,
            ) as spy,
        ):
            tc.post(
                "/api/csp-report",
                json=_LEGACY_REPORT,
                headers={"x-forwarded-for": "192.0.2.1, 10.0.0.1"},
            )
        bucket = spy.call_args_list[0].args[1]
        assert "192.0.2.1" in bucket

    def test_long_field_is_truncated(self, client):
        """A pathological blocked-URI value is clamped before logging/metrics."""
        tc, _ = client
        long_uri = "https://very-long-host.example/" + ("x" * 3000)
        payload = {
            "csp-report": {
                "violated-directive": "script-src",
                "blocked-uri": long_uri,
                "document-uri": "https://example.com/",
            }
        }
        mock_emit = AsyncMock()
        with patch("hive.api.csp.emit_metric", mock_emit):
            resp = tc.post("/api/csp-report", json=payload)
        assert resp.status_code == 204
        drilldown_kwargs = mock_emit.await_args_list[1].kwargs
        # Domain stays short (it's extracted by urlparse); directive untouched.
        assert drilldown_kwargs["directive"] == "script-src"
        assert "very-long-host.example" in drilldown_kwargs["blocked_domain"]


class TestHelpers:
    def test_blocked_domain_keyword_values(self):
        from hive.api.csp import _blocked_domain

        assert _blocked_domain("inline") == "inline"
        assert _blocked_domain("eval") == "eval"
        assert _blocked_domain("self") == "self"
        assert _blocked_domain("data") == "data"

    def test_blocked_domain_empty(self):
        from hive.api.csp import _blocked_domain

        assert _blocked_domain("") == "none"

    def test_blocked_domain_unparseable(self):
        from hive.api.csp import _blocked_domain

        # urlparse almost never raises, but a value with no scheme falls back
        # to the raw string — which is fine for a dimension label.
        assert _blocked_domain("not-a-real-url") == "not-a-real-url"

    def test_truncate_short_string(self):
        from hive.api.csp import _truncate

        assert _truncate("short") == "short"
        assert _truncate(42) == 42  # non-strings pass through

    def test_client_ip_falls_back_to_socket(self):
        from unittest.mock import MagicMock

        from hive.api.csp import _client_ip

        req = MagicMock()
        req.headers = {}
        req.client.host = "127.0.0.1"
        assert _client_ip(req) == "127.0.0.1"

    def test_client_ip_unknown_when_no_client(self):
        from unittest.mock import MagicMock

        from hive.api.csp import _client_ip

        req = MagicMock()
        req.headers = {}
        req.client = None
        assert _client_ip(req) == "unknown"

    def test_storage_factory_returns_storage(self):
        """The module-level _storage() dependency factory returns a HiveStorage."""
        from hive.api.csp import _storage
        from hive.storage import HiveStorage

        assert isinstance(_storage(), HiveStorage)
