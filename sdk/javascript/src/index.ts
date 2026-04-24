// Copyright (c) 2026 John Carter. All rights reserved.
/**
 * Hive client SDK — JavaScript/TypeScript client for the Hive memory API.
 */

const DEFAULT_BASE_URL = "https://app.hive-memory.com";

export interface Memory {
  memory_id: string;
  key: string;
  value: string;
  tags: string[];
  created_at?: string;
  updated_at?: string;
  expires_at?: string;
}

export interface MemoryList {
  items: Memory[];
  next_cursor?: string;
}

export interface HiveClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
}

export class HiveError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly detail: string
  ) {
    super(`HTTP ${statusCode}: ${detail}`);
    this.name = "HiveError";
  }
}

export class HiveClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;

  constructor(options: HiveClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
  }

  private headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
    };
  }

  private async request<T>(
    method: string,
    path: string,
    options: { params?: Record<string, string | number>; body?: unknown } = {}
  ): Promise<T | null> {
    let url = `${this.baseUrl}${path}`;
    if (options.params) {
      const qs = new URLSearchParams(
        Object.entries(options.params).map(([k, v]) => [k, String(v)])
      ).toString();
      if (qs) url += `?${qs}`;
    }

    const resp = await fetch(url, {
      method,
      headers: this.headers(),
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });

    if (resp.status === 204) return null;

    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = {};
    }

    if (!resp.ok) {
      const detail =
        typeof body === "object" && body !== null && "detail" in body
          ? String((body as Record<string, unknown>).detail)
          : resp.statusText;
      throw new HiveError(resp.status, detail);
    }

    return body as T;
  }

  /** Store or update a memory. */
  async remember(
    key: string,
    value: string,
    options: { tags?: string[]; ttlSeconds?: number } = {}
  ): Promise<Memory> {
    const body: Record<string, unknown> = {
      key,
      value,
      tags: options.tags ?? [],
    };
    if (options.ttlSeconds !== undefined) {
      body.ttl_seconds = options.ttlSeconds;
    }
    const result = await this.request<Memory>("POST", "/api/memories", { body });
    return result as Memory;
  }

  /** Retrieve a memory by key (returns null if not found). */
  async recall(key: string): Promise<Memory | null> {
    const list = await this.listMemories();
    return list.items.find((m) => m.key === key) ?? null;
  }

  /** Retrieve a memory by ID. */
  async getMemory(memoryId: string): Promise<Memory> {
    const result = await this.request<Memory>("GET", `/api/memories/${memoryId}`);
    return result as Memory;
  }

  /** Delete a memory by ID. */
  async forget(memoryId: string): Promise<void> {
    await this.request<null>("DELETE", `/api/memories/${memoryId}`);
  }

  /** List memories, optionally filtered by tag. */
  async listMemories(options: {
    tag?: string;
    limit?: number;
    cursor?: string;
  } = {}): Promise<MemoryList> {
    const params: Record<string, string | number> = {
      limit: options.limit ?? 50,
    };
    if (options.tag) params.tag = options.tag;
    if (options.cursor) params.cursor = options.cursor;
    const result = await this.request<MemoryList>("GET", "/api/memories", { params });
    return result as MemoryList;
  }

  /** Semantic search across memories. */
  async searchMemories(query: string, options: { limit?: number } = {}): Promise<MemoryList> {
    const params: Record<string, string | number> = {
      search: query,
      limit: options.limit ?? 50,
    };
    const result = await this.request<MemoryList>("GET", "/api/memories", { params });
    return result as MemoryList;
  }
}
