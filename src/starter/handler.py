# Copyright (c) 2026 John Carter. All rights reserved.
"""Hello-world Lambda entry point. Replace with your application logic."""

from __future__ import annotations

import json
from typing import Any

from starter.logging_config import configure_logging, get_logger

configure_logging("agentcore-starter")
logger = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """AWS Lambda + Function URL entry point."""
    logger.info(
        "request received",
        extra={"path": event.get("rawPath", "/"), "method": event.get("requestContext", {}).get("http", {}).get("method", "?")},
    )
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "hello from agentcore-starter"}),
    }
