# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for Hive data models — no AWS deps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hive.models import (
    AuthorizationCode,
    Memory,
    OAuthClient,
    OAuthClientType,
    Token,
)


class TestMemory:
    def test_default_fields(self):
        m = Memory(key="test", value="hello", owner_client_id="client-1")
        assert m.memory_id  # auto-generated UUID
        assert m.tags == []
        assert m.created_at.tzinfo == timezone.utc

    def test_to_dynamo_meta(self):
        m = Memory(key="foo", value="bar", tags=["t1"], owner_client_id="c1")
        item = m.to_dynamo_meta()
        assert item["PK"] == f"MEMORY#{m.memory_id}"
        assert item["SK"] == "META"
        assert item["key"] == "foo"
        assert item["value"] == "bar"
        assert item["tags"] == ["t1"]
        assert item["GSI1PK"] == "KEY#foo"

    def test_to_dynamo_tag_items(self):
        m = Memory(key="foo", value="bar", tags=["alpha", "beta"], owner_client_id="c1")
        tag_items = m.to_dynamo_tag_items()
        assert len(tag_items) == 2
        sks = {item["SK"] for item in tag_items}
        assert sks == {"TAG#alpha", "TAG#beta"}
        for item in tag_items:
            assert item["GSI2PK"] in {"TAG#alpha", "TAG#beta"}

    def test_from_dynamo_roundtrip(self):
        m = Memory(key="k", value="v", tags=["x"], owner_client_id="c1")
        item = m.to_dynamo_meta()
        m2 = Memory.from_dynamo(item)
        assert m2.memory_id == m.memory_id
        assert m2.key == m.key
        assert m2.value == m.value
        assert m2.tags == m.tags

    def test_no_tags_produces_no_tag_items(self):
        m = Memory(key="k", value="v", owner_client_id="c1")
        assert m.to_dynamo_tag_items() == []

    def test_default_value_type_is_text(self):
        # #497: existing memories stay "text" with no pointer
        # fields, so legacy items round-trip byte-identical through
        # to_dynamo_meta.
        m = Memory(key="k", value="v", owner_client_id="c1")
        assert m.value_type == "text"
        assert m.s3_uri is None
        assert m.content_type is None
        assert m.size_bytes is None
        item = m.to_dynamo_meta()
        # None of the large-memory fields appear on the wire for
        # inline text — legacy readers see an unchanged item.
        assert "value_type" not in item
        assert "s3_uri" not in item
        assert "content_type" not in item
        assert "size_bytes" not in item

    def test_large_memory_fields_round_trip_through_dynamo(self):
        m = Memory(
            key="big",
            value="",
            value_type="text-large",
            s3_uri="s3://hive-memory-blobs/u-1/mem-1",
            content_type="text/plain; charset=utf-8",
            size_bytes=500_000,
            owner_client_id="c1",
        )
        item = m.to_dynamo_meta()
        assert item["value_type"] == "text-large"
        assert item["s3_uri"] == "s3://hive-memory-blobs/u-1/mem-1"
        assert item["content_type"] == "text/plain; charset=utf-8"
        assert item["size_bytes"] == 500_000
        # None-value is serialised as an empty string so readers
        # that expect a str keep working.
        assert item["value"] == ""

        m2 = Memory.from_dynamo(item)
        assert m2.value_type == "text-large"
        assert m2.s3_uri == "s3://hive-memory-blobs/u-1/mem-1"
        assert m2.content_type == "text/plain; charset=utf-8"
        assert m2.size_bytes == 500_000

    def test_legacy_dynamo_item_without_value_type_defaults_to_text(self):
        # Pre-#497 META items have no value_type / s3_uri / etc —
        # from_dynamo must default them so the read path stays
        # backwards compatible.
        item = {
            "memory_id": "mem-1",
            "key": "legacy",
            "value": "legacy-value",
            "created_at": "2026-04-20T00:00:00+00:00",
            "updated_at": "2026-04-20T00:00:00+00:00",
            "owner_client_id": "c1",
        }
        m = Memory.from_dynamo(item)
        assert m.value_type == "text"
        assert m.s3_uri is None
        assert m.size_bytes is None

    def test_default_recall_fields(self):
        m = Memory(key="k", value="v", owner_client_id="c1")
        assert m.recall_count == 0
        assert m.last_accessed_at is None

    def test_recall_fields_persist_and_roundtrip(self):
        from datetime import datetime, timezone

        accessed = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        m = Memory(
            key="k",
            value="v",
            owner_client_id="c1",
            recall_count=7,
            last_accessed_at=accessed,
        )
        item = m.to_dynamo_meta()
        assert item["recall_count"] == 7
        assert item["last_accessed_at"] == accessed.isoformat()
        m2 = Memory.from_dynamo(item)
        assert m2.recall_count == 7
        assert m2.last_accessed_at == accessed

    def test_from_dynamo_tolerates_missing_recall_fields(self):
        # Items written before this field existed won't have recall_count or
        # last_accessed_at; Memory.from_dynamo must default them cleanly.
        m = Memory(key="k", value="v", owner_client_id="c1")
        item = m.to_dynamo_meta()
        item.pop("recall_count", None)
        item.pop("last_accessed_at", None)
        m2 = Memory.from_dynamo(item)
        assert m2.recall_count == 0
        assert m2.last_accessed_at is None

    def test_version_reflects_updated_at(self):
        """Memory.version is the updated_at isoformat — advances on every write."""
        m = Memory(key="k", value="v", owner_client_id="c1")
        assert m.version == m.updated_at.isoformat()
        old = m.version
        m.updated_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert m.version != old
        assert m.version == m.updated_at.isoformat()


class TestOAuthClient:
    def test_defaults(self):
        c = OAuthClient(client_name="Test App")
        assert c.client_id  # UUID
        assert c.client_type == OAuthClientType.public
        assert c.client_secret is None

    def test_to_dynamo(self):
        c = OAuthClient(client_name="App", client_secret="secret")
        item = c.to_dynamo()
        assert item["PK"] == f"CLIENT#{c.client_id}"
        assert item["SK"] == "META"
        assert item["client_secret"] == "secret"

    def test_from_dynamo_roundtrip(self):
        c = OAuthClient(client_name="App")
        item = c.to_dynamo()
        c2 = OAuthClient.from_dynamo(item)
        assert c2.client_id == c.client_id
        assert c2.client_name == c.client_name


class TestToken:
    def _make_token(self, **kwargs) -> Token:
        now = datetime.now(timezone.utc)
        return Token(
            client_id="c1",
            scope="memories:read",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
            **kwargs,
        )

    def test_valid_token(self):
        t = self._make_token()
        assert t.is_valid
        assert not t.is_expired

    def test_expired_token(self):
        now = datetime.now(timezone.utc)
        t = Token(
            client_id="c1",
            scope="s",
            issued_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        assert t.is_expired
        assert not t.is_valid

    def test_revoked_token(self):
        t = self._make_token(revoked=True)
        assert not t.is_valid

    def test_to_dynamo_ttl(self):
        t = self._make_token()
        item = t.to_dynamo()
        assert item["PK"] == f"TOKEN#{t.jti}"
        assert "ttl" in item
        assert isinstance(item["ttl"], int)

    def test_from_dynamo_roundtrip(self):
        t = self._make_token()
        item = t.to_dynamo()
        t2 = Token.from_dynamo(item)
        assert t2.jti == t.jti
        assert t2.client_id == t.client_id


class TestAuthorizationCode:
    def test_to_dynamo_ttl(self):
        now = datetime.now(timezone.utc)
        code = AuthorizationCode(
            client_id="c1",
            redirect_uri="http://localhost/cb",
            scope="s",
            code_challenge="abc",
            expires_at=now + timedelta(minutes=5),
        )
        item = code.to_dynamo()
        assert item["PK"] == f"AUTHCODE#{code.code}"
        assert item["ttl"] == int(code.expires_at.timestamp())

    def test_from_dynamo_roundtrip(self):
        now = datetime.now(timezone.utc)
        code = AuthorizationCode(
            client_id="c1",
            redirect_uri="http://localhost/cb",
            scope="s",
            code_challenge="abc",
            expires_at=now + timedelta(minutes=5),
        )
        item = code.to_dynamo()
        code2 = AuthorizationCode.from_dynamo(item)
        assert code2.code == code.code
        assert code2.code_challenge == code.code_challenge


class TestApiKey:
    def test_to_and_from_dynamo_no_expiry(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="CI",
            key_hash="abc123",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        item = k.to_dynamo()
        assert item["PK"] == f"APIKEY#{k.key_id}"
        assert item["SK"] == "META"
        assert "expires_at" not in item
        assert "ttl" not in item

        k2 = ApiKey.from_dynamo(item)
        assert k2.key_id == k.key_id
        assert k2.expires_at is None
        assert k2.revoked is False

    def test_to_and_from_dynamo_with_expiry(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Expiring",
            key_hash="def456",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            expires_at=datetime(2027, 4, 1, tzinfo=timezone.utc),
        )
        item = k.to_dynamo()
        assert "expires_at" in item
        assert "ttl" in item

        k2 = ApiKey.from_dynamo(item)
        assert k2.expires_at is not None

    def test_is_valid_active_key(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Active",
            key_hash="hash",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        assert k.is_valid is True
        assert k.is_expired is False

    def test_is_valid_revoked(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Revoked",
            key_hash="hash",
            revoked=True,
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        assert k.is_valid is False

    def test_is_valid_expired(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Expired",
            key_hash="hash",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        assert k.is_expired is True
        assert k.is_valid is False

    def test_api_key_response_from_api_key(self):
        from datetime import datetime, timezone

        from hive.models import ApiKey, ApiKeyResponse

        k = ApiKey(
            owner_user_id="u1",
            name="Test",
            key_hash="hash",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        resp = ApiKeyResponse.from_api_key(k)
        assert resp.key_id == k.key_id
        assert resp.name == "Test"
        assert "key_hash" not in resp.model_dump()
