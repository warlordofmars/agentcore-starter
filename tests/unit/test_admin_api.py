# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for /admin/metrics and /admin/costs endpoints.

CloudWatch and Cost Explorer boto3 calls are mocked via unittest.mock so
tests run without any AWS credentials.
"""

from __future__ import annotations

import datetime
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-admin")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)

_ADMIN_CLAIMS = {"sub": "admin-001", "role": "admin", "email": "admin@example.com"}
_USER_CLAIMS = {"sub": "user-001", "role": "user", "email": "user@example.com"}


def _create_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-unit-admin",
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


def _make_cw_response(metric_ids: list[str]) -> dict:
    """Build a minimal CloudWatch GetMetricData response."""
    ts = datetime.datetime(2026, 4, 1, 12, 0, tzinfo=datetime.timezone.utc)
    return {
        "MetricDataResults": [
            {"Id": mid, "Timestamps": [ts], "Values": [1.0]} for mid in metric_ids
        ]
    }


def _make_ce_monthly_response() -> dict:
    """Build a minimal Cost Explorer monthly GetCostAndUsage response."""
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-03-01", "End": "2026-04-01"},
                "Groups": [
                    {
                        "Keys": ["AWS Lambda"],
                        "Metrics": {"UnblendedCost": {"Amount": "0.5000", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["Amazon DynamoDB"],
                        "Metrics": {"UnblendedCost": {"Amount": "0.1200", "Unit": "USD"}},
                    },
                ],
            }
        ]
    }


def _make_ce_daily_response() -> dict:
    """Build a minimal Cost Explorer daily GetCostAndUsage response."""
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-04-01", "End": "2026-04-02"},
                "Groups": [
                    {
                        "Keys": ["AWS Lambda"],
                        "Metrics": {"UnblendedCost": {"Amount": "0.0200", "Unit": "USD"}},
                    },
                ],
            }
        ]
    }


def _make_ce_response() -> dict:
    """Back-compat alias — returns monthly response (used by CW tests that don't check costs)."""
    return _make_ce_monthly_response()


@pytest.fixture()
def admin_tc():
    """TestClient authenticated as admin, with CW/CE boto3 calls mocked."""
    with mock_aws():
        _create_table()
        from hive.api import _auth as auth_mod
        from hive.api.main import app

        app.dependency_overrides[auth_mod.require_mgmt_user] = lambda: _ADMIN_CLAIMS
        yield TestClient(app)
        app.dependency_overrides.clear()


@pytest.fixture()
def user_tc():
    """TestClient authenticated as a non-admin user."""
    with mock_aws():
        _create_table()
        from hive.api import _auth as auth_mod
        from hive.api.main import app

        app.dependency_overrides[auth_mod.require_mgmt_user] = lambda: _USER_CLAIMS
        yield TestClient(app)
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /admin/metrics
# ---------------------------------------------------------------------------


class TestAdminMetrics:
    def test_returns_metrics_for_24h(self, admin_tc):
        metric_ids = [
            "inv_remember",
            "err_remember",
            "p99_remember",
            "inv_recall",
            "err_recall",
            "p99_recall",
            "inv_forget",
            "err_forget",
            "p99_forget",
            "inv_listmemories",
            "err_listmemories",
            "p99_listmemories",
            "inv_summarizecontext",
            "err_summarizecontext",
            "p99_summarizecontext",
            "tokens_issued",
            "token_failures",
            "csp_violations",
            "rate_limited_requests",
        ]
        cw_resp = _make_cw_response(metric_ids)
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.get_metric_data.return_value = cw_resp
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/metrics?period=24h")

        assert resp.status_code == 200
        body = resp.json()
        assert body["period"] == "24h"
        assert "metrics" in body
        assert "inv_remember" in body["metrics"]
        assert body["metrics"]["inv_remember"]["values"] == [1.0]
        # #367 — Rate-limited requests surface as a Dashboard stat card, so
        # the admin metrics endpoint must include the aggregate query.
        assert "rate_limited_requests" in body["metrics"]

    def test_returns_metrics_for_1h(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.get_metric_data.return_value = {"MetricDataResults": []}
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/metrics?period=1h")

        assert resp.status_code == 200
        assert resp.json()["period"] == "1h"

    def test_returns_metrics_for_7d(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.get_metric_data.return_value = {"MetricDataResults": []}
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/metrics?period=7d")

        assert resp.status_code == 200
        assert resp.json()["period"] == "7d"

    def test_returns_metrics_for_30d(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.get_metric_data.return_value = {"MetricDataResults": []}
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/metrics?period=30d")

        assert resp.status_code == 200
        assert resp.json()["period"] == "30d"

    def test_invalid_period_returns_422(self, admin_tc):
        resp = admin_tc.get("/api/admin/metrics?period=99d")
        assert resp.status_code == 422

    def test_non_admin_gets_403(self, user_tc):
        resp = user_tc.get("/api/admin/metrics?period=24h")
        assert resp.status_code == 403

    def test_environment_in_response(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.get_metric_data.return_value = {"MetricDataResults": []}
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/metrics?period=24h")

        assert "environment" in resp.json()


# ---------------------------------------------------------------------------
# /admin/costs
# ---------------------------------------------------------------------------


class TestAdminCosts:
    def setup_method(self):
        # Clear the module-level cache before each test
        import hive.api.admin as admin_mod

        admin_mod._cost_cache.clear()

    def _mock_ce(self, mock_ce, repeats=1):
        """Set side_effect to return monthly then daily responses, repeated N times."""
        responses = []
        for _ in range(repeats):
            responses.append(_make_ce_monthly_response())
            responses.append(_make_ce_daily_response())
        mock_ce.get_cost_and_usage.side_effect = responses

    def test_returns_cost_data(self, admin_tc):
        with patch("hive.api.admin._ce_client") as mock_ce_factory:
            mock_ce = MagicMock()
            self._mock_ce(mock_ce)
            mock_ce_factory.return_value = mock_ce

            resp = admin_tc.get("/api/admin/costs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["currency"] == "USD"
        assert len(body["monthly"]) == 1
        assert body["monthly"][0]["period"] == "2026-03-01"
        assert body["monthly"][0]["total"] == pytest.approx(0.62, abs=0.01)
        assert "AWS Lambda" in body["monthly"][0]["by_service"]
        assert "daily" in body
        assert len(body["daily"]) == 1
        assert body["daily"][0]["date"] == "2026-04-01"
        assert body["daily"][0]["total"] == pytest.approx(0.02, abs=0.001)

    def test_non_admin_gets_403(self, user_tc):
        resp = user_tc.get("/api/admin/costs")
        assert resp.status_code == 403

    def test_cache_is_used_on_second_call(self, admin_tc):
        with patch("hive.api.admin._ce_client") as mock_ce_factory:
            mock_ce = MagicMock()
            self._mock_ce(mock_ce)
            mock_ce_factory.return_value = mock_ce

            admin_tc.get("/api/admin/costs")
            admin_tc.get("/api/admin/costs")

            # CE makes 2 calls (monthly + daily) on first request; second uses cache
            assert mock_ce.get_cost_and_usage.call_count == 2

    def test_cache_expires_after_ttl(self, admin_tc):
        with patch("hive.api.admin._ce_client") as mock_ce_factory:
            mock_ce = MagicMock()
            self._mock_ce(mock_ce, repeats=2)
            mock_ce_factory.return_value = mock_ce

            admin_tc.get("/api/admin/costs")

            # Backdate the cache entry so it appears expired
            import hive.api.admin as admin_mod

            env = admin_mod.ENVIRONMENT
            ts, data = admin_mod._cost_cache[env]
            admin_mod._cost_cache[env] = (ts - admin_mod._COST_CACHE_TTL - 1, data)

            admin_tc.get("/api/admin/costs")
            # 2 CE calls per request × 2 requests = 4
            assert mock_ce.get_cost_and_usage.call_count == 4

    def test_note_and_environment_in_response(self, admin_tc):
        with patch("hive.api.admin._ce_client") as mock_ce_factory:
            mock_ce = MagicMock()
            self._mock_ce(mock_ce)
            mock_ce_factory.return_value = mock_ce

            resp = admin_tc.get("/api/admin/costs")

        body = resp.json()
        assert "note" in body
        assert "environment" in body


# ---------------------------------------------------------------------------
# /admin/alarms
# ---------------------------------------------------------------------------


class TestAdminAlarms:
    def setup_method(self):
        import hive.api.admin as admin_mod

        admin_mod._alarm_cache.clear()

    def _make_describe_alarms_response(self, state: str = "OK") -> dict:
        ts = datetime.datetime(2026, 4, 11, 12, 0, tzinfo=datetime.timezone.utc)
        return {
            "MetricAlarms": [
                {
                    "AlarmName": "Hive-local-McpErrorRate",
                    "AlarmDescription": "MCP error rate > 5%",
                    "StateValue": state,
                    "StateUpdatedTimestamp": ts,
                    "Threshold": 5.0,
                    "ComparisonOperator": "GreaterThanThreshold",
                    "MetricName": "ErrorRate",
                    "Namespace": "AWS/Lambda",
                }
            ]
        }

    def test_returns_alarm_data(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = self._make_describe_alarms_response()
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/alarms")

        assert resp.status_code == 200
        body = resp.json()
        assert "alarms" in body
        assert len(body["alarms"]) == 1
        alarm = body["alarms"][0]
        assert alarm["name"] == "Hive-local-McpErrorRate"
        assert alarm["state"] == "OK"
        assert alarm["description"] == "MCP error rate > 5%"
        assert alarm["threshold"] == 5.0
        assert alarm["metric_name"] == "ErrorRate"
        assert alarm["state_updated_at"] == "2026-04-11T12:00:00+00:00"

    def test_non_admin_gets_403(self, user_tc):
        resp = user_tc.get("/api/admin/alarms")
        assert resp.status_code == 403

    def test_cache_is_used_on_second_call(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = self._make_describe_alarms_response()
            mock_cw_factory.return_value = mock_cw

            admin_tc.get("/api/admin/alarms")
            admin_tc.get("/api/admin/alarms")

            assert mock_cw.describe_alarms.call_count == 1

    def test_cache_expires_after_ttl(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = self._make_describe_alarms_response()
            mock_cw_factory.return_value = mock_cw

            admin_tc.get("/api/admin/alarms")

            import hive.api.admin as admin_mod

            env = admin_mod.ENVIRONMENT
            ts, data = admin_mod._alarm_cache[env]
            admin_mod._alarm_cache[env] = (ts - admin_mod._ALARM_CACHE_TTL - 1, data)

            admin_tc.get("/api/admin/alarms")
            assert mock_cw.describe_alarms.call_count == 2

    def test_empty_when_no_alarms(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = {"MetricAlarms": []}
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/alarms")

        assert resp.json()["alarms"] == []

    def test_environment_in_response(self, admin_tc):
        with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = self._make_describe_alarms_response()
            mock_cw_factory.return_value = mock_cw

            resp = admin_tc.get("/api/admin/alarms")

        assert "environment" in resp.json()

    def test_alarm_state_values(self, admin_tc):
        for state in ("OK", "ALARM", "INSUFFICIENT_DATA"):
            import hive.api.admin as admin_mod

            admin_mod._alarm_cache.clear()
            with patch("hive.api.admin._cloudwatch_client") as mock_cw_factory:
                mock_cw = MagicMock()
                mock_cw.describe_alarms.return_value = self._make_describe_alarms_response(state)
                mock_cw_factory.return_value = mock_cw

                resp = admin_tc.get("/api/admin/alarms")

            assert resp.json()["alarms"][0]["state"] == state


class TestAdminAuditLog:
    """GET /api/admin/audit-log — admin-only compliance audit trail (#395)."""

    @pytest.fixture()
    def audit_storage(self):
        from hive.api import admin as admin_mod
        from hive.api.main import app
        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-admin", region="us-east-1")
        app.dependency_overrides[admin_mod._storage] = lambda: storage
        yield storage
        app.dependency_overrides.pop(admin_mod._storage, None)

    def test_returns_events_newest_first(self, admin_tc, audit_storage):
        from datetime import datetime, timedelta, timezone

        from hive.models import ActivityEvent, EventType

        base = datetime.now(timezone.utc).replace(microsecond=0)
        for i, etype in enumerate(
            [EventType.memory_created, EventType.memory_recalled, EventType.memory_deleted]
        ):
            audit_storage.log_audit_event(
                ActivityEvent(
                    event_type=etype,
                    client_id="c1",
                    metadata={"i": i},
                    timestamp=base - timedelta(seconds=i),
                )
            )

        resp = admin_tc.get("/api/admin/audit-log?days=1&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 3
        # Newest-first ordering
        assert body["items"][0]["event_type"] == "memory_created"
        assert body["items"][-1]["event_type"] == "memory_deleted"

    def test_filter_by_client_id(self, admin_tc, audit_storage):
        from hive.models import ActivityEvent, EventType

        for cid in ["c1", "c2", "c1"]:
            audit_storage.log_audit_event(
                ActivityEvent(event_type=EventType.memory_created, client_id=cid)
            )

        resp = admin_tc.get("/api/admin/audit-log?days=1&client_id=c1")
        items = resp.json()["items"]
        assert {it["client_id"] for it in items} == {"c1"}

    def test_filter_by_event_type(self, admin_tc, audit_storage):
        from hive.models import ActivityEvent, EventType

        audit_storage.log_audit_event(
            ActivityEvent(event_type=EventType.memory_created, client_id="c")
        )
        audit_storage.log_audit_event(
            ActivityEvent(event_type=EventType.memory_deleted, client_id="c")
        )

        resp = admin_tc.get("/api/admin/audit-log?days=1&event_type=memory_deleted")
        items = resp.json()["items"]
        assert {it["event_type"] for it in items} == {"memory_deleted"}

    def test_has_more_flag(self, admin_tc, audit_storage):
        from datetime import datetime, timedelta, timezone

        from hive.models import ActivityEvent, EventType

        base = datetime.now(timezone.utc)
        for i in range(5):
            audit_storage.log_audit_event(
                ActivityEvent(
                    event_type=EventType.memory_created,
                    client_id="c",
                    timestamp=base - timedelta(seconds=i),
                )
            )

        resp = admin_tc.get("/api/admin/audit-log?days=1&limit=3")
        body = resp.json()
        assert body["count"] == 3
        assert body["has_more"] is True

    def test_non_admin_forbidden(self, user_tc):
        resp = user_tc.get("/api/admin/audit-log?days=1")
        assert resp.status_code == 403

    def test_returns_events_straddling_midnight_utc(self, admin_tc, audit_storage):
        """Regression for #583.

        Events written a few seconds before midnight UTC land in the
        previous UTC date's shard. If the endpoint only queries "today"
        UTC, those events are invisible to a ``days=1`` query made just
        after midnight. The fix widens the shard scan by one day and
        applies a time-based cutoff.
        """
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from hive.models import ActivityEvent, EventType

        # Three events straddling the midnight UTC boundary. The first
        # two land on the pre-midnight shard, the last two on the
        # post-midnight shard.
        midnight = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)
        for offset_seconds in (-2, -1, 0, 1, 2):
            audit_storage.log_audit_event(
                ActivityEvent(
                    event_type=EventType.memory_created,
                    client_id="c",
                    timestamp=midnight + timedelta(seconds=offset_seconds),
                    metadata={"offset": offset_seconds},
                )
            )

        # Simulate a request made 1.1 seconds after midnight UTC.
        just_after_midnight = midnight + timedelta(seconds=1, microseconds=100_000)
        with patch("hive.api.admin._dt.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = just_after_midnight
            resp = admin_tc.get("/api/admin/audit-log?days=1&limit=50")

        assert resp.status_code == 200
        body = resp.json()
        # All five events should surface — both pre- and post-midnight
        # shards are scanned and none fall outside the 24h cutoff.
        assert body["count"] == 5, body

    def test_storage_factory_returns_storage(self):
        """_storage() dep factory returns a HiveStorage so the endpoint can run in prod."""
        from hive.api.admin import _storage
        from hive.storage import HiveStorage

        assert isinstance(_storage(), HiveStorage)
