# Copyright (c) 2026 John Carter. All rights reserved.
"""Async-first Hive client with sync convenience wrappers."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from hive_client.models import Memory, MemoryList

_DEFAULT_BASE_URL = "https://app.hive-memory.com"
_DEFAULT_TIMEOUT = 30.0


class HiveError(Exception):
    """Raised when the Hive API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class HiveClient:
    """Hive memory API client.

    Usage::

        client = HiveClient(api_key="hive_sk_...")
        await client.remember("my-key", "my value", tags=["tag1"])
        memory = await client.recall("my-key")
        print(memory.value)

    All methods are async. Use the ``sync_*`` variants for synchronous code::

        client.sync_remember("my-key", "my value")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=self._timeout,
        ) as http:
            resp = await http.request(method, path, params=params, json=json)
            if resp.status_code == 204:
                return None
            try:
                body = resp.json()
            except Exception:
                body = {}
            if not resp.is_success:
                detail = (
                    body.get("detail", resp.reason_phrase)
                    if isinstance(body, dict)
                    else resp.reason_phrase
                )
                raise HiveError(resp.status_code, detail)
            return body

    def _run(self, coro: Any) -> Any:
        """Run a coroutine synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    # ------------------------------------------------------------------ #
    # Async API                                                            #
    # ------------------------------------------------------------------ #

    async def remember(
        self,
        key: str,
        value: str,
        tags: list[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> Memory:
        """Store or update a memory."""
        body: dict[str, Any] = {"key": key, "value": value, "tags": tags or []}
        if ttl_seconds is not None:
            body["ttl_seconds"] = ttl_seconds
        data = await self._request("POST", "/api/memories", json=body)
        return Memory.model_validate(data)

    async def recall(self, key: str) -> Memory | None:
        """Retrieve a memory by key (returns None if not found)."""
        results = await self.list_memories()
        for m in results.items:
            if m.key == key:
                return m
        return None

    async def get_memory(self, memory_id: str) -> Memory:
        """Retrieve a memory by ID."""
        data = await self._request("GET", f"/api/memories/{memory_id}")
        return Memory.model_validate(data)

    async def forget(self, memory_id: str) -> None:
        """Delete a memory by ID."""
        await self._request("DELETE", f"/api/memories/{memory_id}")

    async def list_memories(
        self,
        tag: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> MemoryList:
        """List memories, optionally filtered by tag."""
        params: dict[str, Any] = {"limit": limit}
        if tag:
            params["tag"] = tag
        if cursor:
            params["cursor"] = cursor
        data = await self._request("GET", "/api/memories", params=params)
        return MemoryList.model_validate(data)

    async def search_memories(self, query: str, limit: int = 50) -> MemoryList:
        """Semantic search across memories."""
        params: dict[str, Any] = {"search": query, "limit": limit}
        data = await self._request("GET", "/api/memories", params=params)
        return MemoryList.model_validate(data)

    # ------------------------------------------------------------------ #
    # Sync convenience wrappers                                            #
    # ------------------------------------------------------------------ #

    def sync_remember(
        self,
        key: str,
        value: str,
        tags: list[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> Memory:
        """Synchronous wrapper for :meth:`remember`."""
        return self._run(self.remember(key, value, tags=tags, ttl_seconds=ttl_seconds))

    def sync_recall(self, key: str) -> Memory | None:
        """Synchronous wrapper for :meth:`recall`."""
        return self._run(self.recall(key))

    def sync_get_memory(self, memory_id: str) -> Memory:
        """Synchronous wrapper for :meth:`get_memory`."""
        return self._run(self.get_memory(memory_id))

    def sync_forget(self, memory_id: str) -> None:
        """Synchronous wrapper for :meth:`forget`."""
        self._run(self.forget(memory_id))

    def sync_list_memories(
        self,
        tag: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> MemoryList:
        """Synchronous wrapper for :meth:`list_memories`."""
        return self._run(self.list_memories(tag=tag, limit=limit, cursor=cursor))

    def sync_search_memories(self, query: str, limit: int = 50) -> MemoryList:
        """Synchronous wrapper for :meth:`search_memories`."""
        return self._run(self.search_memories(query, limit=limit))
