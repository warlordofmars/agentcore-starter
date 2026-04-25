# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for Google OAuth helper functions."""

import os

os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("ALLOWED_EMAILS", '["admin@test.com"]')

from starter.auth.google import (  # noqa: E402
    _allowed_emails,
    _google_client_id,
    _google_client_secret,
    google_authorization_url,
    is_admin_email,
    is_email_allowed,
)


def _clear_caches():
    _google_client_id.cache_clear()
    _google_client_secret.cache_clear()
    _allowed_emails.cache_clear()


def setup_function():
    _clear_caches()


def teardown_function():
    _clear_caches()


def test_google_client_id_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "my-client-id")
    assert _google_client_id() == "my-client-id"


def test_google_client_secret_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "my-secret")
    assert _google_client_secret() == "my-secret"


def test_allowed_emails_from_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", '["alice@example.com","bob@example.com"]')
    result = _allowed_emails()
    assert "alice@example.com" in result
    assert "bob@example.com" in result


def test_google_authorization_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-oauth-id")
    url = google_authorization_url("test-state-123", "https://example.com/auth/callback")
    assert "accounts.google.com" in url
    assert "test-state-123" in url
    assert "test-oauth-id" in url
    assert "response_type=code" in url


def test_is_email_allowed_when_in_list(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", '["allowed@test.com"]')
    assert is_email_allowed("allowed@test.com") is True


def test_is_email_allowed_when_not_in_list(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", '["allowed@test.com"]')
    assert is_email_allowed("other@test.com") is False


def test_is_email_allowed_empty_list_allows_all(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "[]")
    assert is_email_allowed("anyone@example.com") is True


def test_is_admin_email_when_listed(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", '["admin@test.com"]')
    assert is_admin_email("admin@test.com") is True


def test_is_admin_email_when_not_listed(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", '["admin@test.com"]')
    assert is_admin_email("user@test.com") is False
