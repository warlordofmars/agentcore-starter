# Copyright (c) 2026 John Carter. All rights reserved.
"""
Admin-only endpoint for CloudWatch Logs browsing.

GET /api/admin/logs
  ?group=all|mcp|api   (default: all)
  &window=15m|1h|3h|24h (default: 1h)
  &filter=<pattern>     (optional CloudWatch filter pattern)
  &next_token=<token>   (optional pagination token from previous response)

Returns up to 500 log events sorted newest-first, with an optional
next_token for pagination.
"""

from __future__ import annotations

import os
import time
from typing import Annotated, Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query

from hive.api._auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

ENVIRONMENT = os.environ.get("HIVE_ENV", os.environ.get("ENV", "local"))

# MCP log group is injected by CDK (mcp_fn.function_name has no cycle).
# API log group is derived from AWS_LAMBDA_FUNCTION_NAME, which the Lambda
# runtime injects automatically — avoids a CDK self-reference circular dep.
_MCP_LOG_GROUP = os.environ.get("HIVE_MCP_LOG_GROUP", f"/aws/lambda/hive-{ENVIRONMENT}-mcp")
_AWS_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")
_API_LOG_GROUP = (
    f"/aws/lambda/{_AWS_FUNCTION_NAME}"
    if _AWS_FUNCTION_NAME
    else f"/aws/lambda/hive-{ENVIRONMENT}-api"
)

# Map human window labels → milliseconds
_WINDOW_MS: dict[str, int] = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "3h": 3 * 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
}

_MAX_EVENTS = 500


def _log_group_names(group: str) -> list[str]:
    """Return the CloudWatch log group name(s) for the requested group selector."""
    if group == "mcp":
        return [_MCP_LOG_GROUP]
    if group == "api":
        return [_API_LOG_GROUP]
    return [_MCP_LOG_GROUP, _API_LOG_GROUP]


def _fetch_log_events(
    group_names: list[str],
    start_ms: int,
    end_ms: int,
    filter_pattern: str,
    next_token: str | None,
    limit: int,
) -> dict[str, Any]:
    """Call CloudWatch Logs FilterLogEvents across one or more log groups."""
    client = boto3.client("logs")
    all_events: list[dict[str, Any]] = []
    returned_token: str | None = None

    for group_name in group_names:
        kwargs: dict[str, Any] = {
            "logGroupName": group_name,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern
        if next_token:
            kwargs["nextToken"] = next_token

        try:
            resp = client.filter_log_events(**kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "ResourceNotFoundException":
                # Log group doesn't exist yet (e.g. local/dev env with no traffic)
                continue
            raise HTTPException(status_code=502, detail=f"CloudWatch Logs error: {code}") from exc

        for event in resp.get("events", []):
            all_events.append(
                {
                    "timestamp": event["timestamp"],
                    "message": event["message"],
                    "log_group": group_name,
                    "log_stream": event.get("logStreamName", ""),
                    "event_id": event.get("eventId", ""),
                }
            )
        if not returned_token:
            returned_token = resp.get("nextToken")

    # Sort newest-first
    all_events.sort(key=lambda e: e["timestamp"], reverse=True)
    return {
        "events": all_events[:limit],
        "next_token": returned_token,
    }


@router.get(
    "/logs",
    summary="Get CloudWatch log events",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Admin role required"},
        502: {"description": "CloudWatch Logs error"},
    },
)
async def get_logs(
    _claims: Annotated[dict[str, Any], Depends(require_admin)],
    group: Annotated[str, Query(pattern="^(all|mcp|api)$")] = "all",
    window: Annotated[str, Query(pattern="^(15m|1h|3h|24h)$")] = "1h",
    filter_pattern: Annotated[str, Query(alias="filter")] = "",
    next_token: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Return recent CloudWatch log events. Admin-only.

    Args:
        group: Which log group(s) to query — mcp, api, or all.
        window: Lookback window — 15m, 1h, 3h, or 24h.
        filter_pattern: Optional CloudWatch filter pattern (passed verbatim).
        next_token: Pagination token from a previous response.
    """
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - _WINDOW_MS[window]
    group_names = _log_group_names(group)
    return _fetch_log_events(group_names, start_ms, end_ms, filter_pattern, next_token, _MAX_EVENTS)
