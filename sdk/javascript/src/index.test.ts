// Copyright (c) 2026 John Carter. All rights reserved.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HiveClient, HiveError } from "./index.js";

const BASE_URL = "https://app.hive-memory.com";
const API_KEY = "hive_sk_test";

describe("HiveClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockOk(body: unknown, status = 200) {
    fetchMock.mockResolvedValue({
      ok: true,
      status,
      statusText: "OK",
      json: () => Promise.resolve(body),
    });
  }

  function mockErr(detail: string | undefined, status = 400) {
    fetchMock.mockResolvedValue({
      ok: false,
      status,
      statusText: "Bad Request",
      json: () =>
        Promise.resolve(detail !== undefined ? { detail } : {}),
    });
  }

  function client() {
    return new HiveClient({ apiKey: API_KEY, baseUrl: BASE_URL });
  }

  // ------------------------------------------------------------------ //
  // Auth header                                                          //
  // ------------------------------------------------------------------ //

  it("sends Authorization header on every request", async () => {
    mockOk({ items: [] });
    await client().listMemories();
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${API_KEY}`);
  });

  // ------------------------------------------------------------------ //
  // remember                                                             //
  // ------------------------------------------------------------------ //

  it("remember sends POST /api/memories with key, value, tags", async () => {
    mockOk({ memory_id: "m1", key: "k", value: "v", tags: [] });
    const memory = await client().remember("k", "v");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(memory.key).toBe("k");
  });

  it("remember sends ttl_seconds when provided", async () => {
    mockOk({ memory_id: "m1", key: "k", value: "v", tags: [] });
    await client().remember("k", "v", { ttlSeconds: 3600 });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.ttl_seconds).toBe(3600);
  });

  it("remember does not include ttl_seconds when not provided", async () => {
    mockOk({ memory_id: "m1", key: "k", value: "v", tags: [] });
    await client().remember("k", "v");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.ttl_seconds).toBeUndefined();
  });

  it("remember throws HiveError on failure", async () => {
    mockErr("Value too large", 422);
    await expect(client().remember("k", "v")).rejects.toThrow(HiveError);
    await expect(client().remember("k", "v")).rejects.toThrow("422");
  });

  // ------------------------------------------------------------------ //
  // getMemory                                                            //
  // ------------------------------------------------------------------ //

  it("getMemory sends GET /api/memories/{id}", async () => {
    mockOk({ memory_id: "m1", key: "k", value: "v", tags: [] });
    const memory = await client().getMemory("m1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/m1");
    expect(memory.memory_id).toBe("m1");
  });

  it("getMemory throws on 404", async () => {
    mockErr("Memory not found", 404);
    await expect(client().getMemory("nope")).rejects.toThrow(HiveError);
  });

  // ------------------------------------------------------------------ //
  // forget                                                               //
  // ------------------------------------------------------------------ //

  it("forget sends DELETE /api/memories/{id}", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await client().forget("m1");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/m1");
  });

  // ------------------------------------------------------------------ //
  // listMemories                                                         //
  // ------------------------------------------------------------------ //

  it("listMemories sends GET /api/memories with default limit", async () => {
    mockOk({ items: [] });
    await client().listMemories();
    expect(fetchMock.mock.calls[0][0]).toContain("limit=50");
  });

  it("listMemories sends tag param", async () => {
    mockOk({ items: [] });
    await client().listMemories({ tag: "mytag" });
    expect(fetchMock.mock.calls[0][0]).toContain("tag=mytag");
  });

  it("listMemories sends cursor param", async () => {
    mockOk({ items: [] });
    await client().listMemories({ cursor: "tok123" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=tok123");
  });

  it("listMemories returns items", async () => {
    mockOk({ items: [{ memory_id: "m1", key: "k", value: "v", tags: [] }] });
    const result = await client().listMemories();
    expect(result.items).toHaveLength(1);
    expect(result.items[0].key).toBe("k");
  });

  // ------------------------------------------------------------------ //
  // searchMemories                                                       //
  // ------------------------------------------------------------------ //

  it("searchMemories sends search param", async () => {
    mockOk({ items: [] });
    await client().searchMemories("hello world");
    expect(fetchMock.mock.calls[0][0]).toContain("search=hello+world");
  });

  // ------------------------------------------------------------------ //
  // recall                                                               //
  // ------------------------------------------------------------------ //

  it("recall finds matching key in list", async () => {
    mockOk({
      items: [
        { memory_id: "m1", key: "target", value: "found", tags: [] },
        { memory_id: "m2", key: "other", value: "other-val", tags: [] },
      ],
    });
    const memory = await client().recall("target");
    expect(memory).not.toBeNull();
    expect(memory!.value).toBe("found");
  });

  it("recall returns null when not found", async () => {
    mockOk({ items: [] });
    const memory = await client().recall("missing");
    expect(memory).toBeNull();
  });

  // ------------------------------------------------------------------ //
  // Error handling                                                       //
  // ------------------------------------------------------------------ //

  it("throws HiveError with detail when error json has detail", async () => {
    mockErr("Something bad", 400);
    await expect(client().listMemories()).rejects.toThrow("Something bad");
  });

  it("falls back to statusText when error json has no detail", async () => {
    mockErr(undefined, 500);
    await expect(client().listMemories()).rejects.toThrow(HiveError);
  });

  it("handles unparseable error body gracefully", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      json: () => Promise.reject(new Error("parse fail")),
    });
    await expect(client().listMemories()).rejects.toThrow(HiveError);
  });

  // ------------------------------------------------------------------ //
  // trailing slash normalisation                                         //
  // ------------------------------------------------------------------ //

  it("trims trailing slash from baseUrl", async () => {
    mockOk({ items: [] });
    const c = new HiveClient({ apiKey: API_KEY, baseUrl: `${BASE_URL}/` });
    await c.listMemories();
    expect(fetchMock.mock.calls[0][0]).not.toContain("//api");
  });
});
