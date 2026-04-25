// Copyright (c) 2026 John Carter. All rights reserved.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api.js";

describe("api", () => {
  let fetchMock;

  let storage;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => storage[k] ?? null,
      setItem: (k, v) => { storage[k] = v; },
      removeItem: (k) => { delete storage[k]; },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockOk(body, status = 200) {
    fetchMock.mockResolvedValue({
      ok: true,
      status,
      json: () => Promise.resolve(body),
    });
  }

  function mockErr(detail, status = 400) {
    fetchMock.mockResolvedValue({
      ok: false,
      status,
      statusText: "Bad Request",
      json: () => Promise.resolve(detail !== undefined ? { detail } : {}),
    });
  }

  // ---------------------------------------------------------------------------
  // request() core behaviour
  // ---------------------------------------------------------------------------

  it("adds Authorization header when token is in localStorage", async () => {
    localStorage.setItem("starter_mgmt_token", "tok123");
    mockOk({ items: [] });
    await api.listMemories();
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer tok123");
  });

  it("omits Authorization header when no token", async () => {
    mockOk({ items: [] });
    await api.listMemories();
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("sends JSON body on POST requests", async () => {
    mockOk({ memory_id: "1", key: "k", value: "v", tags: [] });
    await api.createMemory({ key: "k", value: "v", tags: [] });
    const call = fetchMock.mock.calls[0];
    expect(call[1].method).toBe("POST");
    expect(call[1].body).toBe(JSON.stringify({ key: "k", value: "v", tags: [] }));
  });

  it("omits body on GET requests", async () => {
    mockOk({ items: [] });
    await api.listMemories();
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined();
  });

  it("throws error with detail on non-ok response", async () => {
    mockErr("Something bad");
    await expect(api.listMemories()).rejects.toThrow("Something bad");
  });

  it("attaches the HTTP status to the thrown error so callers can branch on 429", async () => {
    mockErr("Memory quota exceeded.", 429);
    try {
      await api.createMemory({ key: "k", value: "v", tags: [] });
      throw new Error("should have thrown");
    } catch (err) {
      expect(err.message).toBe("Memory quota exceeded.");
      expect(err.status).toBe(429);
    }
  });

  it("falls back to statusText when error json has no detail", async () => {
    mockErr(undefined);
    await expect(api.listMemories()).rejects.toThrow("Request failed");
  });

  it("falls back to statusText when error json parse fails", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("parse fail")),
    });
    await expect(api.listMemories()).rejects.toThrow("Internal Server Error");
  });

  it("returns null on 204 response", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    const result = await api.deleteMemory("id1");
    expect(result).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // listMemories
  // ---------------------------------------------------------------------------

  it("listMemories without tag or cursor", async () => {
    mockOk({ items: [] });
    await api.listMemories();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/memories\?limit=50/);
    expect(fetchMock.mock.calls[0][0]).not.toContain("tag=");
    expect(fetchMock.mock.calls[0][0]).not.toContain("cursor=");
  });

  it("listMemories with tag", async () => {
    mockOk({ items: [] });
    await api.listMemories("mytag");
    expect(fetchMock.mock.calls[0][0]).toContain("tag=mytag");
  });

  it("listMemories with cursor", async () => {
    mockOk({ items: [] });
    await api.listMemories(undefined, { cursor: "abc123" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=abc123");
  });

  it("listMemories with custom limit", async () => {
    mockOk({ items: [] });
    await api.listMemories(undefined, { limit: 10 });
    expect(fetchMock.mock.calls[0][0]).toContain("limit=10");
  });

  it("searchMemories passes search param", async () => {
    mockOk({ items: [], count: 0 });
    await api.searchMemories("hello world");
    expect(fetchMock.mock.calls[0][0]).toContain("search=hello+world");
    expect(fetchMock.mock.calls[0][0]).toContain("limit=50");
  });

  it("searchMemories with custom limit", async () => {
    mockOk({ items: [], count: 0 });
    await api.searchMemories("q", { limit: 10 });
    expect(fetchMock.mock.calls[0][0]).toContain("limit=10");
  });

  // ---------------------------------------------------------------------------
  // Memory CRUD
  // ---------------------------------------------------------------------------

  it("getMemory calls correct endpoint", async () => {
    mockOk({ memory_id: "m1" });
    await api.getMemory("m1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/m1");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("updateMemory sends PATCH with body", async () => {
    mockOk({ memory_id: "m1", value: "new" });
    await api.updateMemory("m1", { value: "new" });
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain("/api/memories/m1");
    expect(call[1].method).toBe("PATCH");
    expect(JSON.parse(call[1].body)).toEqual({ value: "new" });
  });

  it("deleteMemory calls DELETE", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await api.deleteMemory("m2");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/m2");
  });

  // ---------------------------------------------------------------------------
  // listClients
  // ---------------------------------------------------------------------------

  it("listClients without cursor", async () => {
    mockOk({ items: [] });
    await api.listClients();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/clients");
    expect(fetchMock.mock.calls[0][0]).not.toContain("cursor=");
  });

  it("listClients with cursor", async () => {
    mockOk({ items: [] });
    await api.listClients({ cursor: "tok" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=tok");
  });

  // ---------------------------------------------------------------------------
  // Client CRUD
  // ---------------------------------------------------------------------------

  it("getClient calls correct endpoint", async () => {
    mockOk({ client_id: "c1" });
    await api.getClient("c1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/clients/c1");
  });

  it("createClient sends POST with body", async () => {
    mockOk({ client_id: "c1" });
    await api.createClient({ client_name: "App" });
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ client_name: "App" });
  });

  it("deleteClient calls DELETE", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await api.deleteClient("c2");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/clients/c2");
  });

  // ---------------------------------------------------------------------------
  // Stats & Activity
  // ---------------------------------------------------------------------------

  it("getStats calls /api/stats", async () => {
    mockOk({ total_memories: 5 });
    await api.getStats();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/stats");
  });

  it("getAccountStats passes window through", async () => {
    mockOk({ window_days: 30 });
    await api.getAccountStats(30);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/account/stats?window=30");
  });

  it("getAccountStats defaults to 90-day window", async () => {
    mockOk({ window_days: 90 });
    await api.getAccountStats();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/account/stats?window=90");
  });

  it("getActivity with default params", async () => {
    mockOk({ items: [] });
    await api.getActivity();
    expect(fetchMock.mock.calls[0][0]).toContain("days=7");
    expect(fetchMock.mock.calls[0][0]).toContain("limit=100");
  });

  it("getActivity with custom params", async () => {
    mockOk({ items: [] });
    await api.getActivity(30, { limit: 50 });
    expect(fetchMock.mock.calls[0][0]).toContain("days=30");
    expect(fetchMock.mock.calls[0][0]).toContain("limit=50");
  });

  // ---------------------------------------------------------------------------
  // Users
  // ---------------------------------------------------------------------------

  it("getMe calls /api/users/me", async () => {
    mockOk({ user_id: "u1", email: "u@example.com", role: "user" });
    await api.getMe();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/me");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("listUsers calls /api/users", async () => {
    mockOk({ items: [] });
    await api.listUsers();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users");
    expect(fetchMock.mock.calls[0][0]).not.toContain("/me");
  });

  it("listUsers passes cursor when provided", async () => {
    mockOk({ items: [] });
    await api.listUsers({ cursor: "c123" });
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=c123");
  });

  it("deleteUser calls DELETE /api/users/{id}", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await api.deleteUser("u99");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/u99");
  });

  it("updateUserRole calls PATCH /api/users/{id}", async () => {
    mockOk({ user_id: "u1", role: "admin" });
    await api.updateUserRole("u1", "admin");
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/u1");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ role: "admin" });
  });

  it("getUserStats calls GET /api/users/{id}/stats", async () => {
    mockOk({ user_id: "u1", memory_count: 3, client_count: 1 });
    await api.getUserStats("u1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/u1/stats");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("getUserLimits calls GET /api/users/{id}/limits", async () => {
    mockOk({ user_id: "u1", memory_limit: null, storage_bytes_limit: null, effective_memory_limit: 500, effective_storage_bytes_limit: 104857600 });
    await api.getUserLimits("u1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/u1/limits");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("updateUserLimits calls PUT /api/users/{id}/limits with body", async () => {
    mockOk({ user_id: "u1", memory_limit: 100, storage_bytes_limit: null, effective_memory_limit: 100, effective_storage_bytes_limit: 104857600 });
    await api.updateUserLimits("u1", { memory_limit: 100, storage_bytes_limit: null });
    expect(fetchMock.mock.calls[0][0]).toContain("/api/users/u1/limits");
    expect(fetchMock.mock.calls[0][1].method).toBe("PUT");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ memory_limit: 100, storage_bytes_limit: null });
  });

  it("listApiKeys calls GET /api/keys", async () => {
    mockOk([]);
    await api.listApiKeys();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/keys");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("createApiKey calls POST /api/keys with name and scope", async () => {
    mockOk({ key_id: "k1", plaintext_key: "starter_sk_abc" });
    await api.createApiKey("My Key", "memories:read");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/keys");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ name: "My Key", scope: "memories:read" });
  });

  it("deleteApiKey calls DELETE /api/keys/{id}", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await api.deleteApiKey("k1");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/keys/k1");
  });

  it("deleteAccount calls DELETE /api/account with confirm body", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 204 });
    await api.deleteAccount();
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/account");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ confirm: true });
  });

  // ---------------------------------------------------------------------------
  // Admin
  // ---------------------------------------------------------------------------

  it("getMetrics calls GET /api/admin/metrics with default period", async () => {
    mockOk({ period: "24h", metrics: {} });
    await api.getMetrics();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/admin/metrics?period=24h");
  });

  it("getMetrics passes custom period", async () => {
    mockOk({ period: "7d", metrics: {} });
    await api.getMetrics("7d");
    expect(fetchMock.mock.calls[0][0]).toContain("period=7d");
  });

  it("getCosts calls GET /api/admin/costs", async () => {
    mockOk({ monthly: [] });
    await api.getCosts();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/admin/costs");
  });

  it("getAlarms calls GET /api/admin/alarms", async () => {
    mockOk({ alarms: [] });
    await api.getAlarms();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/admin/alarms");
  });

  it("getLogs with defaults calls correct endpoint", async () => {
    mockOk({ events: [], next_token: null });
    await api.getLogs();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/admin/logs");
    expect(fetchMock.mock.calls[0][0]).toContain("group=all");
    expect(fetchMock.mock.calls[0][0]).toContain("window=1h");
  });

  it("getLogs with filter appends filter param", async () => {
    mockOk({ events: [], next_token: null });
    await api.getLogs({ group: "mcp", window: "3h", filter: "ERROR" });
    expect(fetchMock.mock.calls[0][0]).toContain("filter=ERROR");
  });

  it("getLogs omits filter when empty", async () => {
    mockOk({ events: [], next_token: null });
    await api.getLogs({ group: "mcp", window: "1h", filter: "" });
    expect(fetchMock.mock.calls[0][0]).not.toContain("filter=");
  });

  it("getLogs with nextToken appends next_token param", async () => {
    mockOk({ events: [], next_token: null });
    await api.getLogs({ nextToken: "tok123" });
    expect(fetchMock.mock.calls[0][0]).toContain("next_token=tok123");
  });

  // ---------------------------------------------------------------------------
  // Version history endpoints
  // ---------------------------------------------------------------------------

  it("listMemoryVersions calls correct URL", async () => {
    mockOk([]);
    await api.listMemoryVersions("mem-123");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/mem-123/versions");
  });

  it("restoreMemoryVersion calls correct URL with encoded timestamp", async () => {
    mockOk({});
    await api.restoreMemoryVersion("mem-123", "20260412T120000");
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/api/memories/mem-123/restore?version_timestamp=20260412T120000",
    );
  });

  // ---------------------------------------------------------------------------
  // 401 handling — clears token and redirects
  // ---------------------------------------------------------------------------

  it("401 response clears mgmt token and redirects to /", async () => {
    storage["starter_mgmt_token"] = "old-token";
    vi.stubGlobal("location", { replace: vi.fn() });
    fetchMock.mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve({}) });
    const result = await api.getStats();
    expect(result).toBeNull();
    expect(storage["starter_mgmt_token"]).toBeUndefined();
    expect(window.location.replace).toHaveBeenCalledWith("/");
  });

  // ---------------------------------------------------------------------------
  // exportAccount
  // ---------------------------------------------------------------------------

  function mockExportResponse({
    ok = true,
    status = 200,
    blob = new Blob(),
    disposition,
    body,
  } = {}) {
    fetchMock.mockResolvedValue({
      ok,
      status,
      statusText: "Error",
      blob: () => Promise.resolve(blob),
      json: () => Promise.resolve(body ?? {}),
      headers: { get: () => disposition ?? null },
    });
  }

  it("exportAccount sends Authorization header when token present", async () => {
    storage["starter_mgmt_token"] = "user-token";
    mockExportResponse({ disposition: 'attachment; filename="agentcore-starter-export.json"' });
    await api.exportAccount();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/account/export");
    expect(opts.headers.Authorization).toBe("Bearer user-token");
  });

  it("exportAccount omits Authorization when no token is stored", async () => {
    mockExportResponse({ disposition: 'attachment; filename="x.json"' });
    await api.exportAccount();
    const opts = fetchMock.mock.calls[0][1];
    expect(opts.headers.Authorization).toBeUndefined();
  });

  it("exportAccount returns blob + filename parsed from Content-Disposition", async () => {
    const blob = new Blob(["{}"], { type: "application/json" });
    mockExportResponse({
      blob,
      disposition: 'attachment; filename="agentcore-starter-export-user-20260418.json"',
    });
    const result = await api.exportAccount();
    expect(result.blob).toBe(blob);
    expect(result.filename).toBe("agentcore-starter-export-user-20260418.json");
  });

  it("exportAccount falls back to a default filename when disposition is missing", async () => {
    mockExportResponse({ disposition: null });
    const result = await api.exportAccount();
    expect(result.filename).toBe("agentcore-starter-export.json");
  });

  it("exportAccount surfaces error detail from JSON body on non-OK responses", async () => {
    mockExportResponse({
      ok: false,
      status: 429,
      body: { detail: "Exports are limited to one per 5 minutes." },
    });
    await expect(api.exportAccount()).rejects.toThrow(
      "Exports are limited to one per 5 minutes.",
    );
  });

  it("exportAccount falls back to statusText when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
      json: () => Promise.reject(new Error("not json")),
      headers: { get: () => null },
    });
    await expect(api.exportAccount()).rejects.toThrow("Server Error");
  });

  it("exportAccount surfaces generic 'Request failed' when error body is an empty object", async () => {
    mockExportResponse({ ok: false, status: 500, body: {} });
    await expect(api.exportAccount()).rejects.toThrow("Export failed");
  });

  it("exportAccount clears token and redirects on 401", async () => {
    storage["starter_mgmt_token"] = "old-token";
    const replace = vi.fn();
    vi.stubGlobal("location", { replace });
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      headers: { get: () => null },
      blob: () => Promise.resolve(new Blob()),
      json: () => Promise.resolve({}),
    });
    const result = await api.exportAccount();
    expect(result).toBeNull();
    expect(storage["starter_mgmt_token"]).toBeUndefined();
    expect(replace).toHaveBeenCalledWith("/");
  });

  // ---------------------------------------------------------------------------
  // getMemoryContent
  // ---------------------------------------------------------------------------

  it("getMemoryContent fetches memory content and returns blob", async () => {
    const blob = new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" });
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      blob: () => Promise.resolve(blob),
    });
    const result = await api.getMemoryContent("mem-abc");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/memories/mem-abc/content");
    expect(result).toBe(blob);
  });

  it("getMemoryContent sends Authorization header when token present", async () => {
    storage["starter_mgmt_token"] = "user-token";
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      blob: () => Promise.resolve(new Blob()),
    });
    await api.getMemoryContent("mem-abc");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer user-token");
  });

  it("getMemoryContent throws on non-ok response with detail", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: () => Promise.resolve({ detail: "Memory has no S3 content" }),
    });
    await expect(api.getMemoryContent("mem-abc")).rejects.toThrow("Memory has no S3 content");
  });

  it("getMemoryContent throws fallback message when json has no detail field", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
      json: () => Promise.resolve({}),
    });
    await expect(api.getMemoryContent("mem-abc")).rejects.toThrow("Failed to fetch content");
  });

  it("getMemoryContent throws generic message when json parse fails", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
      json: () => Promise.reject(new Error("bad json")),
    });
    await expect(api.getMemoryContent("mem-abc")).rejects.toThrow("Server Error");
  });

  it("getMemoryContent clears token and redirects on 401", async () => {
    storage["starter_mgmt_token"] = "old-token";
    const replace = vi.fn();
    vi.stubGlobal("location", { replace });
    fetchMock.mockResolvedValue({ ok: false, status: 401 });
    const result = await api.getMemoryContent("mem-abc");
    expect(result).toBeNull();
    expect(storage["starter_mgmt_token"]).toBeUndefined();
    expect(replace).toHaveBeenCalledWith("/");
  });
});
