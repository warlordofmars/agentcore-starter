# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for OAuth auth logic — fully mocked, no AWS deps."""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from hive.auth.dcr import register_client
from hive.auth.tokens import decode_jwt, issue_jwt, validate_bearer_token
from hive.models import (
    ClientRegistrationRequest,
    Token,
)

os.environ.setdefault("HIVE_TABLE_NAME", "hive-unit-auth")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")
os.environ.pop("DYNAMODB_ENDPOINT", None)

# ---------------------------------------------------------------------------
# DCR tests
# ---------------------------------------------------------------------------


class TestDCR:
    def _storage(self, client=None):
        s = MagicMock()
        s.get_client.return_value = client
        return s

    def test_register_public_client(self):
        storage = self._storage()
        req = ClientRegistrationRequest(
            client_name="Test Agent",
            redirect_uris=["http://localhost/cb"],
        )
        resp = register_client(req, storage)
        assert resp.client_id
        assert resp.client_secret is None
        assert resp.token_endpoint_auth_method == "none"
        storage.put_client.assert_called_once()

    def test_register_confidential_client(self):
        storage = self._storage()
        req = ClientRegistrationRequest(
            client_name="Server App",
            token_endpoint_auth_method="client_secret_post",
        )
        resp = register_client(req, storage)
        assert resp.client_secret is not None
        assert len(resp.client_secret) > 20

    def test_unsupported_grant_type_raises(self):
        storage = self._storage()
        req = ClientRegistrationRequest(
            client_name="Bad",
            grant_types=["password"],
        )
        with pytest.raises(ValueError, match="Unsupported grant_types"):
            register_client(req, storage)

    def test_unsupported_auth_method_raises(self):
        storage = self._storage()
        req = ClientRegistrationRequest(
            client_name="Bad",
            token_endpoint_auth_method="private_key_jwt",
        )
        with pytest.raises(ValueError, match="Unsupported token_endpoint_auth_method"):
            register_client(req, storage)


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


def _make_token(**kwargs) -> Token:
    now = datetime.now(timezone.utc)
    return Token(
        client_id="client-1",
        scope="memories:read",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        **kwargs,
    )


class TestTokenIssuance:
    def test_issue_and_decode(self):
        t = _make_token()
        jwt_str = issue_jwt(t)
        claims = decode_jwt(jwt_str)
        assert claims["jti"] == t.jti
        assert claims["sub"] == t.client_id
        assert claims["scope"] == t.scope

    def test_tampered_jwt_raises(self):
        from jose import JWTError

        t = _make_token()
        jwt_str = issue_jwt(t)
        tampered = jwt_str[:-4] + "XXXX"
        with pytest.raises(JWTError):
            decode_jwt(tampered)


class TestValidateBearerToken:
    def _storage_with_token(self, token: Token):
        s = MagicMock()
        s.get_token.return_value = token
        return s

    def test_valid_token(self):
        t = _make_token()
        storage = self._storage_with_token(t)
        jwt_str = issue_jwt(t)
        result = validate_bearer_token(f"Bearer {jwt_str}", storage)
        assert result.jti == t.jti

    def test_missing_header_raises(self):
        storage = MagicMock()
        with pytest.raises(ValueError, match="Missing"):
            validate_bearer_token(None, storage)

    def test_bad_scheme_raises(self):
        storage = MagicMock()
        with pytest.raises(ValueError, match="Bearer"):
            validate_bearer_token("Basic abc", storage)

    def test_revoked_token_raises(self):
        t = _make_token(revoked=True)
        storage = self._storage_with_token(t)
        jwt_str = issue_jwt(t)
        with pytest.raises(ValueError, match="revoked"):
            validate_bearer_token(f"Bearer {jwt_str}", storage)

    def test_expired_token_raises(self):
        now = datetime.now(timezone.utc)
        t = Token(
            client_id="c1",
            scope="s",
            issued_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        # JWT exp check will fire before DynamoDB lookup for expired tokens

        jwt_str = issue_jwt(t)
        storage = MagicMock()
        with pytest.raises(ValueError):
            validate_bearer_token(f"Bearer {jwt_str}", storage)

    def test_token_not_in_storage_raises(self):
        t = _make_token()
        storage = MagicMock()
        storage.get_token.return_value = None
        jwt_str = issue_jwt(t)
        with pytest.raises(ValueError, match="not found"):
            validate_bearer_token(f"Bearer {jwt_str}", storage)


# ---------------------------------------------------------------------------
# OAuth 2.1 endpoint tests (FastAPI routes in auth/oauth.py)
# ---------------------------------------------------------------------------


def _create_table(table_name: str = "hive-unit-auth") -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
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


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256-challenge) pair."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@pytest.fixture()
def oauth_client():
    """moto-backed app with a registered OAuth client that has a redirect_uri."""
    with mock_aws():
        _create_table()
        from fastapi.testclient import TestClient

        from hive.api.main import app
        from hive.auth.oauth import get_storage
        from hive.models import OAuthClient
        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        client = OAuthClient(
            client_name="Test OAuth App",
            redirect_uris=["https://app.example.com/cb"],
        )
        storage.put_client(client)

        app.dependency_overrides[get_storage] = lambda: storage
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc, storage, client
        app.dependency_overrides.clear()


class TestOAuthDiscovery:
    def test_discovery_document(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_endpoint" in data
        assert "token_endpoint" in data
        assert "code_challenge_methods_supported" in data
        assert "S256" in data["code_challenge_methods_supported"]

    def test_protected_resource_metadata(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        data = resp.json()
        assert "resource" in data
        assert "/mcp" in data["resource"]
        assert "authorization_servers" in data
        assert len(data["authorization_servers"]) > 0
        assert "scopes_supported" in data
        assert "memories:read" in data["scopes_supported"]
        assert "memories:write" in data["scopes_supported"]
        assert data["bearer_methods_supported"] == ["header"]


class TestOAuthRegister:
    def test_register_public_client(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/register",
            json={
                "client_name": "My Agent",
                "redirect_uris": ["http://localhost/cb"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"]
        assert "client_secret" not in data  # omitted for public clients (RFC 7591)

    def test_register_invalid_grant_type_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/register",
            json={"client_name": "Bad", "grant_types": ["password"]},
        )
        assert resp.status_code == 400


class TestOAuthAuthorize:
    def test_valid_authorize_redirects(self, oauth_client):
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        with patch(
            "hive.auth.google.google_authorization_url",
            return_value="https://accounts.google.com/mock?state=test",
        ):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "state": "xyz",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "accounts.google.com" in location

    def test_unknown_client_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        _, challenge = _pkce_pair()
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": "no-such-client",
                "redirect_uri": "https://app.example.com/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        assert resp.status_code == 400

    def test_unregistered_redirect_uri_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client.client_id,
                "redirect_uri": "https://evil.com/steal",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        assert resp.status_code == 400

    def test_missing_pkce_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client.client_id,
                "redirect_uri": "https://app.example.com/cb",
                "code_challenge": "",
            },
        )
        assert resp.status_code == 400

    def test_unsupported_response_type_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "token",
                "client_id": client.client_id,
                "redirect_uri": "https://app.example.com/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        assert resp.status_code == 400

    def test_bypass_mode_issues_code_directly(self, oauth_client):
        """When HIVE_BYPASS_GOOGLE_AUTH is set, authorize redirects directly with code."""
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        with patch("hive.auth.oauth._BYPASS_GOOGLE_AUTH", True):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "state": "bypass-state",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "code=" in location
        assert "state=bypass-state" in location
        assert "accounts.google.com" not in location

    def test_bypass_test_email_associates_user(self, oauth_client):
        """test_email in bypass mode creates a user and sets client.owner_user_id."""
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        with (
            patch("hive.auth.oauth._BYPASS_GOOGLE_AUTH", True),
            patch("hive.auth.google.is_email_allowed", return_value=True),
            patch("hive.auth.google.is_admin_email", return_value=False),
        ):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "test_email": "bypass@example.com",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        updated = storage.get_client(client.client_id)
        assert updated is not None
        assert updated.owner_user_id is not None
        user = storage.get_user_by_id(updated.owner_user_id)
        assert user is not None
        assert user.email == "bypass@example.com"

    def test_bypass_test_email_disallowed_returns_403(self, oauth_client):
        """test_email that fails the allowlist check returns 403."""
        tc, _, client = oauth_client
        _, challenge = _pkce_pair()
        with (
            patch("hive.auth.oauth._BYPASS_GOOGLE_AUTH", True),
            patch("hive.auth.google.is_email_allowed", return_value=False),
        ):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "test_email": "blocked@example.com",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 403

    def test_bypass_test_email_assigns_admin_role(self, oauth_client):
        """test_email matching is_admin_email creates user with admin role."""
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        with (
            patch("hive.auth.oauth._BYPASS_GOOGLE_AUTH", True),
            patch("hive.auth.google.is_email_allowed", return_value=True),
            patch("hive.auth.google.is_admin_email", return_value=True),
        ):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "test_email": "admin@example.com",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        updated = storage.get_client(client.client_id)
        user = storage.get_user_by_id(updated.owner_user_id)
        assert user.role == "admin"

    def test_bypass_test_email_updates_existing_user(self, oauth_client):
        """test_email in bypass mode updates display_name and role for an existing user."""
        tc, storage, client = oauth_client
        now = datetime.now(timezone.utc)
        from hive.models import User as UserModel

        existing = UserModel(
            email="existing@example.com",
            display_name="oldname",
            role="user",
            created_at=now,
        )
        storage.put_user(existing)

        _, challenge = _pkce_pair()
        with (
            patch("hive.auth.oauth._BYPASS_GOOGLE_AUTH", True),
            patch("hive.auth.google.is_email_allowed", return_value=True),
            patch("hive.auth.google.is_admin_email", return_value=True),
        ):
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "test_email": "existing@example.com",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        user = storage.get_user_by_email("existing@example.com")
        assert user is not None
        assert user.display_name == "existing"
        assert user.role == "admin"


# ---------------------------------------------------------------------------
# Google OAuth callback endpoint tests
# ---------------------------------------------------------------------------


class TestGoogleCallback:
    def _setup_pending(self, storage, client):
        """Create a PendingAuth record in storage and return it."""
        return storage.create_pending_auth(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="memories:read",
            code_challenge=_pkce_pair()[1],
            code_challenge_method="S256",
            original_state="original-xyz",
        )

    def test_success_redirects_with_code(self, oauth_client):
        tc, storage, client = oauth_client
        pending = self._setup_pending(storage, client)
        fake_claims = {"email": "user@example.com", "email_verified": True, "sub": "uid1"}
        with (
            patch("hive.auth.google.exchange_google_code", return_value="fake-id-token"),
            patch("hive.auth.google.verify_google_id_token", return_value=fake_claims),
            patch("hive.auth.google.is_email_allowed", return_value=True),
        ):
            resp = tc.get(
                "/oauth/google/callback",
                params={"code": "goog-code", "state": pending.state},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "code=" in location
        assert "state=original-xyz" in location

    def test_error_param_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.get(
            "/oauth/google/callback",
            params={"error": "access_denied", "state": "s"},
        )
        assert resp.status_code == 400

    def test_missing_code_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.get("/oauth/google/callback", params={"state": "s"})
        assert resp.status_code == 400

    def test_invalid_state_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.get(
            "/oauth/google/callback",
            params={"code": "c", "state": "no-such-state"},
        )
        assert resp.status_code == 400

    def test_expired_state_returns_400(self, oauth_client):
        from unittest.mock import patch as _patch

        tc, storage, client = oauth_client
        pending = self._setup_pending(storage, client)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        with _patch("hive.auth.oauth.datetime") as mock_dt:
            mock_dt.now.return_value = future
            resp = tc.get(
                "/oauth/google/callback",
                params={"code": "c", "state": pending.state},
            )
        assert resp.status_code == 400

    def test_unverified_email_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        pending = self._setup_pending(storage, client)
        fake_claims = {"email": "user@example.com", "email_verified": False, "sub": "uid1"}
        with (
            patch("hive.auth.google.exchange_google_code", return_value="fake-id-token"),
            patch("hive.auth.google.verify_google_id_token", return_value=fake_claims),
        ):
            resp = tc.get(
                "/oauth/google/callback",
                params={"code": "c", "state": pending.state},
            )
        assert resp.status_code == 400

    def test_disallowed_email_returns_403(self, oauth_client):
        tc, storage, client = oauth_client
        pending = self._setup_pending(storage, client)
        fake_claims = {"email": "stranger@example.com", "email_verified": True, "sub": "uid2"}
        with (
            patch("hive.auth.google.exchange_google_code", return_value="fake-id-token"),
            patch("hive.auth.google.verify_google_id_token", return_value=fake_claims),
            patch("hive.auth.google.is_email_allowed", return_value=False),
        ):
            resp = tc.get(
                "/oauth/google/callback",
                params={"code": "c", "state": pending.state},
            )
        assert resp.status_code == 403

    def test_google_token_error_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        pending = self._setup_pending(storage, client)
        with patch("hive.auth.google.exchange_google_code", side_effect=Exception("Google error")):
            resp = tc.get(
                "/oauth/google/callback",
                params={"code": "bad-code", "state": pending.state},
            )
        assert resp.status_code == 400


class TestOAuthToken:
    def _get_auth_code(self, tc, storage, client) -> tuple[str, str]:
        """Create an auth code directly in storage, bypassing Google OAuth."""
        verifier, challenge = _pkce_pair()
        auth_code = storage.create_auth_code(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope=client.scope or "memories:read memories:write",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        return auth_code.code, verifier

    def test_authorization_code_grant(self, oauth_client):
        tc, storage, client = oauth_client
        code, verifier = self._get_auth_code(tc, storage, client)
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": client.client_id,
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "Bearer"

    def test_invalid_pkce_verifier_rejected(self, oauth_client):
        tc, storage, client = oauth_client
        code, _ = self._get_auth_code(tc, storage, client)
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": client.client_id,
                "code_verifier": "wrong-verifier",
            },
        )
        assert resp.status_code == 400

    def test_refresh_token_grant(self, oauth_client):
        tc, storage, client = oauth_client
        # First do a full auth code flow to get a refresh token
        code, verifier = self._get_auth_code(tc, storage, client)
        token_resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": client.client_id,
                "code_verifier": verifier,
            },
        )
        refresh_token = token_resp.json()["refresh_token"]

        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client.client_id,
                "refresh_token": refresh_token,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_missing_client_id_returns_400(self, oauth_client):
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "authorization_code"},
        )
        assert resp.status_code == 400

    def test_unsupported_grant_type_returns_400(self, oauth_client):
        tc, storage, client = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "password", "client_id": client.client_id},
        )
        assert resp.status_code == 400

    def test_already_used_code_rejected(self, oauth_client):
        tc, storage, client = oauth_client
        code, verifier = self._get_auth_code(tc, storage, client)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://app.example.com/cb",
            "client_id": client.client_id,
            "code_verifier": verifier,
        }
        tc.post("/oauth/token", data=data)  # first use — succeeds
        resp = tc.post("/oauth/token", data=data)  # second use — rejected
        assert resp.status_code == 400

    def test_concurrent_redemption_loser_gets_400(self, oauth_client):
        """#584 regression — simulates the race where two requests both
        pass the `auth_code.used` pre-check and the storage-level
        conditional write picks one winner.

        We can't reliably trigger the race in-process against moto, so
        patch `mark_auth_code_used` to raise `AuthCodeAlreadyUsed` on
        the only call and assert the endpoint surfaces a clean 400
        instead of a 500. This verifies the `try/except` in
        `oauth.py`, which is the half of the fix the storage-level
        concurrency test in `test_storage.py` doesn't reach.
        """
        from unittest.mock import patch

        from hive.storage import AuthCodeAlreadyUsed

        tc, storage, client = oauth_client
        code, verifier = self._get_auth_code(tc, storage, client)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://app.example.com/cb",
            "client_id": client.client_id,
            "code_verifier": verifier,
        }
        with patch(
            "hive.storage.HiveStorage.mark_auth_code_used",
            side_effect=AuthCodeAlreadyUsed("raced"),
        ):
            resp = tc.post("/oauth/token", data=data)
        assert resp.status_code == 400
        # Losing redeemer gets the same error body as a pre-observed
        # "already-used" code — no token pair, no stack trace leaked.
        assert "already-used" in resp.json()["detail"]


class TestOAuthAuthorizeEdgeCases:
    def test_wrong_challenge_method_returns_400(self, oauth_client):
        """Covers oauth.py:126 — only S256 is supported."""
        tc, storage, client = oauth_client
        _, challenge = _pkce_pair()
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client.client_id,
                "redirect_uri": "https://app.example.com/cb",
                "code_challenge": challenge,
                "code_challenge_method": "plain",
            },
        )
        assert resp.status_code == 400


class TestOAuthTokenEdgeCases:
    def _get_code(self, tc, storage, client) -> tuple[str, str]:
        """Create an auth code directly in storage, bypassing Google OAuth."""
        verifier, challenge = _pkce_pair()
        auth_code = storage.create_auth_code(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope=client.scope or "memories:read memories:write",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        return auth_code.code, verifier

    def test_basic_auth_header_used(self, oauth_client):
        """Covers oauth.py:169-173 — Basic auth parsed from header."""
        import base64

        tc, storage, client = oauth_client
        code, verifier = self._get_code(tc, storage, client)
        credentials = base64.b64encode(f"{client.client_id}:".encode()).decode()
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "code_verifier": verifier,
            },
            headers={"Authorization": f"Basic {credentials}"},
        )
        assert resp.status_code == 200

    def test_invalid_basic_auth_header_returns_401(self, oauth_client):
        """Covers oauth.py:174-175 — malformed Basic auth header."""
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "authorization_code"},
            headers={"Authorization": "Basic !!!not-valid-base64!!!"},
        )
        assert resp.status_code == 401

    def test_unknown_client_returns_401(self, oauth_client):
        """Covers oauth.py:182 — client_id not in storage."""
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "authorization_code", "client_id": "no-such-client"},
        )
        assert resp.status_code == 401

    def test_missing_code_returns_400(self, oauth_client):
        """Covers oauth.py:193 — code/verifier/redirect_uri required."""
        tc, storage, client = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "authorization_code", "client_id": client.client_id},
        )
        assert resp.status_code == 400

    def test_redirect_uri_mismatch_returns_400(self, oauth_client):
        """Covers oauth.py:203 — redirect_uri in token request != authorized."""
        tc, storage, client = oauth_client
        code, verifier = self._get_code(tc, storage, client)
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://evil.com/steal",
                "client_id": client.client_id,
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 400

    def test_expired_auth_code_returns_400(self, oauth_client):
        """Covers oauth.py:205 — expired authorization code."""
        from datetime import timedelta, timezone
        from unittest.mock import patch

        tc, storage, client = oauth_client
        code, verifier = self._get_code(tc, storage, client)

        # Patch datetime.now to return a time far in the future
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        with patch("hive.auth.oauth.datetime") as mock_dt:
            mock_dt.now.return_value = future
            resp = tc.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "https://app.example.com/cb",
                    "client_id": client.client_id,
                    "code_verifier": verifier,
                },
            )
        assert resp.status_code == 400

    def test_refresh_token_missing_returns_400(self, oauth_client):
        """Covers oauth.py:214 — refresh_token field required."""
        tc, storage, client = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={"grant_type": "refresh_token", "client_id": client.client_id},
        )
        assert resp.status_code == 400

    def test_invalid_refresh_token_jwt_returns_400(self, oauth_client):
        """Covers oauth.py:223-224 — JWTError on bad refresh_token."""
        tc, storage, client = oauth_client
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client.client_id,
                "refresh_token": "not-a-jwt",
            },
        )
        assert resp.status_code == 400

    def test_refresh_token_not_in_storage_returns_400(self, oauth_client):
        """Covers oauth.py:229 — refresh token valid JWT but not found/expired."""
        from hive.auth.tokens import issue_jwt
        from hive.models import Token

        tc, storage, client = oauth_client
        now = datetime.now(timezone.utc)
        # Issue a refresh token but don't store it
        token = Token(
            client_id=client.client_id,
            scope="memories:read",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
        )
        jwt_str = issue_jwt(token)
        # token is not in storage → should return 400
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client.client_id,
                "refresh_token": jwt_str,
            },
        )
        assert resp.status_code == 400

    def test_refresh_token_wrong_client_returns_400(self, oauth_client):
        """Covers oauth.py:231 — refresh token issued to different client."""
        tc, storage, client = oauth_client
        # Register a second client
        other = tc.post(
            "/oauth/register",
            json={"client_name": "Other App", "redirect_uris": ["https://other.com/cb"]},
        ).json()

        # Get a refresh token for the original client (bypass Google)
        code, verifier = self._get_code(tc, storage, client)
        token_resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": client.client_id,
                "code_verifier": verifier,
            },
        )
        refresh_token = token_resp.json()["refresh_token"]

        # Try to use that refresh token as the other client
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": other["client_id"],
                "refresh_token": refresh_token,
            },
        )
        assert resp.status_code == 400


class TestOAuthRevoke:
    def test_revoke_valid_token_returns_200(self, oauth_client):
        tc, storage, client = oauth_client
        # Issue a token directly
        now = datetime.now(timezone.utc)
        token = Token(
            client_id=client.client_id,
            scope="memories:read",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
        )
        storage.put_token(token)
        jwt_str = issue_jwt(token)
        resp = tc.post("/oauth/revoke", data={"token": jwt_str})
        assert resp.status_code == 200

    def test_revoke_invalid_token_still_returns_200(self, oauth_client):
        """RFC 7009: revocation endpoint always returns 200."""
        tc, *_ = oauth_client
        resp = tc.post("/oauth/revoke", data={"token": "not-a-jwt"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# get_storage() dependency — covers oauth.py:43
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DCR unsupported response_types — covers dcr.py:41
# ---------------------------------------------------------------------------


class TestDCRUnsupportedResponseType:
    def test_register_unsupported_response_type_raises(self, oauth_client):
        """Covers dcr.py:41 — unsupported response_types raises 400."""
        tc, *_ = oauth_client
        resp = tc.post(
            "/oauth/register",
            json={
                "client_name": "Bad Response Type",
                "response_types": ["token"],
            },
        )
        assert resp.status_code == 400
        assert "response_types" in resp.json()["detail"]


class TestGetStorage:
    def test_get_storage_returns_hive_storage(self):
        """Covers oauth.py:43 — get_storage() factory returns a HiveStorage."""
        from hive.auth.oauth import get_storage
        from hive.storage import HiveStorage

        result = get_storage()
        assert isinstance(result, HiveStorage)


# ---------------------------------------------------------------------------
# Confidential client wrong secret — covers oauth.py:188
# Auth code not issued to this client — covers oauth.py:201
# ---------------------------------------------------------------------------


class TestOAuthTokenConfidentialAndCodeClient:
    def test_confidential_client_wrong_secret_returns_401(self, oauth_client):
        """Covers oauth.py:188 — confidential client presents wrong secret."""
        from hive.models import OAuthClient

        tc, storage, _ = oauth_client

        # Create a confidential client (has a client_secret)
        conf_client = OAuthClient(
            client_name="Confidential App",
            client_secret="correct-secret",
            token_endpoint_auth_method="client_secret_post",
        )
        storage.put_client(conf_client)

        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": conf_client.client_id,
                "client_secret": "wrong-secret",
                "code": "dummy",
                "redirect_uri": "https://app.example.com/cb",
                "code_verifier": "dummy",
            },
        )
        assert resp.status_code == 401

    def test_auth_code_not_issued_to_client_returns_400(self, oauth_client):
        """Covers oauth.py:201 — code was issued to a different client."""
        tc, storage, client = oauth_client

        # Register a second client
        other = tc.post(
            "/oauth/register",
            json={"client_name": "Other App", "redirect_uris": ["https://other.com/cb"]},
        ).json()

        # Get an auth code for the original client (bypass Google)
        verifier, challenge = _pkce_pair()
        auth_code_obj = storage.create_auth_code(
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope=client.scope or "memories:read memories:write",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        code = auth_code_obj.code

        # Try to redeem the code as the other client
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": other["client_id"],
                "code": code,
                "redirect_uri": "https://other.com/cb",
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 400
        assert "not issued to this client" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# SSM fallback path in _jwt_secret() — covers tokens.py:36-44
# ---------------------------------------------------------------------------


class TestJwtSecretSSMPath:
    def test_ssm_path_returns_secret(self):
        """Covers tokens.py:36-44 — SSM fetch when HIVE_JWT_SECRET is unset."""
        from unittest.mock import MagicMock, patch

        from hive.auth import tokens

        tokens._jwt_secret.cache_clear()
        try:
            mock_ssm = MagicMock()
            mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "ssm-secret-value"}}

            env = {k: v for k, v in os.environ.items() if k != "HIVE_JWT_SECRET"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", return_value=mock_ssm),
            ):
                secret = tokens._jwt_secret()

            assert secret == "ssm-secret-value"
        finally:
            tokens._jwt_secret.cache_clear()
            # Restore the env var so other tests keep working
            os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")

    def test_ssm_failure_returns_random_secret(self):
        """Covers tokens.py:43-44 — random fallback when SSM raises."""
        from unittest.mock import patch

        from hive.auth import tokens

        tokens._jwt_secret.cache_clear()
        try:
            env = {k: v for k, v in os.environ.items() if k != "HIVE_JWT_SECRET"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", side_effect=Exception("no SSM")),
            ):
                secret = tokens._jwt_secret()

            assert len(secret) == 64  # hex(32 bytes)
        finally:
            tokens._jwt_secret.cache_clear()
            os.environ.setdefault("HIVE_JWT_SECRET", "unit-test-secret")


# ---------------------------------------------------------------------------
# validate_bearer_token missing jti — covers tokens.py:88
# ---------------------------------------------------------------------------


class TestValidateBearerMissingJti:
    def test_token_missing_jti_raises(self):
        """Covers tokens.py:88 — JWT has no jti claim → ValueError."""
        from unittest.mock import MagicMock

        # Build a JWT without a jti claim, signed with the actual runtime secret
        from jose import jwt as jose_jwt

        from hive.auth.tokens import _jwt_secret, validate_bearer_token

        payload = {
            "iss": "https://hive.example.com",
            "sub": "some-client",
            "scope": "memories:read",
            "iat": 0,
            "exp": 9999999999,
        }
        token_str = jose_jwt.encode(payload, _jwt_secret(), algorithm="HS256")

        storage = MagicMock()
        with pytest.raises(ValueError, match="missing jti"):
            validate_bearer_token(f"Bearer {token_str}", storage)


# ---------------------------------------------------------------------------
# DCR scope validation — covers dcr.py ALLOWED_SCOPES check
# ---------------------------------------------------------------------------


class TestDCRScopeValidation:
    def test_unknown_scope_raises(self):
        storage = MagicMock()
        req = ClientRegistrationRequest(
            client_name="Bad Scope App",
            scope="memories:read unknown:scope",
        )
        with pytest.raises(ValueError, match="Unknown scope"):
            register_client(req, storage)

    def test_known_scopes_accepted(self):
        storage = MagicMock()
        req = ClientRegistrationRequest(
            client_name="Read Only Agent",
            redirect_uris=["http://localhost/cb"],
            scope="memories:read",
        )
        resp = register_client(req, storage)
        assert resp.scope == "memories:read"

    def test_all_scopes_accepted(self):
        storage = MagicMock()
        req = ClientRegistrationRequest(
            client_name="Admin App",
            redirect_uris=["http://localhost/cb"],
            scope="memories:read memories:write clients:read clients:write",
        )
        resp = register_client(req, storage)
        assert "clients:write" in resp.scope


# ---------------------------------------------------------------------------
# Authorize scope restriction — covers oauth.py scope intersection
# ---------------------------------------------------------------------------


class TestAuthorizeScopeRestriction:
    def test_requested_scope_restricted_to_client_scope(self, oauth_client):
        """Authorize restricts requested scope to client's registered scope."""
        from hive.models import OAuthClient

        tc, storage, _ = oauth_client

        # Register a read-only client
        readonly_client = OAuthClient(
            client_name="Read Only",
            redirect_uris=["https://app.example.com/cb"],
            scope="memories:read",
        )
        storage.put_client(readonly_client)

        _, challenge = _pkce_pair()
        with patch("hive.auth.google.google_authorization_url") as mock_google_url:
            mock_google_url.return_value = "https://accounts.google.com/mock"
            resp = tc.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": readonly_client.client_id,
                    "redirect_uri": "https://app.example.com/cb",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    # Request write scope — should be restricted to read-only
                    "scope": "memories:read memories:write",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        # Scope restriction is stored in the PendingAuth record
        state = mock_google_url.call_args[0][0]
        pending = storage.get_pending_auth(state)
        assert pending is not None
        assert "memories:write" not in pending.scope
        assert "memories:read" in pending.scope

    def test_scope_no_overlap_returns_400(self, oauth_client):
        """Authorize returns 400 when requested scope has no overlap with client scope."""
        from hive.models import OAuthClient

        tc, storage, _ = oauth_client

        readonly_client = OAuthClient(
            client_name="Read Only 2",
            redirect_uris=["https://app.example.com/cb"],
            scope="memories:read",
        )
        storage.put_client(readonly_client)

        _, challenge = _pkce_pair()
        resp = tc.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": readonly_client.client_id,
                "redirect_uri": "https://app.example.com/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "clients:read clients:write",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Token scope — scope in issued access token matches auth code scope
# ---------------------------------------------------------------------------


class TestRefreshTokenScopeNarrowing:
    def test_refresh_intersects_scope_with_current_client_scope(self, oauth_client):
        """Covers oauth.py scope re-intersection — refresh token scope narrows to client scope."""
        from hive.auth.tokens import decode_jwt
        from hive.models import OAuthClient

        tc, storage, _ = oauth_client

        # Register a client with write+read scope
        wide_client = OAuthClient(
            client_name="Wide Scope Client",
            redirect_uris=["https://app.example.com/cb"],
            scope="memories:read memories:write",
        )
        storage.put_client(wide_client)

        verifier, challenge = _pkce_pair()
        auth_code = storage.create_auth_code(
            client_id=wide_client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="memories:read memories:write",
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        code = auth_code.code
        token_resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": wide_client.client_id,
                "code_verifier": verifier,
            },
        )
        refresh_token = token_resp.json()["refresh_token"]

        # Narrow the client's scope in storage
        wide_client.scope = "memories:read"
        storage.put_client(wide_client)

        # Refresh should issue new tokens with narrowed scope
        resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": wide_client.client_id,
                "refresh_token": refresh_token,
            },
        )
        assert resp.status_code == 200
        claims = decode_jwt(resp.json()["access_token"])
        assert "memories:write" not in claims["scope"]
        assert "memories:read" in claims["scope"]


class TestTokenScopeIntersection:
    def test_access_token_carries_restricted_scope(self, oauth_client):
        """Access token scope matches the effective scope from the auth code."""
        from hive.auth.tokens import decode_jwt
        from hive.models import OAuthClient

        tc, storage, _ = oauth_client

        readonly_client = OAuthClient(
            client_name="Scope Test Client",
            redirect_uris=["https://app.example.com/cb"],
            scope="memories:read",
        )
        storage.put_client(readonly_client)

        verifier, challenge = _pkce_pair()
        auth_code = storage.create_auth_code(
            client_id=readonly_client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="memories:read",  # scope already restricted to client's registered scope
            code_challenge=challenge,
            code_challenge_method="S256",
        )
        code = auth_code.code

        token_resp = tc.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/cb",
                "client_id": readonly_client.client_id,
                "code_verifier": verifier,
            },
        )
        assert token_resp.status_code == 200
        data = token_resp.json()
        claims = decode_jwt(data["access_token"])
        assert claims["scope"] == "memories:read"
        assert "memories:write" not in claims["scope"]


# ---------------------------------------------------------------------------
# _origin_verify_secret
# ---------------------------------------------------------------------------


class TestOriginVerifySecret:
    def setup_method(self):
        # Clear the lru_cache before each test so env changes take effect
        from hive.auth.tokens import _origin_verify_secret

        _origin_verify_secret.cache_clear()

    def teardown_method(self):
        from hive.auth.tokens import _origin_verify_secret

        _origin_verify_secret.cache_clear()

    def test_returns_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("HIVE_ORIGIN_VERIFY_SECRET", "env-secret")
        monkeypatch.delenv("HIVE_ORIGIN_VERIFY_PARAM", raising=False)
        from hive.auth.tokens import _origin_verify_secret

        assert _origin_verify_secret() == "env-secret"

    def test_returns_none_when_no_param_name(self, monkeypatch):
        monkeypatch.delenv("HIVE_ORIGIN_VERIFY_SECRET", raising=False)
        monkeypatch.delenv("HIVE_ORIGIN_VERIFY_PARAM", raising=False)
        from hive.auth.tokens import _origin_verify_secret

        assert _origin_verify_secret() is None

    def test_fetches_from_ssm_when_param_name_set(self, monkeypatch):
        monkeypatch.delenv("HIVE_ORIGIN_VERIFY_SECRET", raising=False)
        monkeypatch.setenv("HIVE_ORIGIN_VERIFY_PARAM", "/hive/origin-verify-secret")
        from unittest.mock import MagicMock, patch

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "ssm-secret"}}
        with patch("boto3.client", return_value=mock_ssm):
            from hive.auth.tokens import _origin_verify_secret

            result = _origin_verify_secret()
        assert result == "ssm-secret"

    def test_returns_none_on_ssm_exception(self, monkeypatch):
        monkeypatch.delenv("HIVE_ORIGIN_VERIFY_SECRET", raising=False)
        monkeypatch.setenv("HIVE_ORIGIN_VERIFY_PARAM", "/hive/origin-verify-secret")
        from unittest.mock import MagicMock, patch

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = Exception("SSM unavailable")
        with patch("boto3.client", return_value=mock_ssm):
            from hive.auth.tokens import _origin_verify_secret

            result = _origin_verify_secret()
        assert result is None


# ---------------------------------------------------------------------------
# Management JWT (issue_mgmt_jwt / decode_mgmt_jwt)
# ---------------------------------------------------------------------------


class TestMgmtJwt:
    def _make_user(self):
        from hive.models import User

        return User(email="alice@example.com", display_name="Alice", role="admin")

    def test_issue_and_decode(self):
        from hive.auth.tokens import decode_mgmt_jwt, issue_mgmt_jwt

        user = self._make_user()
        token = issue_mgmt_jwt(user)
        claims = decode_mgmt_jwt(token)
        assert claims["sub"] == user.user_id
        assert claims["email"] == user.email
        assert claims["role"] == "admin"
        assert claims["typ"] == "mgmt"

    def test_mcp_token_rejected_as_mgmt(self):
        """An MCP access token must not be accepted by decode_mgmt_jwt."""
        from datetime import datetime, timedelta, timezone

        from jose import JWTError

        from hive.auth.tokens import decode_mgmt_jwt, issue_jwt
        from hive.models import Token

        now = datetime.now(timezone.utc)
        mcp_token = Token(
            client_id="c1",
            scope="memories:read",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
        )
        jwt_str = issue_jwt(mcp_token)
        with pytest.raises(JWTError, match="management token"):
            decode_mgmt_jwt(jwt_str)

    def test_is_admin_email(self, monkeypatch):
        from hive.auth.google import _allowed_emails, is_admin_email

        _allowed_emails.cache_clear()
        monkeypatch.setenv("ALLOWED_EMAILS", '["admin@example.com"]')
        _allowed_emails.cache_clear()
        assert is_admin_email("admin@example.com") is True
        assert is_admin_email("other@example.com") is False
        _allowed_emails.cache_clear()

    def test_is_admin_email_empty_list(self, monkeypatch):
        from hive.auth.google import _allowed_emails, is_admin_email

        _allowed_emails.cache_clear()
        monkeypatch.setenv("ALLOWED_EMAILS", "[]")
        _allowed_emails.cache_clear()
        assert is_admin_email("anyone@example.com") is False
        _allowed_emails.cache_clear()


# ---------------------------------------------------------------------------
# Management auth routes (/auth/login, /auth/callback)
# ---------------------------------------------------------------------------


class TestMgmtAuthRoutes:
    @pytest.fixture()
    def mgmt_client(self):
        with mock_aws():
            _create_table()
            old = os.environ.get("HIVE_TABLE_NAME")
            os.environ["HIVE_TABLE_NAME"] = "hive-unit-auth"
            try:
                from fastapi.testclient import TestClient

                from hive.api.main import app

                yield TestClient(app, follow_redirects=False)
            finally:
                if old is not None:
                    os.environ["HIVE_TABLE_NAME"] = old
                else:
                    os.environ.pop("HIVE_TABLE_NAME", None)

    def test_login_bypass_issues_jwt(self, mgmt_client):
        """In bypass mode, /auth/login returns HTML with a management JWT."""
        from unittest.mock import patch

        with patch("hive.auth.mgmt_auth._BYPASS", True):
            resp = mgmt_client.get("/auth/login?test_email=dev@example.com")
        assert resp.status_code == 200
        assert "hive_mgmt_token" in resp.text

    def test_login_bypass_without_test_email_redirects_to_google(self, mgmt_client):
        """In bypass mode, /auth/login without test_email falls through to Google."""
        from unittest.mock import patch

        with (
            patch("hive.auth.mgmt_auth._BYPASS", True),
            patch(
                "hive.auth.mgmt_auth.google_authorization_url",
                return_value="https://accounts.google.com/auth?state=x",
            ),
        ):
            resp = mgmt_client.get("/auth/login")
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]

    def test_login_redirects_to_google(self, mgmt_client):
        """Without bypass, /auth/login redirects to Google."""
        from unittest.mock import patch

        with (
            patch("hive.auth.mgmt_auth._BYPASS", False),
            patch(
                "hive.auth.mgmt_auth.google_authorization_url",
                return_value="https://accounts.google.com/auth?state=x",
            ),
        ):
            resp = mgmt_client.get("/auth/login")
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]

    def test_callback_error_param_returns_400(self, mgmt_client):
        resp = mgmt_client.get("/auth/callback?error=access_denied")
        assert resp.status_code == 400

    def test_callback_missing_code_returns_400(self, mgmt_client):
        resp = mgmt_client.get("/auth/callback?state=x")
        assert resp.status_code == 400

    def test_callback_invalid_state_returns_400(self, mgmt_client):
        resp = mgmt_client.get("/auth/callback?code=c&state=no-such-state")
        assert resp.status_code == 400

    def test_callback_creates_user_and_issues_jwt(self, mgmt_client, monkeypatch):
        """Full happy-path: valid state + Google exchange → HTML with JWT."""
        monkeypatch.delenv("HIVE_BYPASS_GOOGLE_AUTH", raising=False)
        from unittest.mock import AsyncMock, patch

        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        pending = storage.create_mgmt_pending_state()

        fake_claims = {
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice",
            "sub": "google-uid-1",
        }
        with (
            patch(
                "hive.auth.mgmt_auth.exchange_google_code",
                new_callable=AsyncMock,
                return_value="fake-id-token",
            ),
            patch(
                "hive.auth.mgmt_auth.verify_google_id_token",
                new_callable=AsyncMock,
                return_value=fake_claims,
            ),
        ):
            resp = mgmt_client.get(f"/auth/callback?code=abc&state={pending.state}")

        assert resp.status_code == 200
        assert "hive_mgmt_token" in resp.text
        # User should have been created
        user = storage.get_user_by_email("alice@example.com")
        assert user is not None
        assert user.email == "alice@example.com"

    def test_callback_unverified_email_returns_400(self, mgmt_client):
        from unittest.mock import AsyncMock, patch

        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        pending = storage.create_mgmt_pending_state()

        fake_claims = {"email": "bad@example.com", "email_verified": False, "name": "Bad"}
        with (
            patch(
                "hive.auth.mgmt_auth.exchange_google_code", new_callable=AsyncMock, return_value="t"
            ),
            patch(
                "hive.auth.mgmt_auth.verify_google_id_token",
                new_callable=AsyncMock,
                return_value=fake_claims,
            ),
        ):
            resp = mgmt_client.get(f"/auth/callback?code=c&state={pending.state}")
        assert resp.status_code == 400

    def test_callback_expired_state_returns_400(self, mgmt_client):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        pending = storage.create_mgmt_pending_state()

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch("hive.auth.mgmt_auth.datetime") as mock_dt:
            mock_dt.now.return_value = future
            resp = mgmt_client.get(f"/auth/callback?code=c&state={pending.state}")
        assert resp.status_code == 400

    def test_callback_google_exchange_failure_returns_400(self, mgmt_client):
        from unittest.mock import AsyncMock, patch

        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        pending = storage.create_mgmt_pending_state()

        with patch(
            "hive.auth.mgmt_auth.exchange_google_code",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            resp = mgmt_client.get(f"/auth/callback?code=c&state={pending.state}")
        assert resp.status_code == 400

    def test_callback_updates_existing_user(self, mgmt_client):
        """Second login updates display_name and last_login_at."""
        from unittest.mock import AsyncMock, patch

        from hive.models import User
        from hive.storage import HiveStorage

        storage = HiveStorage(table_name="hive-unit-auth", region="us-east-1")
        # Pre-create user
        existing = User(email="bob@example.com", display_name="Bob Old", role="user")
        storage.put_user(existing)

        pending = storage.create_mgmt_pending_state()
        fake_claims = {
            "email": "bob@example.com",
            "email_verified": True,
            "name": "Bob New",
            "sub": "google-uid-bob",
        }
        with (
            patch(
                "hive.auth.mgmt_auth.exchange_google_code", new_callable=AsyncMock, return_value="t"
            ),
            patch(
                "hive.auth.mgmt_auth.verify_google_id_token",
                new_callable=AsyncMock,
                return_value=fake_claims,
            ),
        ):
            resp = mgmt_client.get(f"/auth/callback?code=c&state={pending.state}")

        assert resp.status_code == 200
        user = storage.get_user_by_email("bob@example.com")
        assert user is not None
        assert user.display_name == "Bob New"


# ---------------------------------------------------------------------------
# validate_bearer_token — API key path
# ---------------------------------------------------------------------------


class TestValidateBearerTokenApiKey:
    def _storage_with_key(self, key):
        from unittest.mock import MagicMock

        storage = MagicMock()
        storage.get_api_key_by_hash.return_value = key
        return storage

    def test_valid_api_key_returns_synthetic_token(self):
        from datetime import datetime, timezone

        from hive.auth.tokens import validate_bearer_token
        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="CI",
            key_hash="will-be-replaced",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        # Generate real key/hash pair

        from hive.api.keys import generate_api_key

        plaintext, real_hash = generate_api_key()
        k.key_hash = real_hash
        storage = self._storage_with_key(k)

        token = validate_bearer_token(f"Bearer {plaintext}", storage)
        assert token.client_id == f"apikey:{k.key_id}"
        assert token.scope == k.scope

    def test_api_key_not_found_raises(self):
        from unittest.mock import MagicMock

        from hive.auth.tokens import validate_bearer_token

        storage = MagicMock()
        storage.get_api_key_by_hash.return_value = None
        with pytest.raises(ValueError, match="not found"):
            validate_bearer_token("Bearer hive_sk_notfound", storage)

    def test_revoked_api_key_raises(self):
        from datetime import datetime, timezone

        from hive.auth.tokens import validate_bearer_token
        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Revoked",
            key_hash="hash",
            revoked=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        storage = self._storage_with_key(k)
        with pytest.raises(ValueError, match="revoked or has expired"):
            validate_bearer_token("Bearer hive_sk_revoked", storage)

    def test_expired_api_key_raises(self):
        from datetime import datetime, timezone

        from hive.auth.tokens import validate_bearer_token
        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="Expired",
            key_hash="hash",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2025, 6, 1, tzinfo=timezone.utc),  # past
        )
        storage = self._storage_with_key(k)
        with pytest.raises(ValueError, match="revoked or has expired"):
            validate_bearer_token("Bearer hive_sk_expired", storage)

    def test_api_key_with_no_expiry_gets_far_future_expires(self):
        from datetime import datetime, timezone

        from hive.auth.tokens import validate_bearer_token
        from hive.models import ApiKey

        k = ApiKey(
            owner_user_id="u1",
            name="NoExpiry",
            key_hash="hash",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            expires_at=None,
        )
        storage = self._storage_with_key(k)
        token = validate_bearer_token("Bearer hive_sk_noexpiry", storage)
        assert token.expires_at > datetime(2030, 1, 1, tzinfo=timezone.utc)
