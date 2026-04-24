// Copyright (c) 2026 John Carter. All rights reserved.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MemoryGrowth, { projectGrowth } from "./MemoryGrowth.jsx";

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe("projectGrowth", () => {
  it("returns empty when history is shorter than MIN_HISTORY_DAYS", () => {
    const history = Array.from({ length: 10 }, (_, i) => ({
      date: `2026-04-${String(i + 1).padStart(2, "0")}`,
      cumulative: i,
    }));
    expect(projectGrowth(history)).toEqual([]);
  });

  it("returns empty when history is null/undefined", () => {
    expect(projectGrowth()).toEqual([]);
    expect(projectGrowth(null)).toEqual([]);
  });

  it("returns empty when growth is flat/declining", () => {
    const history = Array.from({ length: 30 }, (_, i) => ({
      date: `2026-04-${String(i + 1).padStart(2, "0")}`,
      cumulative: 5,
    }));
    expect(projectGrowth(history)).toEqual([]);
  });

  it("projects `days` points forward when history has positive growth", () => {
    const history = Array.from({ length: 30 }, (_, i) => ({
      date: `2026-03-${String(i + 1).padStart(2, "0")}`,
      cumulative: i,
    }));
    const projection = projectGrowth(history, 10);
    expect(projection).toHaveLength(10);
    // Each projected cumulative is non-decreasing and starts > last actual.
    const last = history[history.length - 1].cumulative;
    expect(projection[0].projected).toBeGreaterThan(last);
    for (let i = 1; i < projection.length; i++) {
      expect(projection[i].projected).toBeGreaterThanOrEqual(projection[i - 1].projected);
    }
  });
});

describe("MemoryGrowth", () => {
  it("returns null when data is missing", () => {
    const { container } = render(<MemoryGrowth />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when data is an empty array", () => {
    const { container } = render(<MemoryGrowth data={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a chart container when data is present", () => {
    const data = Array.from({ length: 30 }, (_, i) => ({
      date: `2026-03-${String(i + 1).padStart(2, "0")}`,
      cumulative: i,
    }));
    const { container } = render(<MemoryGrowth data={data} />);
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("renders without a projection line for short histories", () => {
    const data = Array.from({ length: 5 }, (_, i) => ({
      date: `2026-04-${String(i + 1).padStart(2, "0")}`,
      cumulative: i,
    }));
    const { container } = render(<MemoryGrowth data={data} />);
    // Chart still renders (history-only path).
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
