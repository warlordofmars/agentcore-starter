# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the /api/agents/echo endpoint."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("STARTER_JWT_SECRET", "test-secret-for-unit-tests")

from starter.agents.bedrock import ConverseResponse  # noqa: E402
from starter.api.main import app  # noqa: E402
from starter.auth.tokens import issue_mgmt_jwt  # noqa: E402

client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    token = issue_mgmt_jwt(
        {"user_id": "u1", "email": "user@test.com", "display_name": "User", "role": "user"}
    )
    return {"Authorization": f"Bearer {token}"}


def _mock_converse(text: str = "Hello back!") -> ConverseResponse:
    return ConverseResponse(
        content=text,
        input_tokens=8,
        output_tokens=4,
        stop_reason="end_turn",
    )


def test_echo_requires_auth() -> None:
    resp = client.post("/api/agents/echo", json={"message": "Hi"})
    assert resp.status_code in (401, 403)


def test_echo_returns_reply() -> None:
    with patch("starter.api.agents.converse", return_value=_mock_converse("Hello back!")):
        resp = client.post(
            "/api/agents/echo",
            json={"message": "Hi"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hello back!"
    assert data["input_tokens"] == 8
    assert data["output_tokens"] == 4


def test_echo_forwards_system_prompt() -> None:
    captured: list = []

    def _capture(req):
        captured.append(req)
        return _mock_converse()

    with patch("starter.api.agents.converse", side_effect=_capture):
        client.post(
            "/api/agents/echo",
            json={"message": "Hi", "system": "Be concise."},
            headers=_auth_headers(),
        )

    assert len(captured) == 1
    assert captured[0].system == "Be concise."
