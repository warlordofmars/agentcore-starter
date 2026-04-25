# Copyright (c) 2026 John Carter. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from starter.agents.bedrock import (
    BedrockMessage,
    ConverseRequest,
    ConverseResponse,
    _bedrock_client,
    converse,
    get_model_id,
)


def setup_function() -> None:
    _bedrock_client.cache_clear()


def teardown_function() -> None:
    _bedrock_client.cache_clear()


def test_get_model_id_default() -> None:
    env = {k: v for k, v in os.environ.items() if k != "BEDROCK_MODEL_ID"}
    with patch.dict(os.environ, env, clear=True):
        assert get_model_id() == "anthropic.claude-sonnet-4-6"


def test_get_model_id_env_override() -> None:
    with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "anthropic.claude-haiku-4-5-20251001-v1:0"}):
        assert get_model_id() == "anthropic.claude-haiku-4-5-20251001-v1:0"


def test_bedrock_client_passes_region_when_set() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("AWS_REGION", "AWS_DEFAULT_REGION")}
    with (
        patch.dict(os.environ, {**env, "AWS_REGION": "eu-west-1"}, clear=True),
        patch("boto3.client", return_value=MagicMock()) as mock_boto,
    ):
        _bedrock_client()
        mock_boto.assert_called_once_with("bedrock-runtime", region_name="eu-west-1")


def test_bedrock_client_omits_region_when_unset() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("AWS_REGION", "AWS_DEFAULT_REGION")}
    with (
        patch.dict(os.environ, env, clear=True),
        patch("boto3.client", return_value=MagicMock()) as mock_boto,
    ):
        _bedrock_client()
        mock_boto.assert_called_once_with("bedrock-runtime")


def test_bedrock_client_falls_back_to_default_region() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("AWS_REGION", "AWS_DEFAULT_REGION")}
    with (
        patch.dict(os.environ, {**env, "AWS_DEFAULT_REGION": "ap-southeast-1"}, clear=True),
        patch("boto3.client", return_value=MagicMock()) as mock_boto,
    ):
        _bedrock_client()
        mock_boto.assert_called_once_with("bedrock-runtime", region_name="ap-southeast-1")


def _mock_converse_response(text: str = "Hello!") -> dict:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": 10, "outputTokens": 5},
        "stopReason": "end_turn",
    }


def test_converse_success() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _mock_converse_response("Hi there!")

    with patch("starter.agents.bedrock._bedrock_client", return_value=mock_client):
        result = converse(ConverseRequest(messages=[BedrockMessage(role="user", content="Hello")]))

    assert isinstance(result, ConverseResponse)
    assert result.content == "Hi there!"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.stop_reason == "end_turn"


def test_converse_with_system_prompt() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _mock_converse_response("Got it.")

    with patch("starter.agents.bedrock._bedrock_client", return_value=mock_client):
        converse(
            ConverseRequest(
                messages=[BedrockMessage(role="user", content="Hi")],
                system="You are a helpful assistant.",
            )
        )

    call_kwargs = mock_client.converse.call_args[1]
    assert "system" in call_kwargs
    assert call_kwargs["system"] == [{"text": "You are a helpful assistant."}]


def test_converse_without_system_prompt_omits_key() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _mock_converse_response()

    with patch("starter.agents.bedrock._bedrock_client", return_value=mock_client):
        converse(ConverseRequest(messages=[BedrockMessage(role="user", content="Hi")]))

    call_kwargs = mock_client.converse.call_args[1]
    assert "system" not in call_kwargs


def test_converse_message_shape() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _mock_converse_response()

    with patch("starter.agents.bedrock._bedrock_client", return_value=mock_client):
        converse(
            ConverseRequest(
                messages=[
                    BedrockMessage(role="user", content="Hello"),
                    BedrockMessage(role="assistant", content="Hi"),
                    BedrockMessage(role="user", content="Bye"),
                ]
            )
        )

    call_kwargs = mock_client.converse.call_args[1]
    assert call_kwargs["messages"] == [
        {"role": "user", "content": [{"text": "Hello"}]},
        {"role": "assistant", "content": [{"text": "Hi"}]},
        {"role": "user", "content": [{"text": "Bye"}]},
    ]
