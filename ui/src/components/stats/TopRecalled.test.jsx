// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TopRecalled, { formatRecallTooltip, openMemory } from "./TopRecalled.jsx";

// Recharts uses ResponsiveContainer which needs ResizeObserver in jsdom.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const _data = [
  { memory_id: "m1", key: "top-key", recall_count: 10 },
  { memory_id: "m2", key: "next-key", recall_count: 4 },
];

describe("TopRecalled", () => {
  let originalDispatch;
  let calls;

  beforeEach(() => {
    originalDispatch = globalThis.dispatchEvent;
    calls = [];
    globalThis.dispatchEvent = (e) => {
      calls.push(e);
      return true;
    };
  });

  afterEach(() => {
    globalThis.dispatchEvent = originalDispatch;
  });

  it("renders a chart container when data is present", () => {
    const { container } = render(<TopRecalled data={_data} />);
    // Empty handling is the GraphCard parent's job; this component
    // assumes at least one bar to draw.
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("openMemory dispatches switch-tab first, then memory-browser on next tick", () => {
    vi.useFakeTimers();
    openMemory({ memory_id: "m1", key: "top-key", recall_count: 10 });
    // Before the timer flushes, only the tab-switch has dispatched — so
    // MemoryBrowser has a chance to mount + attach its listener.
    expect(calls.map((e) => e.type)).toEqual(["hive:switch-tab"]);
    vi.runAllTimers();
    const types = calls.map((e) => e.type);
    expect(types).toEqual(["hive:switch-tab", "hive:memory-browser"]);
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ search: "top-key" });
    const switchEvent = calls.find((e) => e.type === "hive:switch-tab");
    expect(switchEvent.detail).toBe("memories");
    vi.useRealTimers();
  });

  it("openMemory is a no-op without a dispatchEvent global", () => {
    globalThis.dispatchEvent = undefined;
    // Should not throw.
    expect(() => openMemory({ memory_id: "m1", key: "k", recall_count: 1 })).not.toThrow();
  });

  it("openMemory is a no-op when the datum is missing / lacks a key", () => {
    // Recharts wrappers with no payload, or payloads without a key, must
    // not dispatch — covers the early-return guard.
    openMemory(undefined);
    openMemory(null);
    openMemory({});
    openMemory({ key: "" });
    openMemory({ payload: { key: "" } });
    expect(calls).toEqual([]);
  });

  it("formatRecallTooltip labels the value with 'recalls'", () => {
    expect(formatRecallTooltip(7)).toEqual(["7 recalls", ""]);
  });

  it("openMemory unwraps a Recharts-style payload wrapper", () => {
    vi.useFakeTimers();
    openMemory({ payload: { memory_id: "m2", key: "wrapped-key", recall_count: 3 } });
    vi.runAllTimers();
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ search: "wrapped-key" });
    vi.useRealTimers();
  });
});
