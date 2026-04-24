# Copyright (c) 2026 John Carter. All rights reserved.
"""
E2E tests for the admin-only CloudWatch metrics and cost endpoints.
Requires:
  HIVE_API_URL       — deployed management API URL
  HIVE_ADMIN_EMAIL   — admin email address (resolved against allowed-emails list)

These tests verify structure only — they do not assert specific metric values,
since CloudWatch data may lag or be sparse depending on recent traffic.
"""

from __future__ import annotations

import os

import httpx
import pytest

API_URL = os.environ.get("HIVE_API_URL", "")

pytestmark = pytest.mark.skipif(
    not API_URL,
    reason="HIVE_API_URL not set — skipping admin e2e tests",
)

_EXPECTED_TOOLS = ["remember", "recall", "forget", "listmemories", "summarizecontext"]
_EXPECTED_METRIC_PREFIXES = ["inv_", "err_", "p99_"]


def _assert_metric_structure(data: dict) -> None:
    """Assert that a metrics response has the expected shape."""
    assert "period" in data
    assert "environment" in data
    assert "metrics" in data
    metrics = data["metrics"]
    assert isinstance(metrics, dict)

    for tool in _EXPECTED_TOOLS:
        for prefix in _EXPECTED_METRIC_PREFIXES:
            key = f"{prefix}{tool}"
            assert key in metrics, f"Missing metric key: {key}"
            entry = metrics[key]
            assert "timestamps" in entry
            assert "values" in entry
            assert isinstance(entry["timestamps"], list)
            assert isinstance(entry["values"], list)

    assert "tokens_issued" in metrics
    assert "token_failures" in metrics


@pytest.mark.asyncio
class TestAdminMetricsE2E:
    async def test_metrics_1h(self, live_admin_token):
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                params={"period": "1h"},
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            _assert_metric_structure(resp.json())

    async def test_metrics_24h(self, live_admin_token):
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                params={"period": "24h"},
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            _assert_metric_structure(data)
            assert data["period"] == "24h"

    async def test_metrics_7d(self, live_admin_token):
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                params={"period": "7d"},
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            _assert_metric_structure(resp.json())

    async def test_metrics_invalid_period(self, live_admin_token):
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                params={"period": "99y"},
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 422

    async def test_metrics_requires_admin(self, live_token):
        """MCP access tokens must not grant access to admin endpoints."""
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                headers={"Authorization": f"Bearer {live_token}"},
            )
            assert resp.status_code == 401

    async def test_metrics_has_data_after_synthetic_traffic(self, live_admin_token):
        """After synthetic traffic has run, the 7d window should have invocation data."""
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/metrics",
                params={"period": "7d"},
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200
            metrics = resp.json()["metrics"]
            # At least one tool should have invocation data points
            total_invocations = sum(
                sum(metrics[f"inv_{t}"]["values"])
                for t in _EXPECTED_TOOLS
                if metrics.get(f"inv_{t}", {}).get("values")
            )
            assert total_invocations > 0, (
                "No invocation data found in 7d window — synthetic traffic may not have run yet"
            )


@pytest.mark.asyncio
class TestAdminCostsE2E:
    async def test_costs_returns_200(self, live_admin_token):
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/costs",
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text

    async def test_costs_response_structure(self, live_admin_token):
        """Response must contain required keys regardless of whether billing data exists."""
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/costs",
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "monthly" in data, "Response missing 'monthly' key"
            assert "daily" in data, "Response missing 'daily' key"
            assert "currency" in data, "Response missing 'currency' key"
            assert "environment" in data, "Response missing 'environment' key"
            assert isinstance(data["monthly"], list)
            assert isinstance(data["daily"], list)

    async def test_costs_monthly_items_have_correct_shape(self, live_admin_token):
        """Each monthly item must have period, total, and by_service keys."""
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/costs",
                headers={"Authorization": f"Bearer {live_admin_token}"},
            )
            assert resp.status_code == 200, resp.text
            monthly = resp.json()["monthly"]
            for item in monthly:
                assert "period" in item, f"Monthly item missing 'period': {item}"
                assert "total" in item, f"Monthly item missing 'total': {item}"
                assert "by_service" in item, f"Monthly item missing 'by_service': {item}"
                assert isinstance(item["total"], (int, float))
                assert isinstance(item["by_service"], dict)

    async def test_costs_requires_admin(self, live_token):
        """MCP access tokens must not grant access to admin cost endpoints."""
        async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http:
            resp = await http.get(
                "/api/admin/costs",
                headers={"Authorization": f"Bearer {live_token}"},
            )
            assert resp.status_code == 401
