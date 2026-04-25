# Copyright (c) 2026 John Carter. All rights reserved.
"""Agent scaffold endpoints — replace with your agent logic."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from starter.agents.bedrock import BedrockMessage, ConverseRequest, converse
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
async def echo(
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
