# Copyright (c) 2026 John Carter. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import boto3
from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient


class BedrockMessage(BaseModel):
    role: str
    content: str


class ConverseRequest(BaseModel):
    messages: list[BedrockMessage]
    system: str | None = None
    max_tokens: int = 1024


class ConverseResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


def get_model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")


def converse(request: ConverseRequest) -> ConverseResponse:
    client: BedrockRuntimeClient = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    messages = [
        {"role": m.role, "content": [{"text": m.content}]}
        for m in request.messages
    ]
    kwargs: dict = {
        "modelId": get_model_id(),
        "messages": messages,
        "inferenceConfig": {"maxTokens": request.max_tokens},
    }
    if request.system:
        kwargs["system"] = [{"text": request.system}]
    response = client.converse(**kwargs)
    return ConverseResponse(
        content=response["output"]["message"]["content"][0]["text"],
        input_tokens=response["usage"]["inputTokens"],
        output_tokens=response["usage"]["outputTokens"],
        stop_reason=response["stopReason"],
    )
