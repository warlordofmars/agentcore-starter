# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the Google OAuth integration (auth/google.py)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("ALLOWED_EMAILS", '["allowed@example.com"]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_google_caches():
    from hive.auth import google as g

    g._google_client_id.cache_clear()
    g._google_client_secret.cache_clear()
    g._allowed_emails.cache_clear()


# ---------------------------------------------------------------------------
# google_authorization_url
# ---------------------------------------------------------------------------


class TestGoogleAuthorizationUrl:
    def test_url_contains_required_params(self):
        from hive.auth.google import google_authorization_url

        url = google_authorization_url("my-state", "https://hive.example.com/oauth/google/callback")
        assert "accounts.google.com" in url
        assert "my-state" in url
        assert "openid" in url
        assert "email" in url
        assert "test-google-client-id" in url

    def test_url_contains_callback_uri(self):
        from hive.auth.google import google_authorization_url

        url = google_authorization_url("s", "https://cb.example.com/callback")
        assert "cb.example.com" in url


# ---------------------------------------------------------------------------
# _google_client_id / _google_client_secret — SSM fallback path
# ---------------------------------------------------------------------------


class TestCredentialSSMFallback:
    def test_client_id_from_env(self):
        from hive.auth import google as g

        _clear_google_caches()
        try:
            with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "env-client-id"}):
                g._google_client_id.cache_clear()
                assert g._google_client_id() == "env-client-id"
        finally:
            _clear_google_caches()

    def test_client_id_from_ssm(self):
        from hive.auth import google as g

        _clear_google_caches()
        try:
            mock_ssm = MagicMock()
            mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "ssm-client-id"}}
            env = {k: v for k, v in os.environ.items() if k != "GOOGLE_CLIENT_ID"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", return_value=mock_ssm),
            ):
                g._google_client_id.cache_clear()
                assert g._google_client_id() == "ssm-client-id"
        finally:
            _clear_google_caches()

    def test_client_secret_from_ssm(self):
        from hive.auth import google as g

        _clear_google_caches()
        try:
            mock_ssm = MagicMock()
            mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "ssm-secret"}}
            env = {k: v for k, v in os.environ.items() if k != "GOOGLE_CLIENT_SECRET"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", return_value=mock_ssm),
            ):
                g._google_client_secret.cache_clear()
                assert g._google_client_secret() == "ssm-secret"
        finally:
            _clear_google_caches()


# ---------------------------------------------------------------------------
# _allowed_emails
# ---------------------------------------------------------------------------


class TestAllowedEmails:
    def test_from_env_json(self):
        from hive.auth import google as g

        _clear_google_caches()
        try:
            with patch.dict(os.environ, {"ALLOWED_EMAILS": '["a@b.com", "c@d.com"]'}):
                g._allowed_emails.cache_clear()
                allowed = g._allowed_emails()
            assert "a@b.com" in allowed
            assert "c@d.com" in allowed
        finally:
            _clear_google_caches()

    def test_from_ssm(self):
        from hive.auth import google as g

        _clear_google_caches()
        try:
            mock_ssm = MagicMock()
            mock_ssm.get_parameter.return_value = {"Parameter": {"Value": '["ssm@example.com"]'}}
            env = {k: v for k, v in os.environ.items() if k != "ALLOWED_EMAILS"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", return_value=mock_ssm),
            ):
                g._allowed_emails.cache_clear()
                allowed = g._allowed_emails()
            assert "ssm@example.com" in allowed
        finally:
            _clear_google_caches()

    def test_ssm_failure_returns_empty_frozenset(self):
        """When SSM fails and no env var, returns empty frozenset (allow all)."""
        from hive.auth import google as g

        _clear_google_caches()
        try:
            env = {k: v for k, v in os.environ.items() if k != "ALLOWED_EMAILS"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("boto3.client", side_effect=Exception("no SSM")),
            ):
                g._allowed_emails.cache_clear()
                allowed = g._allowed_emails()
            assert allowed == frozenset()
        finally:
            _clear_google_caches()


# ---------------------------------------------------------------------------
# is_email_allowed
# ---------------------------------------------------------------------------


class TestIsEmailAllowed:
    def test_allowed_email_returns_true(self):
        from hive.auth.google import is_email_allowed

        _clear_google_caches()
        try:
            with patch.dict(os.environ, {"ALLOWED_EMAILS": '["allowed@example.com"]'}):
                from hive.auth import google as g

                g._allowed_emails.cache_clear()
                assert is_email_allowed("allowed@example.com") is True
        finally:
            _clear_google_caches()

    def test_unlisted_email_returns_false(self):
        from hive.auth.google import is_email_allowed

        _clear_google_caches()
        try:
            with patch.dict(os.environ, {"ALLOWED_EMAILS": '["allowed@example.com"]'}):
                from hive.auth import google as g

                g._allowed_emails.cache_clear()
                assert is_email_allowed("stranger@example.com") is False
        finally:
            _clear_google_caches()

    def test_empty_allowlist_permits_everyone(self):
        """Empty allowlist = open access."""
        from hive.auth.google import is_email_allowed

        _clear_google_caches()
        try:
            with patch.dict(os.environ, {"ALLOWED_EMAILS": "[]"}):
                from hive.auth import google as g

                g._allowed_emails.cache_clear()
                assert is_email_allowed("anyone@anywhere.com") is True
        finally:
            _clear_google_caches()


# ---------------------------------------------------------------------------
# exchange_google_code
# ---------------------------------------------------------------------------


class TestExchangeGoogleCode:
    async def test_returns_id_token_on_success(self):
        from hive.auth.google import exchange_google_code

        mock_response = MagicMock()
        mock_response.json.return_value = {"id_token": "fake-id-token", "access_token": "at"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await exchange_google_code("auth-code", "https://cb.example.com/cb")

        assert result == "fake-id-token"

    async def test_raises_on_http_error(self):
        import httpx

        from hive.auth.google import exchange_google_code

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await exchange_google_code("bad-code", "https://cb.example.com/cb")


# ---------------------------------------------------------------------------
# fetch_google_jwks
# ---------------------------------------------------------------------------


class TestFetchGoogleJwks:
    async def test_returns_jwks_dict(self):
        from hive.auth.google import fetch_google_jwks

        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "abc", "kty": "RSA"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_google_jwks()

        assert "keys" in result


# ---------------------------------------------------------------------------
# verify_google_id_token
# ---------------------------------------------------------------------------


class TestVerifyGoogleIdToken:
    async def test_returns_claims_on_valid_token(self):
        from hive.auth.google import verify_google_id_token

        fake_claims = {"email": "user@example.com", "email_verified": True, "sub": "12345"}
        fake_jwks = {"keys": []}

        with (
            patch("hive.auth.google.fetch_google_jwks", AsyncMock(return_value=fake_jwks)),
            patch("hive.auth.google.jose_jwt.decode", return_value=fake_claims),
        ):
            result = await verify_google_id_token("fake-token")

        assert result["email"] == "user@example.com"

    async def test_raises_on_invalid_token(self):
        from jose import JWTError

        from hive.auth.google import verify_google_id_token

        fake_jwks = {"keys": []}
        with (
            patch("hive.auth.google.fetch_google_jwks", AsyncMock(return_value=fake_jwks)),
            patch("hive.auth.google.jose_jwt.decode", side_effect=JWTError("bad token")),
            pytest.raises(JWTError),
        ):
            await verify_google_id_token("bad-token")
