# Copyright (c) 2026 John Carter. All rights reserved.
"""
Unit tests for the DELETE /api/account self-service account deletion endpoint.
"""

from __future__ import annotations

import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-account")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)

_USER_ID = "account-user-001"
_USER_CLAIMS = {"sub": _USER_ID, "role": "user", "email": "user@example.com"}


def _create_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="hive-unit-account",
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


@pytest.fixture()
def client():
    with mock_aws():
        _create_table()
        from hive.api import _auth as auth_mod
        from hive.api import account as account_mod
        from hive.api.main import app
        from hive.models import Memory, User
        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-account", region="us-east-1")

        user = User(user_id=_USER_ID, email="user@example.com", display_name="Test", role="user")
        storage.put_user(user)

        # Pre-seed a memory and a client so we can verify deletion
        memory = Memory(
            key="test-key",
            value="test-value",
            tags=["t1"],
            owner_client_id=_USER_ID,
            owner_user_id=_USER_ID,
        )
        storage.put_memory(memory)

        def _override_mgmt_user():
            return _USER_CLAIMS

        def _override_storage():
            return storage

        app.dependency_overrides[auth_mod.require_mgmt_user] = _override_mgmt_user
        app.dependency_overrides[account_mod._storage] = _override_storage
        yield TestClient(app), storage
        app.dependency_overrides.clear()


@pytest.fixture()
def unauthed_client():
    with mock_aws():
        _create_table()
        from hive.api.main import app

        app.dependency_overrides.clear()
        yield TestClient(app, raise_server_exceptions=False)


class TestStorageDep:
    def test_storage_dep_returns_hive_storage(self):
        with mock_aws():
            _create_table()
            from hive.api.account import _storage
            from hive.storage import HiveStorage

            result = _storage()
            assert isinstance(result, HiveStorage)


class TestDeleteAccount:
    def test_requires_confirm_true(self, client):
        tc, _ = client
        resp = tc.request("DELETE", "/api/account", json={"confirm": False})
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"]

    def test_requires_confirm_field(self, client):
        tc, _ = client
        resp = tc.request("DELETE", "/api/account", json={})
        assert resp.status_code == 400

    def test_deletes_account_and_data(self, client):
        tc, storage = client
        resp = tc.request("DELETE", "/api/account", json={"confirm": True})
        assert resp.status_code == 204
        # User record should be gone
        assert storage.get_user_by_id(_USER_ID) is None
        # Memory should be gone
        memories, _ = storage.list_all_memories(owner_user_id=_USER_ID, limit=10)
        assert memories == []

    def test_returns_404_if_user_not_found(self, client):
        tc, storage = client
        # Delete user first so it's missing on the DELETE call
        storage.delete_user(_USER_ID)
        resp = tc.request("DELETE", "/api/account", json={"confirm": True})
        assert resp.status_code == 404

    def test_deletes_clients(self, client):
        tc, storage = client
        from hive.auth.dcr import register_client
        from hive.models import ClientRegistrationRequest

        req = ClientRegistrationRequest(
            client_name="test-client",
            redirect_uris=["https://example.com/cb"],
            grant_types=["authorization_code"],
        )
        resp_dcr = register_client(req, storage)
        c = storage.get_client(resp_dcr.client_id)
        assert c is not None
        c.owner_user_id = _USER_ID
        storage.put_client(c)

        resp = tc.request("DELETE", "/api/account", json={"confirm": True})
        assert resp.status_code == 204
        # Client should be deleted
        assert storage.get_client(resp_dcr.client_id) is None

    def test_requires_auth(self, unauthed_client):
        resp = unauthed_client.request("DELETE", "/api/account", json={"confirm": True})
        assert resp.status_code in (401, 403)


class TestExportAccount:
    def test_returns_json_bundle_with_all_sections(self, client):
        import json

        tc, storage = client
        from hive.models import ActivityEvent, EventType, OAuthClient

        # Add a client owned by the user and an activity event under it
        c = OAuthClient(client_name="my-agent", owner_user_id=_USER_ID)
        storage.put_client(c)
        storage.log_event(
            ActivityEvent(
                event_type=EventType.memory_created,
                client_id=c.client_id,
                metadata={"key": "test-key"},
            )
        )

        resp = tc.get("/api/account/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert f"hive-export-{_USER_ID}" in disposition

        body = json.loads(resp.content)
        assert set(body.keys()) == {
            "exported_at",
            "user",
            "memories",
            "clients",
            "activity_log",
        }
        assert body["user"]["user_id"] == _USER_ID
        assert body["user"]["email"] == "user@example.com"
        assert len(body["memories"]) == 1
        assert body["memories"][0]["key"] == "test-key"
        assert any(client["client_id"] == c.client_id for client in body["clients"])
        assert any(e["client_id"] == c.client_id for e in body["activity_log"])

    def test_excludes_memories_from_other_users(self, client):
        import json

        tc, storage = client
        from hive.models import Memory

        storage.put_memory(
            Memory(
                key="someone-else",
                value="v",
                owner_client_id="other-client",
                owner_user_id="other-user",
            )
        )

        resp = tc.get("/api/account/export")
        body = json.loads(resp.content)
        keys = [m["key"] for m in body["memories"]]
        assert "someone-else" not in keys

    def test_excludes_activity_events_from_other_clients(self, client):
        import json

        tc, storage = client
        from hive.models import ActivityEvent, EventType

        storage.log_event(
            ActivityEvent(
                event_type=EventType.memory_created,
                client_id="not-my-client",
                metadata={"key": "leak"},
            )
        )

        resp = tc.get("/api/account/export")
        body = json.loads(resp.content)
        client_ids = {e["client_id"] for e in body["activity_log"]}
        assert "not-my-client" not in client_ids

    def test_rate_limited_after_first_export(self, client):
        tc, _ = client
        first = tc.get("/api/account/export")
        assert first.status_code == 200
        # Drain the stream so the counter has been written.
        _ = first.content

        second = tc.get("/api/account/export")
        assert second.status_code == 429
        assert second.headers.get("retry-after") == "300"

    def test_returns_404_if_user_not_found(self, client):
        tc, storage = client
        storage.delete_user(_USER_ID)
        resp = tc.get("/api/account/export")
        assert resp.status_code == 404

    def test_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/api/account/export")
        assert resp.status_code in (401, 403)

    def test_memory_expires_at_serialised_when_present(self, client):
        import json
        from datetime import datetime, timedelta, timezone

        tc, storage = client
        from hive.models import Memory

        storage.put_memory(
            Memory(
                key="ttl-key",
                value="v",
                owner_client_id=_USER_ID,
                owner_user_id=_USER_ID,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        resp = tc.get("/api/account/export")
        body = json.loads(resp.content)
        ttl_mem = next(m for m in body["memories"] if m["key"] == "ttl-key")
        assert ttl_mem["expires_at"] is not None

    def test_empty_sections_render_as_empty_arrays(self, client):
        import json

        tc, storage = client
        # Remove the seeded memory so the memories section is empty
        m = storage.get_memory_by_key("test-key")
        storage.delete_memory(m.memory_id)

        resp = tc.get("/api/account/export")
        body = json.loads(resp.content)
        assert body["memories"] == []
        assert body["clients"] == []
        assert body["activity_log"] == []

    def test_multiple_clients_and_events_render_with_separators(self, client):
        import json

        tc, storage = client
        from hive.models import ActivityEvent, EventType, OAuthClient

        # Two clients and two events for the user — exercises the inter-item
        # separator branches in the streamed JSON builder.
        c1 = OAuthClient(client_name="agent-1", owner_user_id=_USER_ID)
        c2 = OAuthClient(client_name="agent-2", owner_user_id=_USER_ID)
        storage.put_client(c1)
        storage.put_client(c2)
        for c in (c1, c2):
            storage.log_event(
                ActivityEvent(
                    event_type=EventType.memory_created,
                    client_id=c.client_id,
                    metadata={"key": "k"},
                )
            )

        resp = tc.get("/api/account/export")
        body = json.loads(resp.content)
        ids = {c["client_id"] for c in body["clients"]}
        assert {c1.client_id, c2.client_id}.issubset(ids)
        event_client_ids = [e["client_id"] for e in body["activity_log"]]
        assert len(event_client_ids) >= 2


# ---------------------------------------------------------------------------
# GET /api/account/stats  (#535)
# ---------------------------------------------------------------------------


class TestAccountStats:
    def setup_method(self):
        # The endpoint caches results in a module-level dict keyed by
        # (user_id, window). Wipe it between tests so cache-hit/miss
        # assertions stay deterministic.
        from hive.api.account import _STATS_CACHE

        _STATS_CACHE.clear()

    def test_unauthed_returns_401(self, unauthed_client):
        resp = unauthed_client.get("/api/account/stats")
        assert resp.status_code in (401, 403)

    def test_returns_all_eight_series(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats")
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "activity_heatmap",
            "top_recalled",
            "tag_distribution",
            "memory_growth",
            "quota",
            "freshness",
            "client_contribution",
            "tag_cooccurrence",
        ):
            assert key in body, f"missing series: {key}"
        assert body["window_days"] == 90  # default

    def test_default_window_is_90_days(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats")
        assert len(resp.json()["activity_heatmap"]) == 90

    def test_window_30(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats?window=30")
        assert resp.status_code == 200
        body = resp.json()
        assert body["window_days"] == 30
        assert len(body["activity_heatmap"]) == 30
        assert len(body["memory_growth"]) == 30

    def test_window_365(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats?window=365")
        assert resp.status_code == 200
        assert resp.json()["window_days"] == 365

    def test_invalid_window_returns_422(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats?window=7")
        assert resp.status_code == 422

    def test_quota_reports_memory_count_and_limit(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats")
        quota = resp.json()["quota"]
        assert quota["memory_count"] >= 1  # pre-seeded by the fixture
        # Default memory_limit is set via get_memory_limit() — a positive int
        # for a non-exempt, non-admin user.
        assert isinstance(quota["memory_limit"], int)
        assert quota["memory_limit"] > 0

    def test_tag_distribution_counts_seeded_tag(self, client):
        tc, _ = client
        resp = tc.get("/api/account/stats")
        tags = {t["tag"]: t["count"] for t in resp.json()["tag_distribution"]}
        assert tags.get("t1") == 1  # from the fixture's pre-seeded memory

    def test_freshness_has_entry_per_memory(self, client):
        tc, storage = client
        resp = tc.get("/api/account/stats")
        body = resp.json()
        assert len(body["freshness"]) == body["quota"]["memory_count"]
        entry = body["freshness"][0]
        assert entry["days_since_created"] >= 0
        assert entry["days_since_accessed"] >= 0
        # Key + tags ride along so the scatter tooltip + click-through can
        # work without a second API round-trip per dot.
        assert isinstance(entry["key"], str) and entry["key"]
        assert isinstance(entry["tags"], list)

    def test_top_recalled_only_includes_recalled_memories(self, client):
        from hive.models import Memory

        tc, storage = client
        # Add a second memory with recall_count > 0.
        hot = Memory(
            key="hot-key",
            value="hot",
            tags=["hot"],
            owner_client_id=_USER_ID,
            owner_user_id=_USER_ID,
            recall_count=5,
        )
        storage.put_memory(hot)

        resp = tc.get("/api/account/stats")
        keys = [m["key"] for m in resp.json()["top_recalled"]]
        # The pre-seeded "test-key" has recall_count=0 and must be filtered
        # out; only the hot memory should surface.
        assert keys == ["hot-key"]

    def test_client_names_maps_client_id_to_display_name(self, client):
        from hive.models import OAuthClient

        tc, storage = client
        # Register a named client owned by the user so the stats endpoint
        # has a display name to surface.
        oc = OAuthClient(client_name="Claude Code", owner_user_id=_USER_ID)
        storage.put_client(oc)

        resp = tc.get("/api/account/stats")
        names = resp.json()["client_names"]
        assert names.get(oc.client_id) == "Claude Code"

    def test_tag_cooccurrence_edges(self, client):
        from hive.models import Memory

        tc, storage = client
        # A memory carrying two tags should produce one (a, b) edge.
        storage.put_memory(
            Memory(
                key="pair",
                value="v",
                tags=["alpha", "beta"],
                owner_client_id=_USER_ID,
                owner_user_id=_USER_ID,
            )
        )

        resp = tc.get("/api/account/stats")
        edges = [(e["source"], e["target"], e["weight"]) for e in resp.json()["tag_cooccurrence"]]
        assert ("alpha", "beta", 1) in edges

    def test_cache_hit_returns_same_object(self, client, monkeypatch):
        # Two back-to-back calls with the same window must share the cache.
        # `assert first == second` alone isn't enough — deterministic input
        # produces identical output with or without caching. Spy on
        # `_compute_account_stats` and assert it runs exactly once across
        # both requests.
        from hive.api import account as account_mod

        tc, _ = client

        calls = 0
        original = account_mod._compute_account_stats

        def counting_compute(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(account_mod, "_compute_account_stats", counting_compute)

        first = tc.get("/api/account/stats")
        second = tc.get("/api/account/stats")

        assert first.status_code == 200
        assert second.status_code == 200
        assert calls == 1

    def test_cache_miss_after_ttl_elapses(self, client, monkeypatch):
        # Freeze `time.time()` so the cache ages past its TTL on the second
        # call without actually sleeping.
        from hive.api import account as account_mod

        tc, _ = client

        fake_time = [1_000_000.0]

        def fake_now():
            return fake_time[0]

        monkeypatch.setattr(account_mod.time, "time", fake_now)

        tc.get("/api/account/stats")
        # Count cached entries.
        assert len(account_mod._STATS_CACHE) == 1

        # Jump past TTL; the next call should recompute (same payload, but
        # the cache entry timestamp must advance).
        prev_ts = next(iter(account_mod._STATS_CACHE.values()))[0]
        fake_time[0] += account_mod._STATS_CACHE_TTL + 1

        tc.get("/api/account/stats")
        new_ts = next(iter(account_mod._STATS_CACHE.values()))[0]
        assert new_ts > prev_ts

    def test_different_windows_cached_independently(self, client):
        from hive.api import account as account_mod

        tc, _ = client
        tc.get("/api/account/stats?window=30")
        tc.get("/api/account/stats?window=90")
        # One entry per (user, window).
        assert len(account_mod._STATS_CACHE) == 2

    def test_own_events_populate_heatmap_and_client_contribution(self, client):
        """Exercises the `for e in own_events` loop bodies — needs both a
        client owned by the user AND an activity event whose client_id
        matches. Covers the activity_heatmap and client_contribution
        aggregation paths."""
        from hive.models import ActivityEvent, EventType, OAuthClient

        tc, storage = client

        owned_client = OAuthClient(client_name="my-agent", owner_user_id=_USER_ID)
        storage.put_client(owned_client)
        storage.log_event(
            ActivityEvent(
                event_type=EventType.memory_recalled,
                client_id=owned_client.client_id,
                metadata={"key": "test-key"},
            )
        )

        resp = tc.get("/api/account/stats")
        body = resp.json()

        # activity_heatmap should carry a non-zero bucket for today.
        today_bucket = next((b for b in body["activity_heatmap"] if b["count"] > 0), None)
        assert today_bucket is not None

        # client_contribution should surface the owned client's event.
        contrib_clients = {c["client_id"] for c in body["client_contribution"]}
        assert owned_client.client_id in contrib_clients

    def test_memory_predating_window_counts_as_baseline(self, client):
        """Exercises the pre-window baseline bump in memory_growth — needs
        a memory whose created_at is before the window start."""
        from datetime import datetime, timedelta, timezone

        from hive.models import Memory

        tc, storage = client

        old = Memory(
            key="ancient",
            value="v",
            tags=[],
            owner_client_id=_USER_ID,
            owner_user_id=_USER_ID,
        )
        # Force created_at well before the default 90-day window.
        old.created_at = datetime.now(timezone.utc) - timedelta(days=365)
        storage.put_memory(old)

        resp = tc.get("/api/account/stats?window=30")
        growth = resp.json()["memory_growth"]
        # The ancient memory is counted as baseline, so every point in the
        # 30-day window must already be at least 1 (plus the fixture's
        # pre-seeded memory).
        assert growth[0]["cumulative"] >= 1
