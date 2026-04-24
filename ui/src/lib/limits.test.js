// Copyright (c) 2026 John Carter. All rights reserved.
import { describe, expect, it } from "vitest";
import { FREE_TIER_MEMORY_LIMIT, FREE_TIER_STORAGE_BYTES_LIMIT, formatBytes } from "./limits.js";

describe("constants", () => {
  it("FREE_TIER_MEMORY_LIMIT is 500", () => {
    expect(FREE_TIER_MEMORY_LIMIT).toBe(500);
  });

  it("FREE_TIER_STORAGE_BYTES_LIMIT is 100 MB", () => {
    expect(FREE_TIER_STORAGE_BYTES_LIMIT).toBe(100 * 1024 * 1024);
  });
});

describe("formatBytes", () => {
  it("returns em dash for null", () => {
    expect(formatBytes(null)).toBe("—");
  });

  it("returns em dash for undefined", () => {
    expect(formatBytes(undefined)).toBe("—");
  });

  it("returns '0 B' for zero", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("returns bytes for small values", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("returns KB for kilobyte values", () => {
    expect(formatBytes(1024)).toBe("1 KB");
  });

  it("returns fractional KB for non-round kilobyte values", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
  });

  it("returns MB for megabyte values", () => {
    expect(formatBytes(1024 * 1024)).toBe("1 MB");
  });

  it("returns GB for gigabyte values", () => {
    expect(formatBytes(1024 * 1024 * 1024)).toBe("1 GB");
  });

  it("caps at GB and does not return TB", () => {
    expect(formatBytes(1024 * 1024 * 1024 * 1024)).toBe("1024 GB");
  });
});
