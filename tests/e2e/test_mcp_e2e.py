# Copyright (c) 2026 John Carter. All rights reserved.
"""
E2E tests for the deployed Hive MCP server.
Requires environment variables:
  HIVE_MCP_URL    — Function URL of the deployed MCP Lambda
  HIVE_API_URL    — Function URL of the deployed management API Lambda
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

MCP_URL = os.environ.get("HIVE_MCP_URL")

pytestmark = pytest.mark.skipif(
    not MCP_URL,
    reason="HIVE_MCP_URL not set — skipping e2e tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


async def _call(http, token: str, name: str, arguments: dict, req_id: int = 1) -> dict:
    """Send a tools/call JSON-RPC request and return the parsed response."""
    resp = await http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200, f"Unexpected HTTP {resp.status_code}: {resp.text}"
    return resp.json()


def _text(result: dict) -> str:
    """Extract the text payload from a tools/call JSON-RPC response."""
    return result.get("result", {}).get("content", [{}])[0].get("text", "")


def _is_error(result: dict) -> bool:
    return result.get("result", {}).get("isError", False)


def _run_id() -> str:
    """Short unique prefix for keys/tags created in a test run."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Tool coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMCPToolsE2E:
    async def test_remember_and_recall(self, live_token):
        """Store a memory and retrieve it by key."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-basic"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                r = await _call(
                    http, live_token, "remember", {"key": key, "value": "hello-e2e", "tags": []}
                )
                assert not _is_error(r), f"remember failed: {_text(r)}"
                assert "Stored" in _text(r)

                r2 = await _call(http, live_token, "recall", {"key": key})
                assert not _is_error(r2), f"recall failed: {_text(r2)}"
                assert "hello-e2e" in _text(r2)
            finally:
                await _call(http, live_token, "forget", {"key": key})

    async def test_remember_upsert(self, live_token):
        """Updating an existing key returns 'Updated' and recall reflects the new value."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-upsert"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                await _call(
                    http, live_token, "remember", {"key": key, "value": "original", "tags": []}
                )

                r = await _call(
                    http, live_token, "remember", {"key": key, "value": "updated", "tags": []}
                )
                assert not _is_error(r), f"upsert failed: {_text(r)}"
                assert "Updated" in _text(r)

                r2 = await _call(http, live_token, "recall", {"key": key})
                assert "updated" in _text(r2)
            finally:
                await _call(http, live_token, "forget", {"key": key})

    async def test_remember_idempotent(self, live_token):
        """Calling remember with the same key+value+tags is a no-op."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-idempotent"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                await _call(
                    http, live_token, "remember", {"key": key, "value": "same", "tags": ["t"]}
                )

                r = await _call(
                    http, live_token, "remember", {"key": key, "value": "same", "tags": ["t"]}
                )
                assert not _is_error(r), f"idempotent remember failed: {_text(r)}"
                assert "unchanged" in _text(r).lower()
            finally:
                await _call(http, live_token, "forget", {"key": key})

    async def test_forget(self, live_token):
        """Deleting a memory makes subsequent recall raise a ToolError."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-forget"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            await _call(
                http, live_token, "remember", {"key": key, "value": "to-delete", "tags": []}
            )

            r = await _call(http, live_token, "forget", {"key": key})
            assert not _is_error(r), f"forget failed: {_text(r)}"
            assert "Deleted" in _text(r)

            r2 = await _call(http, live_token, "recall", {"key": key})
            assert _is_error(r2), "Expected ToolError after forget but got success"
            assert key in _text(r2)

    async def test_recall_missing_key(self, live_token):
        """Recalling a key that does not exist raises a ToolError."""
        import httpx

        key = f"e2e-{_run_id()}-nonexistent"
        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            r = await _call(http, live_token, "recall", {"key": key})
            assert _is_error(r), "Expected ToolError for missing key"
            assert "No memory found" in _text(r)

    async def test_forget_missing_key(self, live_token):
        """Forgetting a key that does not exist raises a ToolError."""
        import httpx

        key = f"e2e-{_run_id()}-nonexistent"
        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            r = await _call(http, live_token, "forget", {"key": key})
            assert _is_error(r), "Expected ToolError for missing key"
            assert "No memory found" in _text(r)

    async def test_list_memories_by_tag(self, live_token):
        """Memories stored with a unique tag appear in list_memories results."""
        import httpx

        rid = _run_id()
        tag = f"e2e-tag-{rid}"
        keys = [f"e2e-{rid}-list-{i}" for i in range(3)]

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                for k in keys:
                    await _call(
                        http, live_token, "remember", {"key": k, "value": f"val-{k}", "tags": [tag]}
                    )

                r = await _call(http, live_token, "list_memories", {"tag": tag})
                assert not _is_error(r), f"list_memories failed: {_text(r)}"
                data = json.loads(_text(r))
                listed_keys = [item["key"] for item in data["items"]]
                for k in keys:
                    assert k in listed_keys, f"Expected key {k!r} in list results"
                assert data["count"] >= 3
            finally:
                for k in keys:
                    await _call(http, live_token, "forget", {"key": k})

    async def test_list_memories_empty_tag(self, live_token):
        """list_memories for a tag with no memories returns an empty list, not an error."""
        import httpx

        tag = f"e2e-empty-{_run_id()}"
        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            r = await _call(http, live_token, "list_memories", {"tag": tag})
            assert not _is_error(r), f"list_memories errored on empty tag: {_text(r)}"
            data = json.loads(_text(r))
            assert data["items"] == []
            assert data["count"] == 0

    async def test_summarize_context(self, live_token):
        """summarize_context returns a formatted summary listing stored memories."""
        import httpx

        rid = _run_id()
        tag = f"e2e-sum-{rid}"
        key = f"e2e-{rid}-sum"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                await _call(
                    http,
                    live_token,
                    "remember",
                    {"key": key, "value": "summary-content", "tags": [tag]},
                )

                r = await _call(http, live_token, "summarize_context", {"topic": tag})
                assert not _is_error(r), f"summarize_context failed: {_text(r)}"
                text = _text(r)
                assert key in text
                assert "summary-content" in text
            finally:
                await _call(http, live_token, "forget", {"key": key})

    async def test_summarize_context_empty_topic(self, live_token):
        """summarize_context on a topic with no memories returns a 'no memories' message."""
        import httpx

        topic = f"e2e-empty-sum-{_run_id()}"
        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            r = await _call(http, live_token, "summarize_context", {"topic": topic})
            assert not _is_error(r), f"summarize_context errored on empty topic: {_text(r)}"
            assert "No memories found" in _text(r)

    async def test_search_memories(self, live_token):
        """search_memories returns a result dict without errors."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-search"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                await _call(
                    http,
                    live_token,
                    "remember",
                    {"key": key, "value": f"unique-searchable-{rid}", "tags": []},
                )

                r = await _call(
                    http, live_token, "search_memories", {"query": f"unique-searchable-{rid}"}
                )
                assert not _is_error(r), f"search_memories failed: {_text(r)}"
                data = json.loads(_text(r))
                assert "items" in data
                assert "count" in data
            finally:
                await _call(http, live_token, "forget", {"key": key})

    async def test_search_memories_no_results(self, live_token):
        """search_memories for an unmatched query returns empty items, not an error."""
        import httpx

        query = f"zzznomatch-{_run_id()}"
        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            r = await _call(http, live_token, "search_memories", {"query": query})
            assert not _is_error(r), f"search_memories errored: {_text(r)}"
            data = json.loads(_text(r))
            assert "items" in data


# ---------------------------------------------------------------------------
# Auth failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMCPAuthE2E:
    async def test_invalid_token_rejected(self):
        """Any tool call with a garbage Bearer token is rejected (401 or ToolError)."""
        import httpx

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=30.0) as http:
            resp = await http.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "recall", "arguments": {"key": "any-key"}},
                },
                headers={
                    **_headers("not-a-real-token"),
                },
            )
            # FastMCP may return 401 directly or 200 with a ToolError payload
            if resp.status_code == 401:
                return
            assert resp.status_code == 200
            r = resp.json()
            assert _is_error(r), "Expected ToolError for invalid token"
            assert "Unauthorized" in _text(r)

    async def test_missing_token_rejected(self):
        """A request without an Authorization header is rejected (401 or ToolError)."""
        import httpx

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=30.0) as http:
            resp = await http.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "recall", "arguments": {"key": "any-key"}},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            # FastMCP may return 401 directly or 200 with a ToolError payload
            if resp.status_code == 401:
                return
            assert resp.status_code == 200
            r = resp.json()
            assert _is_error(r), "Expected ToolError for missing token"
            assert "Unauthorized" in _text(r)


# ---------------------------------------------------------------------------
# Multi-client isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMCPIsolationE2E:
    @pytest.mark.xfail(
        strict=False,
        reason="Client-level key isolation not yet enforced — memories keyed globally. "
        "This test documents the desired behaviour.",
    )
    async def test_client_cannot_recall_other_clients_memory(self, live_token, live_token_b):
        """Client B must not be able to recall a memory stored by client A."""
        import httpx

        rid = _run_id()
        key = f"e2e-{rid}-isolation"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                r = await _call(
                    http,
                    live_token,
                    "remember",
                    {"key": key, "value": "client-a-secret", "tags": []},
                )
                assert not _is_error(r)

                r2 = await _call(http, live_token_b, "recall", {"key": key})
                assert _is_error(r2), (
                    "Client B should NOT be able to recall client A's memory, "
                    f"but got: {_text(r2)!r}"
                )
            finally:
                await _call(http, live_token, "forget", {"key": key})

    @pytest.mark.xfail(
        strict=False,
        reason="Client-level tag isolation not yet enforced — tag index is global. "
        "This test documents the desired behaviour.",
    )
    async def test_client_cannot_list_other_clients_memories(self, live_token, live_token_b):
        """Client B's list_memories must not return memories tagged by client A."""
        import httpx

        rid = _run_id()
        tag = f"e2e-iso-tag-{rid}"
        key = f"e2e-{rid}-iso-list"

        async with httpx.AsyncClient(base_url=MCP_URL, timeout=60.0) as http:
            try:
                r = await _call(
                    http, live_token, "remember", {"key": key, "value": "private", "tags": [tag]}
                )
                assert not _is_error(r)

                r2 = await _call(http, live_token_b, "list_memories", {"tag": tag})
                assert not _is_error(r2)
                data = json.loads(_text(r2))
                assert data["count"] == 0, (
                    f"Client B should see 0 memories for client A's tag, got {data['count']}"
                )
            finally:
                await _call(http, live_token, "forget", {"key": key})
