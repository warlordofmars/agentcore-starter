# Copyright (c) 2026 John Carter. All rights reserved.
from __future__ import annotations

import os
from functools import lru_cache
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


@lru_cache(maxsize=1)
def _bedrock_client() -> BedrockRuntimeClient:
    """Return a cached Bedrock runtime client.

    Region resolution follows boto3 precedence: AWS_REGION → AWS_DEFAULT_REGION
    → ~/.aws/config.  We only pass region_name when one of the env vars is
    explicitly set so local dev and CI inherit the configured default naturally.
    """
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    kwargs: dict = {}
    if region:
        kwargs["region_name"] = region
    return boto3.client("bedrock-runtime", **kwargs)  # type: ignore[return-value]


def converse(request: ConverseRequest) -> ConverseResponse:
    client = _bedrock_client()
    messages = [{"role": m.role, "content": [{"text": m.content}]} for m in request.messages]
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
