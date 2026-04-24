# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the Hive Python SDK (mocked HTTP)."""

from __future__ import annotations

import pytest
import pytest_asyncio  # noqa: F401 — registers asyncio mode
from hive_client import HiveClient
from hive_client.client import HiveError
from pytest_httpx import HTTPXMock

BASE_URL = "https://app.hive-memory.com"
API_KEY = "hive_sk_test"


@pytest.fixture
def client():
    return HiveClient(api_key=API_KEY, base_url=BASE_URL)


# ------------------------------------------------------------------ #
# remember                                                             #
# ------------------------------------------------------------------ #


class TestRemember:
    async def test_remember_sends_post(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/api/memories",
            json={"memory_id": "m1", "key": "k", "value": "v", "tags": []},
        )
        memory = await client.remember("k", "v")
        assert memory.memory_id == "m1"
        assert memory.key == "k"
        assert memory.value == "v"

    async def test_remember_sends_tags_and_ttl(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/api/memories",
            json={"memory_id": "m2", "key": "k2", "value": "v2", "tags": ["t1"]},
        )
        memory = await client.remember("k2", "v2", tags=["t1"], ttl_seconds=3600)
        assert memory.tags == ["t1"]
        request = httpx_mock.get_request()
        import json

        body = json.loads(request.content)
        assert body["ttl_seconds"] == 3600
        assert body["tags"] == ["t1"]

    async def test_remember_raises_on_error(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/api/memories",
            status_code=422,
            json={"detail": "Value too large"},
        )
        with pytest.raises(HiveError) as exc_info:
            await client.remember("k", "v" * 100_000)
        assert exc_info.value.status_code == 422
        assert "Value too large" in str(exc_info.value)


# ------------------------------------------------------------------ #
# get_memory                                                           #
# ------------------------------------------------------------------ #


class TestGetMemory:
    async def test_get_memory_sends_get(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/api/memories/m1",
            json={"memory_id": "m1", "key": "k", "value": "v", "tags": []},
        )
        memory = await client.get_memory("m1")
        assert memory.memory_id == "m1"

    async def test_get_memory_not_found_raises(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/api/memories/nope",
            status_code=404,
            json={"detail": "Memory not found"},
        )
        with pytest.raises(HiveError) as exc_info:
            await client.get_memory("nope")
        assert exc_info.value.status_code == 404


# ------------------------------------------------------------------ #
# forget                                                               #
# ------------------------------------------------------------------ #


class TestForget:
    async def test_forget_sends_delete(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/api/memories/m1",
            status_code=204,
        )
        result = await client.forget("m1")
        assert result is None


# ------------------------------------------------------------------ #
# list_memories                                                        #
# ------------------------------------------------------------------ #


class TestListMemories:
    async def test_list_returns_items(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            json={"items": [{"memory_id": "m1", "key": "k", "value": "v", "tags": []}]},
        )
        result = await client.list_memories()
        assert len(result.items) == 1
        assert result.items[0].key == "k"

    async def test_list_sends_tag_param(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": []})
        await client.list_memories(tag="mytag")
        request = httpx_mock.get_request()
        assert "tag=mytag" in str(request.url)

    async def test_list_sends_cursor_param(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": []})
        await client.list_memories(cursor="tok123")
        request = httpx_mock.get_request()
        assert "cursor=tok123" in str(request.url)


# ------------------------------------------------------------------ #
# search_memories                                                      #
# ------------------------------------------------------------------ #


class TestSearchMemories:
    async def test_search_sends_search_param(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": [], "count": 0})
        await client.search_memories("hello world")
        request = httpx_mock.get_request()
        assert "search=hello+world" in str(request.url) or "search=hello%20world" in str(
            request.url
        )


# ------------------------------------------------------------------ #
# recall                                                               #
# ------------------------------------------------------------------ #


class TestRecall:
    async def test_recall_finds_matching_key(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            json={
                "items": [
                    {"memory_id": "m1", "key": "target", "value": "found", "tags": []},
                    {"memory_id": "m2", "key": "other", "value": "other-val", "tags": []},
                ]
            },
        )
        memory = await client.recall("target")
        assert memory is not None
        assert memory.value == "found"

    async def test_recall_returns_none_when_not_found(
        self, client: HiveClient, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(method="GET", json={"items": []})
        memory = await client.recall("missing")
        assert memory is None


# ------------------------------------------------------------------ #
# Authorization header                                                 #
# ------------------------------------------------------------------ #


class TestAuth:
    async def test_sends_bearer_token(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": []})
        await client.list_memories()
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"


# ------------------------------------------------------------------ #
# Error handling — no detail field                                     #
# ------------------------------------------------------------------ #


class TestErrorHandling:
    async def test_error_without_detail_uses_reason_phrase(
        self, client: HiveClient, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            method="GET",
            status_code=500,
            json={},
        )
        with pytest.raises(HiveError) as exc_info:
            await client.list_memories()
        assert exc_info.value.status_code == 500

    async def test_error_with_unparseable_body(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            status_code=503,
            text="Service Unavailable",
        )
        with pytest.raises(HiveError) as exc_info:
            await client.list_memories()
        assert exc_info.value.status_code == 503


# ------------------------------------------------------------------ #
# Sync wrappers                                                        #
# ------------------------------------------------------------------ #


class TestSyncWrappers:
    def test_sync_remember(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/api/memories",
            json={"memory_id": "m1", "key": "k", "value": "v", "tags": []},
        )
        memory = client.sync_remember("k", "v")
        assert memory.key == "k"

    def test_sync_forget(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/api/memories/m1",
            status_code=204,
        )
        result = client.sync_forget("m1")
        assert result is None

    def test_sync_list_memories(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": []})
        result = client.sync_list_memories()
        assert result.items == []

    def test_sync_search_memories(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", json={"items": []})
        result = client.sync_search_memories("query")
        assert result.items == []

    def test_sync_get_memory(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/api/memories/m1",
            json={"memory_id": "m1", "key": "k", "value": "v", "tags": []},
        )
        memory = client.sync_get_memory("m1")
        assert memory.memory_id == "m1"

    def test_sync_recall(self, client: HiveClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            json={"items": [{"memory_id": "m1", "key": "mykey", "value": "val", "tags": []}]},
        )
        memory = client.sync_recall("mykey")
        assert memory is not None
        assert memory.value == "val"
