# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the /api/agents/echo and /api/agents/echo/stream endpoints."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
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


# ---------------------------------------------------------------------------
# /api/agents/echo/stream
# ---------------------------------------------------------------------------


def _fake_stream(request) -> Iterator[str]:
    yield f"data: {json.dumps({'type': 'delta', 'text': 'Hi'})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'stop_reason': 'end_turn', 'input_tokens': 5, 'output_tokens': 3})}\n\n"


def test_echo_stream_requires_auth() -> None:
    resp = client.post("/api/agents/echo/stream", json={"message": "Hi"})
    assert resp.status_code in (401, 403)


def test_echo_stream_returns_event_stream_content_type() -> None:
    with patch("starter.api.agents.converse_stream", side_effect=_fake_stream):
        resp = client.post(
            "/api/agents/echo/stream",
            json={"message": "Hi"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


def test_echo_stream_yields_delta_and_done_events() -> None:
    with patch("starter.api.agents.converse_stream", side_effect=_fake_stream):
        resp = client.post(
            "/api/agents/echo/stream",
            json={"message": "Hi"},
            headers=_auth_headers(),
        )

    events = [line for line in resp.text.split("\n\n") if line.startswith("data: ")]
    assert len(events) == 2
    delta = json.loads(events[0][len("data: ") :])
    assert delta == {"type": "delta", "text": "Hi"}
    done = json.loads(events[1][len("data: ") :])
    assert done["type"] == "done"
    assert done["stop_reason"] == "end_turn"


def test_echo_stream_forwards_system_prompt() -> None:
    captured: list = []

    def _capture(req) -> Iterator[str]:
        captured.append(req)
        yield f"data: {json.dumps({'type': 'done', 'stop_reason': 'end_turn', 'input_tokens': 1, 'output_tokens': 1})}\n\n"

    with patch("starter.api.agents.converse_stream", side_effect=_capture):
        client.post(
            "/api/agents/echo/stream",
            json={"message": "Hi", "system": "Be terse."},
            headers=_auth_headers(),
        )

    assert len(captured) == 1
    assert captured[0].system == "Be terse."
