# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for agent API endpoints (echo, echo/stream, invoke, invoke/stream)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("STARTER_JWT_SECRET", "test-secret-for-unit-tests")

from starter.agents.bedrock import ConverseResponse  # noqa: E402
from starter.agents.inline_agent import InlineAgentResponse  # noqa: E402
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


# ---------------------------------------------------------------------------
# /api/agents/invoke
# ---------------------------------------------------------------------------


def _mock_invoke_response(
    reply: str = "Agent reply", session_id: str = "s1"
) -> InlineAgentResponse:
    return InlineAgentResponse(reply=reply, session_id=session_id)


def test_agent_invoke_requires_auth() -> None:
    resp = client.post("/api/agents/invoke", json={"message": "Hi"})
    assert resp.status_code in (401, 403)


def test_agent_invoke_returns_reply_and_session_id() -> None:
    with patch(
        "starter.api.agents.invoke",
        return_value=_mock_invoke_response("Hello from agent", "sess-42"),
    ):
        resp = client.post(
            "/api/agents/invoke",
            json={"message": "Hi"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hello from agent"
    assert data["session_id"] == "sess-42"


def test_agent_invoke_forwards_session_and_instruction() -> None:
    captured: list = []

    def _capture(req, *, user_id):
        captured.append((req, user_id))
        return _mock_invoke_response()

    with patch("starter.api.agents.invoke", side_effect=_capture):
        client.post(
            "/api/agents/invoke",
            json={"message": "Hi", "session_id": "my-sess", "instruction": "Be concise."},
            headers=_auth_headers(),
        )

    assert len(captured) == 1
    req, user_id = captured[0]
    assert req.session_id == "my-sess"
    assert req.instruction == "Be concise."
    assert user_id == "u1"  # JWT sub claim


# ---------------------------------------------------------------------------
# /api/agents/invoke/stream
# ---------------------------------------------------------------------------


def _fake_invoke_stream(req, *, user_id) -> Iterator[str]:
    yield f"data: {json.dumps({'type': 'delta', 'text': 'Hi'})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'session_id': req.session_id or 'new-sess'})}\n\n"


def test_agent_invoke_stream_requires_auth() -> None:
    resp = client.post("/api/agents/invoke/stream", json={"message": "Hi"})
    assert resp.status_code in (401, 403)


def test_agent_invoke_stream_returns_event_stream_content_type() -> None:
    with patch("starter.api.agents.invoke_stream", side_effect=_fake_invoke_stream):
        resp = client.post(
            "/api/agents/invoke/stream",
            json={"message": "Hi", "session_id": "s1"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


def test_agent_invoke_stream_yields_delta_and_done() -> None:
    with patch("starter.api.agents.invoke_stream", side_effect=_fake_invoke_stream):
        resp = client.post(
            "/api/agents/invoke/stream",
            json={"message": "Hi", "session_id": "s1"},
            headers=_auth_headers(),
        )

    events = [line for line in resp.text.split("\n\n") if line.startswith("data: ")]
    assert len(events) == 2
    delta = json.loads(events[0][len("data: ") :])
    assert delta == {"type": "delta", "text": "Hi"}
    done = json.loads(events[1][len("data: ") :])
    assert done["type"] == "done"


def test_agent_invoke_stream_forwards_user_id_from_claims() -> None:
    captured: list = []

    def _capture(req, *, user_id) -> Iterator[str]:
        captured.append(user_id)
        yield f"data: {json.dumps({'type': 'done', 'session_id': 's1'})}\n\n"

    with patch("starter.api.agents.invoke_stream", side_effect=_capture):
        client.post(
            "/api/agents/invoke/stream",
            json={"message": "Hi"},
            headers=_auth_headers(),
        )

    assert captured == ["u1"]  # JWT sub claim
