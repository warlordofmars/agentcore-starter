// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Stats, { GraphCard } from "./Stats.jsx";

vi.mock("../api.js", () => ({
  api: {
    getAccountStats: vi.fn(),
  },
}));

// Stub the chart components — each has its own co-located test file.
// Mocking keeps Stats.test focused on the parent layout + branch logic
// and avoids booting recharts + SVG measurement in every test.
vi.mock("./stats/ActivityHeatmap.jsx", () => ({
  default: () => <div data-testid="activity-heatmap" />,
}));
vi.mock("./stats/TopRecalled.jsx", () => ({
  default: () => <div data-testid="top-recalled" />,
}));
vi.mock("./stats/TagDistribution.jsx", () => ({
  default: () => <div data-testid="tag-distribution" />,
}));
vi.mock("./stats/MemoryGrowth.jsx", () => ({
  default: () => <div data-testid="memory-growth" />,
}));
vi.mock("./stats/FreshnessScatter.jsx", () => ({
  default: () => <div data-testid="freshness-scatter" />,
}));
vi.mock("./stats/ClientContribution.jsx", () => ({
  default: () => <div data-testid="client-contribution" />,
}));
vi.mock("./stats/TagCooccurrence.jsx", () => ({
  default: () => <div data-testid="tag-cooccurrence" />,
}));
vi.mock("./stats/QuotaGauge.jsx", () => ({
  default: ({ quota }) => (
    <div data-testid="quota-gauge">
      {quota.memory_count}
      {quota.memory_limit !== null ? `/${quota.memory_limit}` : ""}
    </div>
  ),
}));

import { api } from "../api.js";

const MINIMAL_STATS = {
  window_days: 90,
  activity_heatmap: Array.from({ length: 90 }, (_, i) => ({
    date: `2026-${String((i % 12) + 1).padStart(2, "0")}-01`,
    count: i === 0 ? 3 : 0,
  })),
  top_recalled: [{ memory_id: "m1", key: "top-key", recall_count: 5 }],
  tag_distribution: [{ tag: "work", count: 4 }],
  memory_growth: Array.from({ length: 90 }, (_, i) => ({
    date: `2026-${String((i % 12) + 1).padStart(2, "0")}-01`,
    cumulative: i,
  })),
  quota: { memory_count: 12, memory_limit: 100 },
  freshness: Array.from({ length: 12 }, (_, i) => ({
    memory_id: `m${i}`,
    key: `key-${i}`,
    tags: [`t${i}`],
    days_since_created: i * 5,
    days_since_accessed: i,
  })),
  client_contribution: [{ date: "2026-04-01", client_id: "c1", count: 2 }],
  client_names: { c1: "Claude Code" },
  tag_cooccurrence: [{ source: "a", target: "b", weight: 1 }],
};

describe("GraphCard", () => {
  it("renders children when data is present", () => {
    render(
      <GraphCard title="T" data={[1]}>
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("body")).toBeTruthy();
  });

  it("renders empty message when data is empty array", () => {
    render(
      <GraphCard title="T" data={[]} empty="nope">
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("nope")).toBeTruthy();
  });

  it("falls back to default empty copy when no empty prop", () => {
    render(
      <GraphCard title="T" data={[]}>
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("No data yet.")).toBeTruthy();
  });

  it("renders description when provided", () => {
    render(<GraphCard title="T" description="sub" data={[1]}>body</GraphCard>);
    expect(screen.getByText("sub")).toBeTruthy();
  });

  it("treats object data as present when non-empty", () => {
    render(
      <GraphCard title="T" data={{ foo: 1 }}>
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("body")).toBeTruthy();
  });

  it("treats empty object as no data", () => {
    render(
      <GraphCard title="T" data={{}}>
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("No data yet.")).toBeTruthy();
  });

  it("treats undefined data as no data (falls through both type checks)", () => {
    render(
      <GraphCard title="T">
        <div>body</div>
      </GraphCard>,
    );
    expect(screen.getByText("No data yet.")).toBeTruthy();
  });
});

describe("Stats", () => {
  beforeEach(() => {
    api.getAccountStats.mockResolvedValue(MINIMAL_STATS);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state before data arrives", async () => {
    let resolveFn;
    api.getAccountStats.mockReturnValue(
      new Promise((resolve) => {
        resolveFn = resolve;
      }),
    );
    await act(async () => render(<Stats />));
    expect(screen.getByText("Loading…")).toBeTruthy();
    await act(async () => resolveFn(MINIMAL_STATS));
  });

  it("renders all eight graph-card titles once data arrives", async () => {
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("Activity heatmap")).toBeTruthy());
    for (const title of [
      "Top recalled",
      "Tag distribution",
      "Memory growth",
      "Quota",
      "Freshness",
      "Client contribution",
      "Tag co-occurrence",
    ]) {
      expect(screen.getByText(title)).toBeTruthy();
    }
  });

  it("passes the quota prop through to QuotaGauge", async () => {
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByTestId("quota-gauge")).toBeTruthy());
    // Mock stringifies the quota to {count}/{limit}.
    expect(screen.getByTestId("quota-gauge").textContent).toBe("12/100");
  });

  it("QuotaGauge receives null limit when the user is exempt/admin", async () => {
    api.getAccountStats.mockResolvedValueOnce({
      ...MINIMAL_STATS,
      quota: { memory_count: 7, memory_limit: null },
    });
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByTestId("quota-gauge")).toBeTruthy());
    // Mock omits the /limit suffix when memory_limit is null, proving the
    // prop passed through correctly.
    expect(screen.getByTestId("quota-gauge").textContent).toBe("7");
  });

  it("Quota card shows empty copy when memory_count is malformed", async () => {
    api.getAccountStats.mockResolvedValueOnce({
      ...MINIMAL_STATS,
      quota: { memory_count: "oops", memory_limit: 100 },
    });
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("Quota")).toBeTruthy());
    // GraphCard's empty copy renders instead of a silent blank QuotaGauge.
    expect(screen.getByText(/Quota data unavailable/)).toBeTruthy();
    expect(screen.queryByTestId("quota-gauge")).toBeNull();
  });

  it("top-level empty state when user has no memories", async () => {
    api.getAccountStats.mockResolvedValueOnce({
      ...MINIMAL_STATS,
      quota: { memory_count: 0, memory_limit: 100 },
    });
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("No data yet")).toBeTruthy());
    // Graph cards should NOT render in the empty-shell state.
    expect(screen.queryByText("Activity heatmap")).toBeNull();
  });

  it("re-fetches with new window when a window button is clicked", async () => {
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("Activity heatmap")).toBeTruthy());
    expect(api.getAccountStats).toHaveBeenLastCalledWith("90");
    await act(async () => {
      fireEvent.click(screen.getByText("Last 30 days"));
    });
    await waitFor(() =>
      expect(api.getAccountStats).toHaveBeenLastCalledWith("30"),
    );
  });

  it("shows error banner when API call fails", async () => {
    api.getAccountStats.mockRejectedValueOnce(new Error("boom"));
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());
    // No graph cards rendered in the error branch.
    expect(screen.queryByText("Activity heatmap")).toBeNull();
  });

  it("renders empty card body for activity_heatmap when all counts are zero", async () => {
    api.getAccountStats.mockResolvedValueOnce({
      ...MINIMAL_STATS,
      activity_heatmap: MINIMAL_STATS.activity_heatmap.map((d) => ({
        ...d,
        count: 0,
      })),
    });
    await act(async () => render(<Stats />));
    await waitFor(() => expect(screen.getByText("Activity heatmap")).toBeTruthy());
    expect(screen.getByText("No activity in this window yet.")).toBeTruthy();
  });

});
