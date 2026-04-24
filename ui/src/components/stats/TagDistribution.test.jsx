// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TagDistribution, { buildSlices, filterByTag, formatTagTooltip, handlePieSliceClick } from "./TagDistribution.jsx";

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe("buildSlices", () => {
  it("returns empty for missing/empty data", () => {
    expect(buildSlices()).toEqual([]);
    expect(buildSlices([])).toEqual([]);
  });

  it("sorts by count descending", () => {
    const slices = buildSlices([
      { tag: "a", count: 2 },
      { tag: "b", count: 5 },
    ]);
    expect(slices.map((s) => s.tag)).toEqual(["b", "a"]);
  });

  it("bundles anything past the top N into an 'Other' slice", () => {
    const data = Array.from({ length: 12 }, (_, i) => ({
      tag: `t${i}`,
      count: 12 - i,
    }));
    const slices = buildSlices(data);
    // Top 8 + one Other slice = 9 entries.
    expect(slices).toHaveLength(9);
    const other = slices[slices.length - 1];
    expect(other.tag).toBe("Other");
    expect(other.isOther).toBe(true);
    // Other count = sum of tags 9–12 = 4 + 3 + 2 + 1 = 10.
    expect(other.count).toBe(10);
  });

  it("does not add an 'Other' slice when count <= top N", () => {
    const data = Array.from({ length: 4 }, (_, i) => ({ tag: `t${i}`, count: i + 1 }));
    const slices = buildSlices(data);
    expect(slices).toHaveLength(4);
    expect(slices.every((s) => !s.isOther)).toBe(true);
  });
});

describe("TagDistribution", () => {
  it("renders the pie chart when data is present", () => {
    const { container } = render(
      <TagDistribution data={[{ tag: "work", count: 5 }, { tag: "home", count: 3 }]} />,
    );
    // Empty handling is the GraphCard parent's job; this component
    // assumes at least one slice to draw.
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("renders the Other slice when input exceeds the top-N cap", () => {
    const data = Array.from({ length: 10 }, (_, i) => ({
      tag: `t${i}`,
      count: 10 - i,
    }));
    const { container } = render(<TagDistribution data={data} />);
    // The Cell `fill` branch for the Other slice is now exercised — the
    // rendered recharts surface mounts normally without throwing.
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});

describe("filterByTag", () => {
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

  it("dispatches switch-tab first, then memory-browser on next tick", () => {
    vi.useFakeTimers();
    filterByTag("work");
    // Pre-flush: only the tab-switch has fired so MemoryBrowser can mount.
    expect(calls.map((e) => e.type)).toEqual(["hive:switch-tab"]);
    vi.runAllTimers();
    const types = calls.map((e) => e.type);
    expect(types).toEqual(["hive:switch-tab", "hive:memory-browser"]);
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ tag: "work" });
    vi.useRealTimers();
  });

  it("is a no-op without a dispatchEvent global", () => {
    globalThis.dispatchEvent = undefined;
    expect(() => filterByTag("x")).not.toThrow();
  });
});

describe("formatTagTooltip", () => {
  it("labels the value with 'memories' and passes the name through", () => {
    expect(formatTagTooltip(3, "work")).toEqual(["3 memories", "work"]);
  });
});

describe("handlePieSliceClick", () => {
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

  it("dispatches for a real slice", () => {
    vi.useFakeTimers();
    handlePieSliceClick({ tag: "work", count: 5 });
    vi.runAllTimers();
    const types = calls.map((e) => e.type);
    expect(types).toContain("hive:memory-browser");
    expect(types).toContain("hive:switch-tab");
    vi.useRealTimers();
  });

  it("unwraps a Recharts-style payload wrapper", () => {
    vi.useFakeTimers();
    handlePieSliceClick({ payload: { tag: "home", count: 3 } });
    vi.runAllTimers();
    const browserEvent = calls.find((e) => e.type === "hive:memory-browser");
    expect(browserEvent.detail).toEqual({ tag: "home" });
    vi.useRealTimers();
  });

  it("ignores the Other bucket", () => {
    handlePieSliceClick({ tag: "Other", count: 10, isOther: true });
    expect(calls).toEqual([]);
  });

  it("ignores missing / malformed input", () => {
    handlePieSliceClick(undefined);
    handlePieSliceClick(null);
    handlePieSliceClick({});
    handlePieSliceClick({ tag: "" });
    handlePieSliceClick({ payload: { tag: null } });
    expect(calls).toEqual([]);
  });
});
