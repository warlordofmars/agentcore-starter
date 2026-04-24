# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for POST/GET/DELETE /api/keys endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hive.api.keys import generate_api_key, hash_api_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claims(user_id: str = "user-1", role: str = "user") -> dict:
    return {"sub": user_id, "role": role}


# ---------------------------------------------------------------------------
# generate_api_key / hash_api_key
# ---------------------------------------------------------------------------


class TestStorageDep:
    def test_storage_dep_returns_hive_storage(self):
        from moto import mock_aws

        with mock_aws():
            import boto3

            boto3.client("dynamodb", region_name="us-east-1").create_table(
                TableName="hive",
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
            from hive.api.keys import _storage
            from hive.storage import HiveStorage

            result = _storage()
            assert isinstance(result, HiveStorage)


class TestGenerateApiKey:
    def test_has_hive_sk_prefix(self):
        plaintext, _ = generate_api_key()
        assert plaintext.startswith("hive_sk_")

    def test_hash_is_sha256_hex(self):
        import hashlib

        plaintext, key_hash = generate_api_key()
        assert key_hash == hashlib.sha256(plaintext.encode()).hexdigest()
        assert len(key_hash) == 64

    def test_two_calls_produce_different_keys(self):
        p1, _ = generate_api_key()
        p2, _ = generate_api_key()
        assert p1 != p2

    def test_hash_api_key(self):
        import hashlib

        plaintext = "hive_sk_test"
        assert hash_api_key(plaintext) == hashlib.sha256(b"hive_sk_test").hexdigest()


# ---------------------------------------------------------------------------
# Fixtures — use a real in-memory app like test_api.py
# ---------------------------------------------------------------------------


@pytest.fixture()
def _app_and_storage():
    """Spin up the FastAPI app with a mocked HiveStorage."""
    from fastapi.testclient import TestClient

    from hive.api import _auth as auth_mod
    from hive.api import keys as keys_mod
    from hive.api.main import app

    storage = MagicMock()
    storage.list_api_keys_for_user.return_value = []
    storage.get_api_key_by_id.return_value = None

    claims = _make_claims()
    app.dependency_overrides[auth_mod.require_mgmt_user] = lambda: claims
    app.dependency_overrides[keys_mod._storage] = lambda: storage
    try:
        yield TestClient(app), storage
    finally:
        app.dependency_overrides.pop(auth_mod.require_mgmt_user, None)
        app.dependency_overrides.pop(keys_mod._storage, None)


class TestApiKeysEndpoints:
    @pytest.fixture(autouse=True)
    def setup(self, _app_and_storage):
        self.tc, self.storage = _app_and_storage

    def _auth_header(self, user_id: str = "user-1") -> dict:
        return {"Authorization": "Bearer fake-mgmt-jwt"}

    def test_list_keys_returns_empty(self):
        resp = self.tc.get("/api/keys", headers=self._auth_header())
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_keys_returns_items(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="user-1",
            name="CI",
            key_hash="abc",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        self.storage.list_api_keys_for_user.return_value = [k]
        resp = self.tc.get("/api/keys", headers=self._auth_header())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "CI"
        assert "key_hash" not in data[0]

    def test_create_key_returns_201_with_plaintext(self):
        from hive.models import ApiKey

        captured = {}

        def capture_put(key: ApiKey) -> None:
            captured["key"] = key

        self.storage.put_api_key.side_effect = capture_put
        resp = self.tc.post(
            "/api/keys",
            json={"name": "My Key", "scope": "memories:read"},
            headers=self._auth_header(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "plaintext_key" in data
        assert data["plaintext_key"].startswith("hive_sk_")
        assert data["name"] == "My Key"
        assert data["scope"] == "memories:read"
        assert "key_hash" not in data

    def test_create_key_uses_default_scope(self):
        resp = self.tc.post(
            "/api/keys",
            json={"name": "Default"},
            headers=self._auth_header(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scope"] == "memories:read memories:write"

    def test_delete_key_returns_204(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="user-1",
            name="To delete",
            key_hash="abc",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        self.storage.get_api_key_by_id.return_value = k
        self.storage.delete_api_key.return_value = True
        resp = self.tc.delete(f"/api/keys/{k.key_id}", headers=self._auth_header())
        assert resp.status_code == 204

    def test_delete_key_not_found_returns_404(self):
        self.storage.get_api_key_by_id.return_value = None
        resp = self.tc.delete("/api/keys/no-such-key", headers=self._auth_header())
        assert resp.status_code == 404

    def test_delete_key_owned_by_other_user_returns_403(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="other-user",
            name="Not mine",
            key_hash="abc",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        self.storage.get_api_key_by_id.return_value = k
        resp = self.tc.delete(f"/api/keys/{k.key_id}", headers=self._auth_header())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Auth-required tests — run without dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture()
def _unauthed_client():
    from fastapi.testclient import TestClient

    from hive.api.main import app

    app.dependency_overrides.clear()
    yield TestClient(app, raise_server_exceptions=False)


class TestApiKeysRequireAuth:
    @pytest.fixture(autouse=True)
    def setup(self, _unauthed_client):
        self.tc = _unauthed_client

    def test_list_keys_requires_auth(self):
        resp = self.tc.get("/api/keys")
        assert resp.status_code == 401

    def test_create_key_requires_auth(self):
        resp = self.tc.post("/api/keys", json={"name": "x"})
        assert resp.status_code == 401
