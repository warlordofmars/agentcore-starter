# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for :mod:`starter.auth.state_store`.

These tests cover the four required cases from issue #23:

- happy path (put + consume returns the payload)
- missing key (consume returns None on ConditionalCheckFailed)
- expired item (consume returns None on app-level expiry check)
- atomic-consume race (one consumer wins, the other gets None)

DynamoDB calls are mocked at the ``_get_table()`` helper boundary so
these tests run without any external service. Integration tests in
``tests/integration/test_auth_state_store.py`` cover the same surface
against DynamoDB Local.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from starter.auth import state_store


@pytest.fixture
def fake_table():
    """Patch ``state_store._get_table`` to return a MagicMock surface.

    The yielded mock is the Table object — call ``.put_item.assert_*`` /
    ``.delete_item.return_value = ...`` on it from the test body.
    """
    table = MagicMock(name="StarterTable")
    with patch.object(state_store, "_get_table", return_value=table):
        yield table


def _attach_log_handler() -> tuple[logging.Logger, list[logging.LogRecord]]:
    """Attach a list-backed handler to the state_store logger.

    The project's structured logger sets ``propagate=False`` on the
    ``starter`` tree so :data:`pytest`'s ``caplog`` fixture cannot see
    the records via the root logger — mirror the pattern from
    ``tests/integration/test_startup.py``.
    """
    captured: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _ListHandler(level=logging.DEBUG)
    log = logging.getLogger("starter.auth.state_store")
    log.addHandler(handler)
    return log, captured


# ── put_state ────────────────────────────────────────────────────────────────


def test_put_state_writes_expected_pk_sk_and_ttl(fake_table):
    """Item must use the MGMT_STATE#{state} / META key shape with TTL."""
    state_store.put_state("abc123", ttl_seconds=600)

    fake_table.put_item.assert_called_once()
    item = fake_table.put_item.call_args.kwargs["Item"]
    assert item["PK"] == "MGMT_STATE#abc123"
    assert item["SK"] == "META"
    # ttl is an absolute Unix timestamp — must be an int (DynamoDB's TTL
    # service silently ignores non-integer values).
    assert isinstance(item["ttl"], int)
    # ttl_seconds is the operator-supplied window; ttl is created_at + ttl_seconds.
    assert item["ttl"] == item["created_at"] + 600
    assert item["ttl_seconds"] == 600


def test_put_state_default_ttl_is_600_seconds(fake_table):
    state_store.put_state("xyz")
    item = fake_table.put_item.call_args.kwargs["Item"]
    assert item["ttl_seconds"] == 600


def test_put_state_includes_caller_payload(fake_table):
    state_store.put_state("xyz", payload={"nonce": "n1", "redirect_uri": "/cb"})
    item = fake_table.put_item.call_args.kwargs["Item"]
    assert item["nonce"] == "n1"
    assert item["redirect_uri"] == "/cb"


def test_put_state_payload_cannot_overwrite_reserved_keys(fake_table):
    """Reserved keys (PK / SK / created_at / ttl / ttl_seconds) must win."""
    state_store.put_state(
        "abc",
        payload={
            "PK": "EVIL#hijack",
            "SK": "EVIL",
            "ttl": 1,
            "ttl_seconds": 9999,
            "created_at": 0,
            "nonce": "n1",
        },
        ttl_seconds=300,
    )
    item = fake_table.put_item.call_args.kwargs["Item"]
    assert item["PK"] == "MGMT_STATE#abc"
    assert item["SK"] == "META"
    assert item["ttl_seconds"] == 300
    assert item["nonce"] == "n1"  # non-reserved attributes still come through


# ── consume_state — happy path ───────────────────────────────────────────────


def test_consume_state_returns_payload_when_present_and_unexpired(fake_table):
    now = int(time.time())
    fake_table.delete_item.return_value = {
        "Attributes": {
            "PK": "MGMT_STATE#abc",
            "SK": "META",
            "created_at": now,
            "ttl_seconds": 600,
            "ttl": now + 600,
            "nonce": "n1",
        }
    }

    result = state_store.consume_state("abc")

    assert result is not None
    assert result["nonce"] == "n1"
    # Verify the delete was conditional on presence + asked for the old image.
    call = fake_table.delete_item.call_args.kwargs
    assert call["Key"] == {"PK": "MGMT_STATE#abc", "SK": "META"}
    assert call["ConditionExpression"] == "attribute_exists(PK)"
    assert call["ReturnValues"] == "ALL_OLD"


# ── consume_state — missing key ──────────────────────────────────────────────


def test_consume_state_returns_none_on_conditional_check_failed(fake_table):
    """Replay or already-consumed → ConditionalCheckFailedException → None."""
    fake_table.delete_item.side_effect = ClientError(
        error_response={
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        },
        operation_name="DeleteItem",
    )

    log, captured = _attach_log_handler()
    try:
        result = state_store.consume_state("never-existed")
    finally:
        log.removeHandler(log.handlers[-1])

    assert result is None
    info_lines = [r for r in captured if r.levelno == logging.INFO]
    assert any("not present" in r.getMessage() for r in info_lines), (
        f"expected an INFO log mentioning 'not present', got: "
        f"{[r.getMessage() for r in info_lines]}"
    )


def test_consume_state_propagates_unexpected_client_error(fake_table):
    """Non-ConditionalCheckFailed errors must surface, not return None."""
    fake_table.delete_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ProvisionedThroughputExceededException"}},
        operation_name="DeleteItem",
    )

    with pytest.raises(ClientError):
        state_store.consume_state("abc")


def test_consume_state_returns_none_when_attributes_missing(fake_table):
    """Defensive: ALL_OLD with no Attributes key → treat as not present."""
    fake_table.delete_item.return_value = {}  # no Attributes key

    log, captured = _attach_log_handler()
    try:
        result = state_store.consume_state("abc")
    finally:
        log.removeHandler(log.handlers[-1])

    assert result is None
    info_lines = [r for r in captured if r.levelno == logging.INFO]
    assert any("no attributes" in r.getMessage() for r in info_lines)


# ── consume_state — expired item ─────────────────────────────────────────────


def test_consume_state_returns_none_when_expired(fake_table):
    """Delete succeeds but app-level expiry fails → None + 'expired' log."""
    long_ago = int(time.time()) - 3600  # one hour ago
    fake_table.delete_item.return_value = {
        "Attributes": {
            "PK": "MGMT_STATE#stale",
            "SK": "META",
            "created_at": long_ago,
            "ttl_seconds": 600,  # 10-minute window expired ~50 minutes ago
            "ttl": long_ago + 600,
        }
    }

    log, captured = _attach_log_handler()
    try:
        result = state_store.consume_state("stale")
    finally:
        log.removeHandler(log.handlers[-1])

    assert result is None
    info_lines = [r for r in captured if r.levelno == logging.INFO]
    assert any("expired" in r.getMessage() for r in info_lines), (
        f"expected an INFO log mentioning 'expired', got: {[r.getMessage() for r in info_lines]}"
    )


def test_consume_state_returns_none_when_ttl_seconds_missing_and_default_expires(fake_table):
    """If ttl_seconds is absent the default (600s) is applied — and an old
    created_at means the row is treated as expired."""
    long_ago = int(time.time()) - 3600
    fake_table.delete_item.return_value = {
        "Attributes": {
            "PK": "MGMT_STATE#x",
            "SK": "META",
            "created_at": long_ago,
            # no ttl_seconds attribute
        }
    }
    assert state_store.consume_state("x") is None


# ── atomic-consume race ──────────────────────────────────────────────────────


def test_consume_state_atomic_race_one_winner_one_loser(fake_table):
    """Two concurrent consumes: first wins (returns payload), second gets None.

    Modelled by configuring the mock to return the payload on the first
    call and raise ConditionalCheckFailedException on the second.
    """
    now = int(time.time())
    fake_table.delete_item.side_effect = [
        {
            "Attributes": {
                "PK": "MGMT_STATE#race",
                "SK": "META",
                "created_at": now,
                "ttl_seconds": 600,
                "ttl": now + 600,
                "nonce": "n1",
            }
        },
        ClientError(
            error_response={"Error": {"Code": "ConditionalCheckFailedException"}},
            operation_name="DeleteItem",
        ),
    ]

    first = state_store.consume_state("race")
    second = state_store.consume_state("race")

    assert first is not None
    assert first["nonce"] == "n1"
    assert second is None


# ── _get_table ───────────────────────────────────────────────────────────────


def test_get_table_uses_env_vars(monkeypatch):
    """STARTER_TABLE_NAME / DYNAMODB_ENDPOINT must be read at call time."""
    monkeypatch.setenv("STARTER_TABLE_NAME", "test-table-from-env")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:9999")
    monkeypatch.setenv("AWS_REGION", "us-west-2")

    captured: dict[str, Any] = {}

    class _FakeResource:
        def Table(self, name: str) -> str:
            captured["table_name"] = name
            return f"table:{name}"

    def _fake_resource(service: str, **kwargs: Any) -> _FakeResource:
        captured["service"] = service
        captured["kwargs"] = kwargs
        return _FakeResource()

    with patch.object(state_store.boto3, "resource", side_effect=_fake_resource):
        result = state_store._get_table()

    assert result == "table:test-table-from-env"
    assert captured["service"] == "dynamodb"
    assert captured["kwargs"]["region_name"] == "us-west-2"
    assert captured["kwargs"]["endpoint_url"] == "http://localhost:9999"
    assert captured["table_name"] == "test-table-from-env"


def test_get_table_uses_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("STARTER_TABLE_NAME", raising=False)
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)

    captured: dict[str, Any] = {}

    class _FakeResource:
        def Table(self, name: str) -> str:
            captured["table_name"] = name
            return name

    def _fake_resource(service: str, **kwargs: Any) -> _FakeResource:
        captured["kwargs"] = kwargs
        return _FakeResource()

    with patch.object(state_store.boto3, "resource", side_effect=_fake_resource):
        state_store._get_table()

    assert captured["table_name"] == "agentcore-starter-dev"
    assert captured["kwargs"]["region_name"] == "us-east-1"
    assert captured["kwargs"]["endpoint_url"] is None
