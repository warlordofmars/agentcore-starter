# Copyright (c) 2026 John Carter. All rights reserved.
"""Synthetic traffic script — exercises the full MCP + management API chain
against a deployed Hive environment.

Generates real invocation counts, latency samples, and token events that are
visible in the CloudWatch metrics dashboard.

Usage:
  uv run python scripts/synthetic_traffic.py

Environment variables (required):
  HIVE_API_URL          Management API Lambda Function URL
  HIVE_MCP_URL          MCP Lambda Function URL
  HIVE_BEARER_TOKEN     Valid Bearer token (pre-issued long-lived token)

Exit codes:
  0  All checks passed
  1  One or more checks failed
"""

from __future__ import annotations

import os
import sys

import httpx

API_URL = os.environ.get("HIVE_API_URL", "").rstrip("/")
MCP_URL = os.environ.get("HIVE_MCP_URL", "").rstrip("/")
TOKEN = os.environ.get("HIVE_BEARER_TOKEN", "")

# Synthetic data uses a reserved prefix so it is identifiable in the activity log
# and cleaned up on every run.
_SYNTHETIC_KEY = "synthetic/health-check"
_SYNTHETIC_VALUE = "synthetic traffic check — safe to delete"
_SYNTHETIC_TAG = "synthetic"


def _mcp_call(http: httpx.Client, tool: str, arguments: dict, req_id: int = 1) -> dict:
    resp = http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def _api_call(http: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    return http.request(
        method,
        path,
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=30.0,
        **kwargs,
    )


def run() -> bool:
    errors: list[str] = []

    # ── MCP tool calls ────────────────────────────────────────────────────────
    with httpx.Client(base_url=MCP_URL) as mcp:
        # remember
        try:
            _mcp_call(
                mcp,
                "remember",
                {"key": _SYNTHETIC_KEY, "value": _SYNTHETIC_VALUE, "tags": [_SYNTHETIC_TAG]},
                req_id=1,
            )
        except Exception as exc:
            errors.append(f"remember: {exc}")

        # recall
        try:
            result = _mcp_call(mcp, "recall", {"key": _SYNTHETIC_KEY}, req_id=2)
            if _SYNTHETIC_VALUE not in str(result):
                errors.append("recall: expected value not found in response")
        except Exception as exc:
            errors.append(f"recall: {exc}")

        # list_memories
        try:
            _mcp_call(mcp, "list_memories", {"tag": _SYNTHETIC_TAG}, req_id=3)
        except Exception as exc:
            errors.append(f"list_memories: {exc}")

        # summarize_context
        try:
            _mcp_call(mcp, "summarize_context", {"topic": _SYNTHETIC_TAG}, req_id=4)
        except Exception as exc:
            errors.append(f"summarize_context: {exc}")

        # forget — cleanup synthetic key regardless of earlier failures
        try:
            _mcp_call(mcp, "forget", {"key": _SYNTHETIC_KEY}, req_id=5)
        except Exception as exc:
            errors.append(f"forget: {exc}")

    # ── Management API health check ───────────────────────────────────────────
    # /health is unauthenticated — invokes the API Lambda and exercises the
    # full CloudFront → Lambda path without requiring a management session JWT.
    with httpx.Client(base_url=API_URL) as api:
        try:
            api.get("/health", timeout=30.0).raise_for_status()
        except Exception as exc:
            errors.append(f"GET /health: {exc}")

    if errors:
        print("FAILURES:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return False

    print("All synthetic checks passed.")
    return True


def main() -> None:
    if not API_URL or not MCP_URL or not TOKEN:
        print(
            "Error: HIVE_API_URL, HIVE_MCP_URL, and HIVE_BEARER_TOKEN must all be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0 if run() else 1)


if __name__ == "__main__":
    main()
