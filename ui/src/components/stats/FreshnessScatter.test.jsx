// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FreshnessScatter, {
  ScatterTooltipContent,
  formatScatterTooltip,
  isStale,
  openMemory,
} from "./FreshnessScatter.jsx";

// Recharts needs ResizeObserver to mount ResponsiveContainer under jsdom.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

function makePoint(i, overrides = {}) {
  return {
    memory_id: `m${i}`,
    key: `key-${i}`,
    tags: [`t${i}`],
    days_since_created: i * 10,
    days_since_accessed: i * 5,
    ...overrides,
  };
}

const TEN_POINTS = Array.from({ length: 10 }, (_, i) => makePoint(i));

describe("FreshnessScatter", () => {
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

  it("renders the empty-copy when fewer than 10 memories", () => {
    render(<FreshnessScatter data={TEN_POINTS.slice(0, 5)} />);
    expect(
      screen.getByText(/Freshness needs at least 10 memories/),
    ).toBeTruthy();
  });

  it("renders the chart when the data meets the minimum point count", () => {
    const { container } = render(<FreshnessScatter data={TEN_POINTS} />);
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
    // Legend text present as a fallback for colour-blind users.
    expect(screen.getByText(/Stale/)).toBeTruthy();
    expect(screen.getByText(/Active/)).toBeTruthy();
  });

  it("treats missing data as not-enough-points (null-safe)", () => {
    render(<FreshnessScatter />);
    expect(
      screen.getByText(/Freshness needs at least 10 memories/),
    ).toBeTruthy();
  });

  it("isStale flags the upper-right quadrant", () => {
    expect(isStale({ days_since_created: 45, days_since_accessed: 45 })).toBe(true);
    // Exactly at threshold is considered stale (inclusive bound).
    expect(isStale({ days_since_created: 30, days_since_accessed: 30 })).toBe(true);
    // One axis under threshold ⇒ not stale.
    expect(isStale({ days_since_created: 45, days_since_accessed: 10 })).toBe(false);
    expect(isStale({ days_since_created: 10, days_since_accessed: 45 })).toBe(false);
  });

  it("openMemory fires switch-tab first then memory-browser on next tick", () => {
    vi.useFakeTimers();
    openMemory({ key: "key-5" });
    expect(calls.map((e) => e.type)).toEqual(["hive:switch-tab"]);
    vi.runAllTimers();
    expect(calls.map((e) => e.type)).toEqual([
      "hive:switch-tab",
      "hive:memory-browser",
    ]);
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ search: "key-5" });
    const switchEvent = calls.find((e) => e.type === "hive:switch-tab");
    expect(switchEvent.detail).toBe("memories");
    vi.useRealTimers();
  });

  it("openMemory unwraps a Recharts-style payload wrapper", () => {
    vi.useFakeTimers();
    openMemory({ payload: { key: "wrapped" } });
    vi.runAllTimers();
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ search: "wrapped" });
    vi.useRealTimers();
  });

  it("openMemory is a no-op on missing datum / missing key / no dispatcher", () => {
    openMemory(undefined);
    openMemory(null);
    openMemory({});
    openMemory({ key: "" });
    openMemory({ payload: { key: "" } });
    expect(calls).toEqual([]);
    globalThis.dispatchEvent = undefined;
    expect(() => openMemory({ key: "k" })).not.toThrow();
  });

  it("formatScatterTooltip labels the two axes and falls back for unknowns", () => {
    expect(formatScatterTooltip(42, "days_since_created", { payload: { key: "k" } }))
      .toEqual(["42 days old", "k"]);
    expect(formatScatterTooltip(7, "days_since_accessed", { payload: { key: "k" } }))
      .toEqual(["7 days since access", "k"]);
    // Falls back to a bare [value, name] when the series name is unexpected.
    expect(formatScatterTooltip(1, "other", { payload: {} })).toEqual([1, "other"]);
    // Handles a missing entry (no .payload) without crashing.
    expect(formatScatterTooltip(1, "days_since_created")).toEqual(["1 days old", ""]);
    // Exercises the `p.key ?? ""` fallback on the `days_since_accessed`
    // branch — a payload without a key must still produce a [value, ""]
    // tuple rather than `[value, undefined]`.
    expect(formatScatterTooltip(2, "days_since_accessed", { payload: {} }))
      .toEqual(["2 days since access", ""]);
  });

  it("ScatterTooltipContent renders key + tags + counts when active", () => {
    const payload = [
      {
        payload: {
          key: "k",
          tags: ["a", "b"],
          days_since_created: 3,
          days_since_accessed: 1,
        },
      },
    ];
    render(<ScatterTooltipContent active={true} payload={payload} />);
    const body = screen.getByTestId("freshness-tooltip");
    expect(body.textContent).toContain("k");
    expect(body.textContent).toContain("a, b");
    expect(body.textContent).toContain("3 days old");
    expect(body.textContent).toContain("1 days since access");
  });

  it("ScatterTooltipContent omits the tags row when tags is empty", () => {
    const payload = [
      { payload: { key: "k", tags: [], days_since_created: 0, days_since_accessed: 0 } },
    ];
    render(<ScatterTooltipContent active={true} payload={payload} />);
    const body = screen.getByTestId("freshness-tooltip");
    // No comma-separated tag line renders for the empty list.
    expect(body.textContent).not.toContain(",");
  });

  it("ScatterTooltipContent tolerates a payload row with no .payload wrapper", () => {
    // Exercises the `payload[0].payload ?? {}` fallback — recharts can
    // hand us a payload row before it's been hydrated with a datum.
    render(<ScatterTooltipContent active={true} payload={[{}]} />);
    const body = screen.getByTestId("freshness-tooltip");
    // Both axis values render as `undefined days…` but the component
    // must not throw trying to read `.key` / `.tags` off `undefined`.
    expect(body.textContent).toContain("days old");
  });

  it("ScatterTooltipContent returns null when inactive / empty", () => {
    const { container: c1 } = render(<ScatterTooltipContent active={false} payload={[]} />);
    expect(c1.firstChild).toBeNull();
    const { container: c2 } = render(<ScatterTooltipContent active={true} payload={[]} />);
    expect(c2.firstChild).toBeNull();
    const { container: c3 } = render(<ScatterTooltipContent />);
    expect(c3.firstChild).toBeNull();
  });
});
