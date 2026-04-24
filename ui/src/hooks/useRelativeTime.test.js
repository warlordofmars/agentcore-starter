// Copyright (c) 2026 John Carter. All rights reserved.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatRelativeTime, useRelativeTime } from "./useRelativeTime.js";

// ---------------------------------------------------------------------------
// formatRelativeTime — pure formatting logic
// ---------------------------------------------------------------------------

describe("formatRelativeTime", () => {
  it("returns null for null input", () => {
    expect(formatRelativeTime(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(formatRelativeTime(undefined)).toBeNull();
  });

  it("returns 'just now' for < 60 seconds ago", () => {
    const date = new Date(Date.now() - 30_000);
    expect(formatRelativeTime(date)).toBe("just now");
  });

  it("returns '1 min ago' for exactly 60 seconds ago", () => {
    const date = new Date(Date.now() - 60_000);
    expect(formatRelativeTime(date)).toBe("1 min ago");
  });

  it("returns '5 mins ago' for 5 minutes ago", () => {
    const date = new Date(Date.now() - 5 * 60_000);
    expect(formatRelativeTime(date)).toBe("5 mins ago");
  });

  it("returns '1 hour ago' for exactly 60 minutes ago", () => {
    const date = new Date(Date.now() - 60 * 60_000);
    expect(formatRelativeTime(date)).toBe("1 hour ago");
  });

  it("returns '3 hours ago' for 3 hours ago", () => {
    const date = new Date(Date.now() - 3 * 60 * 60_000);
    expect(formatRelativeTime(date)).toBe("3 hours ago");
  });

  it("returns '1 day ago' for exactly 24 hours ago", () => {
    const date = new Date(Date.now() - 24 * 60 * 60_000);
    expect(formatRelativeTime(date)).toBe("1 day ago");
  });

  it("returns '3 days ago' for 3 days ago", () => {
    const date = new Date(Date.now() - 3 * 24 * 60 * 60_000);
    expect(formatRelativeTime(date)).toBe("3 days ago");
  });
});

// ---------------------------------------------------------------------------
// useRelativeTime — hook behaviour
// ---------------------------------------------------------------------------

describe("useRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null when date is null", () => {
    const { result } = renderHook(() => useRelativeTime(null));
    expect(result.current).toBeNull();
  });

  it("returns relative string for a given date", () => {
    const date = new Date(Date.now() - 10_000);
    const { result } = renderHook(() => useRelativeTime(date));
    expect(result.current).toBe("just now");
  });

  it("re-renders after 30 seconds to update the relative string", async () => {
    // Start 50 seconds ago → "just now"
    const date = new Date(Date.now() - 50_000);
    const { result } = renderHook(() => useRelativeTime(date));
    expect(result.current).toBe("just now");

    // Advance 30 s — now 80 s ago → "1 min ago"
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    expect(result.current).toBe("1 min ago");
  });

  it("clears interval on unmount", () => {
    const clearSpy = vi.spyOn(globalThis, "clearInterval");
    const date = new Date(Date.now() - 10_000);
    const { unmount } = renderHook(() => useRelativeTime(date));
    unmount();
    expect(clearSpy).toHaveBeenCalled();
  });

  it("does not set interval when date is null", () => {
    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
    renderHook(() => useRelativeTime(null));
    expect(setIntervalSpy).not.toHaveBeenCalled();
  });
});
