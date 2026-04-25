# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the hello-world Lambda handler."""

import json

from starter.handler import lambda_handler


def test_lambda_handler_returns_200():
    event = {"rawPath": "/", "requestContext": {"http": {"method": "GET"}}}
    result = lambda_handler(event, object())
    assert result["statusCode"] == 200


def test_lambda_handler_body_contains_message():
    event = {}
    result = lambda_handler(event, object())
    body = json.loads(result["body"])
    assert body["message"] == "hello from agentcore-starter"


def test_lambda_handler_content_type():
    result = lambda_handler({}, object())
    assert result["headers"]["Content-Type"] == "application/json"
