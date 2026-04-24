// Copyright (c) 2026 John Carter. All rights reserved.
/**
 * Hive API client — thin wrapper around fetch.
 * Token is read from localStorage.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "";

function getToken() {
  return localStorage.getItem("hive_mgmt_token") ?? "";
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    localStorage.removeItem("hive_mgmt_token");
    globalThis.location.replace("/");
    return null;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    // Attach the HTTP status so callers can branch on 429 (quota / rate
    // limit) without scraping the message — generic JS Error has no
    // status field of its own.
    const message = err.detail ?? "Request failed";
    const wrapped = new Error(message);
    wrapped.status = res.status;
    throw wrapped;
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Memories
  listMemories: (tag, { limit = 50, cursor } = {}) => {
    const params = new URLSearchParams();
    if (tag) params.set("tag", tag);
    params.set("limit", limit);
    if (cursor) params.set("cursor", cursor);
    return request("GET", `/api/memories?${params}`);
  },
  searchMemories: (query, { limit = 50 } = {}) => {
    const params = new URLSearchParams({ search: query, limit });
    return request("GET", `/api/memories?${params}`);
  },
  getMemory: (id) => request("GET", `/api/memories/${id}`),
  createMemory: (body) => request("POST", "/api/memories", body),
  updateMemory: (id, body) => request("PATCH", `/api/memories/${id}`, body),
  deleteMemory: (id) => request("DELETE", `/api/memories/${id}`),
  listMemoryVersions: (id) => request("GET", `/api/memories/${id}/versions`),
  restoreMemoryVersion: (id, versionTimestamp) =>
    request("POST", `/api/memories/${id}/restore?version_timestamp=${encodeURIComponent(versionTimestamp)}`),
  getMemoryContent: async (id) => {
    const token = getToken();
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${BASE}/api/memories/${id}/content`, { headers });
    if (res.status === 401) {
      localStorage.removeItem("hive_mgmt_token");
      globalThis.location.replace("/");
      return null;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Failed to fetch content");
    }
    return res.blob();
  },

  // Clients
  listClients: ({ limit = 50, cursor } = {}) => {
    const params = new URLSearchParams({ limit });
    if (cursor) params.set("cursor", cursor);
    return request("GET", `/api/clients?${params}`);
  },
  getClient: (id) => request("GET", `/api/clients/${id}`),
  createClient: (body) => request("POST", "/api/clients", body),
  deleteClient: (id) => request("DELETE", `/api/clients/${id}`),

  // Stats & Activity
  getStats: () => request("GET", "/api/stats"),
  getActivity: (days = 7, { limit = 100 } = {}) =>
    request("GET", `/api/activity?days=${days}&limit=${limit}`),
  getAccountStats: (windowDays = 90) =>
    request("GET", `/api/account/stats?window=${windowDays}`),

  // Admin
  getMetrics: (period = "24h") => request("GET", `/api/admin/metrics?period=${period}`),
  getCosts: () => request("GET", "/api/admin/costs"),
  getAlarms: () => request("GET", "/api/admin/alarms"),
  getLogs: ({ group = "all", window = "1h", filter = "", nextToken } = {}) => {
    const params = new URLSearchParams({ group, window });
    if (filter) params.set("filter", filter);
    if (nextToken) params.set("next_token", nextToken);
    return request("GET", `/api/admin/logs?${params}`);
  },

  // Users
  getMe: () => request("GET", "/api/users/me"),
  listUsers: ({ limit = 50, cursor } = {}) => {
    const params = new URLSearchParams({ limit });
    if (cursor) params.set("cursor", cursor);
    return request("GET", `/api/users?${params}`);
  },
  updateUserRole: (id, role) => request("PATCH", `/api/users/${id}`, { role }),
  getUserStats: (id) => request("GET", `/api/users/${id}/stats`),
  getUserLimits: (id) => request("GET", `/api/users/${id}/limits`),
  updateUserLimits: (id, body) => request("PUT", `/api/users/${id}/limits`, body),
  deleteUser: (id) => request("DELETE", `/api/users/${id}`),

  // API Keys
  listApiKeys: () => request("GET", "/api/keys"),
  createApiKey: (name, scope) => request("POST", "/api/keys", { name, scope }),
  deleteApiKey: (id) => request("DELETE", `/api/keys/${id}`),

  // Account
  deleteAccount: () => request("DELETE", "/api/account", { confirm: true }),
  exportAccount: async () => {
    const token = getToken();
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${BASE}/api/account/export`, { headers });
    if (res.status === 401) {
      localStorage.removeItem("hive_mgmt_token");
      globalThis.location.replace("/");
      return null;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Export failed");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : "hive-export.json";
    return { blob, filename };
  },
};
