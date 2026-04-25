// Copyright (c) 2026 John Carter. All rights reserved.
import { describe, expect, it } from "vitest";
import { formatBytes } from "./limits.js";

describe("formatBytes", () => {
  it("returns em dash for null", () => {
    expect(formatBytes(null)).toBe("—");
  });

  it("returns em dash for undefined", () => {
    expect(formatBytes(undefined)).toBe("—");
  });

  it("returns 0 B for zero", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("formats bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("formats kilobytes", () => {
    expect(formatBytes(1024)).toBe("1.0 KB");
  });

  it("formats megabytes", () => {
    expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
  });

  it("formats gigabytes", () => {
    expect(formatBytes(1024 * 1024 * 1024)).toBe("1.0 GB");
  });

  it("caps at terabytes", () => {
    expect(formatBytes(1024 ** 4)).toBe("1.0 TB");
    // Beyond TB still uses TB
    expect(formatBytes(1024 ** 5)).toBe("1024.0 TB");
  });
});
