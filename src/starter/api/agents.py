# Copyright (c) 2026 John Carter. All rights reserved.
"""Agent scaffold endpoints — replace with your agent logic."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from starter.agents.bedrock import BedrockMessage, ConverseRequest, converse, converse_stream
from starter.agents.inline_agent import InlineAgentRequest, invoke, invoke_stream
from starter.api._auth import require_mgmt_user

router = APIRouter()


class EchoRequest(BaseModel):
    message: str
    system: str | None = None


class EchoResponse(BaseModel):
    reply: str
    input_tokens: int
    output_tokens: int


@router.post("/agents/echo", response_model=EchoResponse)
def echo(
    body: EchoRequest,
    _claims: dict[str, Any] = Depends(require_mgmt_user),
) -> EchoResponse:
    """Echo endpoint — forwards the message to Bedrock and returns the reply.

    This is a scaffold for your own agent endpoints.  Replace the implementation
    with whatever tool-calling, memory lookup, or multi-step logic you need.
    """
    result = converse(
        ConverseRequest(
            messages=[BedrockMessage(role="user", content=body.message)],
            system=body.system,
        )
    )
    return EchoResponse(
        reply=result.content,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


@router.post("/agents/echo/stream")
def echo_stream(
    body: EchoRequest,
    _claims: dict[str, Any] = Depends(require_mgmt_user),
) -> StreamingResponse:
    """Streaming echo endpoint — returns an SSE stream of Bedrock reply tokens.

    Each ``data:`` event is a JSON object with ``type`` equal to ``"delta"``
    (incremental text) or ``"done"`` (final event with token counts).

    Replace or extend this scaffold with your own streaming agent logic.
    """

    def _stream() -> Iterator[str]:
        yield from converse_stream(
            ConverseRequest(
                messages=[BedrockMessage(role="user", content=body.message)],
                system=body.system,
            )
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Inline agent endpoints (Bedrock Agents via invoke_inline_agent)
# ---------------------------------------------------------------------------


class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None
    instruction: str | None = None


class AgentResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/agents/invoke", response_model=AgentResponse)
def agent_invoke(
    body: AgentRequest,
    claims: dict[str, Any] = Depends(require_mgmt_user),
) -> AgentResponse:
    """Invoke a Bedrock inline agent and return the full response.

    The agent maintains conversation history within a session — pass the same
    ``session_id`` across turns to continue a conversation.  Omit it to start
    a new session; the returned ``session_id`` can be stored and reused.

    Session scope is automatically namespaced to the authenticated user so
    sessions are never shared across users.
    """
    result = invoke(
        InlineAgentRequest(
            message=body.message,
            session_id=body.session_id,
            instruction=body.instruction,
        ),
        user_id=claims["sub"],
    )
    return AgentResponse(reply=result.reply, session_id=result.session_id)


@router.post("/agents/invoke/stream")
def agent_invoke_stream(
    body: AgentRequest,
    claims: dict[str, Any] = Depends(require_mgmt_user),
) -> StreamingResponse:
    """Streaming inline agent invocation — returns an SSE stream of agent reply chunks.

    Event schema mirrors ``/agents/echo/stream``:

    * ``{"type": "delta", "text": "..."}`` — incremental text chunk.
    * ``{"type": "done", "session_id": "..."}`` — final event; ``session_id``
      can be stored and reused to continue the conversation.
    """

    def _stream() -> Iterator[str]:
        yield from invoke_stream(
            InlineAgentRequest(
                message=body.message,
                session_id=body.session_id,
                instruction=body.instruction,
            ),
            user_id=claims["sub"],
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")
