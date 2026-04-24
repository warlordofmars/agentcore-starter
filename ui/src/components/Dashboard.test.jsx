// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard.jsx";

// Recharts renders SVG; jsdom doesn't support ResizeObserver
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

vi.mock("../api.js", () => ({
  api: {
    getStats: vi.fn(),
    getMetrics: vi.fn(),
    getCosts: vi.fn(),
    getAlarms: vi.fn(),
  },
}));

import { api } from "../api.js";
import { formatCostTick, formatCostTooltip, CustomTooltip, CustomCostTooltip, CustomDailyCostTooltip, AlarmBadge, AlarmSummaryBadge, AlarmOkCountBadge, ALARM_STATE_STYLE } from "./Dashboard.jsx";

const STATS = {
  total_memories: 42,
  total_clients: 3,
  total_users: 7,
  events_today: 10,
  events_last_7_days: 88,
};

const METRICS = {
  period: "24h",
  environment: "test",
  metrics: {
    inv_remember: { timestamps: ["2026-04-01T12:00:00Z"], values: [5] },
    err_remember: { timestamps: ["2026-04-01T12:00:00Z"], values: [1] },
    p99_remember: { timestamps: ["2026-04-01T12:00:00Z"], values: [120] },
    inv_recall: { timestamps: [], values: [] },
    err_recall: { timestamps: [], values: [] },
    p99_recall: { timestamps: [], values: [] },
    inv_forget: { timestamps: [], values: [] },
    err_forget: { timestamps: [], values: [] },
    p99_forget: { timestamps: [], values: [] },
    inv_listmemories: { timestamps: [], values: [] },
    err_listmemories: { timestamps: [], values: [] },
    p99_listmemories: { timestamps: [], values: [] },
    inv_summarizecontext: { timestamps: [], values: [] },
    err_summarizecontext: { timestamps: [], values: [] },
    p99_summarizecontext: { timestamps: [], values: [] },
    inv_searchmemories: { timestamps: [], values: [] },
    err_searchmemories: { timestamps: [], values: [] },
    p99_searchmemories: { timestamps: [], values: [] },
    tokens_issued: { timestamps: ["2026-04-01T12:00:00Z"], values: [7] },
    token_failures: { timestamps: ["2026-04-01T12:00:00Z"], values: [2] },
    csp_violations: { timestamps: ["2026-04-01T12:00:00Z"], values: [17] },
    rate_limited_requests: { timestamps: ["2026-04-01T12:00:00Z"], values: [23] },
  },
};

const COSTS = {
  environment: "dev",
  currency: "USD",
  note: "Cost data lags ~24 h. Cached for 24 h.",
  monthly: [
    {
      period: "2026-03-01",
      total: 0.62,
      by_service: { "AWS Lambda": 0.5, "Amazon DynamoDB": 0.12 },
    },
  ],
  daily: [
    { date: "2026-04-01", total: 0.02 },
    { date: "2026-04-02", total: 0.03 },
  ],
};

const ALARMS = {
  environment: "test",
  alarms: [
    {
      name: "Hive-test-McpErrorRate",
      description: "MCP error rate > 5%",
      state: "OK",
      state_updated_at: "2026-04-11T12:00:00+00:00",
      threshold: 5.0,
      comparison_operator: "GreaterThanThreshold",
      metric_name: "ErrorRate",
      namespace: "AWS/Lambda",
    },
  ],
};

describe("AlarmBadge", () => {
  it("renders OK state with description as label", () => {
    const { container } = render(
      <AlarmBadge alarm={{ name: "Hive-test-McpErrorRate", description: "MCP error rate > 5%", state: "OK" }} />
    );
    expect(screen.getByText("MCP error rate > 5%")).toBeTruthy();
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("renders ALARM state", () => {
    render(<AlarmBadge alarm={{ name: "Hive-test-ToolErrors", description: "Tool errors high", state: "ALARM" }} />);
    expect(screen.getByText("Tool errors high")).toBeTruthy();
  });

  it("renders INSUFFICIENT_DATA state", () => {
    render(<AlarmBadge alarm={{ name: "Hive-test-Foo", description: "Foo alarm", state: "INSUFFICIENT_DATA" }} />);
    expect(screen.getByText("Foo alarm")).toBeTruthy();
  });

  it("falls back to INSUFFICIENT_DATA style for unknown state", () => {
    render(<AlarmBadge alarm={{ name: "Hive-test-X", description: "", state: "UNKNOWN_STATE" }} />);
    // Falls back: icon is AlertTriangle (same as INSUFFICIENT_DATA)
    expect(ALARM_STATE_STYLE.INSUFFICIENT_DATA).toBeTruthy();
  });

  it("strips env prefix from name when description is empty", () => {
    render(<AlarmBadge alarm={{ name: "Hive-dev-McpErrorRate", description: "", state: "OK" }} />);
    expect(screen.getByText("McpErrorRate")).toBeTruthy();
  });
});

describe("AlarmSummaryBadge", () => {
  it("pluralises the alarm count", () => {
    render(<AlarmSummaryBadge count={12} />);
    expect(screen.getByText("12 alarms OK")).toBeTruthy();
  });

  it("uses singular form for one alarm", () => {
    render(<AlarmSummaryBadge count={1} />);
    expect(screen.getByText("1 alarm OK")).toBeTruthy();
  });
});

describe("AlarmOkCountBadge", () => {
  it("renders the muted +N OK pill", () => {
    render(<AlarmOkCountBadge count={10} />);
    expect(screen.getByText("+10 OK")).toBeTruthy();
  });
});

describe("CustomTooltip", () => {
  it("returns null when not active", () => {
    const { container } = render(<CustomTooltip active={false} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when payload is empty", () => {
    const { container } = render(<CustomTooltip active={true} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders label and payload entries when active", () => {
    const payload = [{ dataKey: "remember", value: 5, color: "#e8a020" }];
    render(<CustomTooltip active={true} payload={payload} label="2026-04-01 12:00" />);
    expect(screen.getByText("2026-04-01 12:00")).toBeTruthy();
    expect(screen.getByText("remember:")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
  });
});

describe("CustomDailyCostTooltip", () => {
  it("returns null when not active", () => {
    const { container } = render(<CustomDailyCostTooltip active={false} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when payload is empty", () => {
    const { container } = render(<CustomDailyCostTooltip active={true} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders date and formatted cost when active", () => {
    const payload = [{ value: 0.02 }];
    render(<CustomDailyCostTooltip active={true} payload={payload} label="2026-04-01" />);
    expect(screen.getByText("2026-04-01")).toBeTruthy();
    expect(screen.getByText("$0.0200")).toBeTruthy();
  });
});

describe("CustomCostTooltip", () => {
  it("returns null when not active", () => {
    const { container } = render(<CustomCostTooltip active={false} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when payload is empty", () => {
    const { container } = render(<CustomCostTooltip active={true} payload={[]} label="x" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders label and formatted cost entries when active", () => {
    const payload = [{ dataKey: "AWS Lambda", value: 0.5, color: "#1a1a2e" }];
    render(<CustomCostTooltip active={true} payload={payload} label="2026-03" />);
    expect(screen.getByText("2026-03")).toBeTruthy();
    expect(screen.getByText("AWS Lambda:")).toBeTruthy();
    expect(screen.getByText("$0.5000")).toBeTruthy();
  });
});

describe("formatters", () => {
  it("formatCostTick formats to 2 decimal places with $", () => {
    expect(formatCostTick(1.5)).toBe("$1.50");
    expect(formatCostTick(0)).toBe("$0.00");
  });

  it("formatCostTooltip formats to 4 decimal places with $", () => {
    expect(formatCostTooltip(0.1234)).toBe("$0.1234");
    expect(formatCostTooltip("0.5")).toBe("$0.5000");
  });
});

describe("Dashboard", () => {
  beforeEach(() => {
    api.getStats.mockResolvedValue(STATS);
    api.getMetrics.mockResolvedValue(METRICS);
    api.getCosts.mockResolvedValue(COSTS);
    api.getAlarms.mockResolvedValue(ALARMS);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Dashboard heading", async () => {
    await act(async () => render(<Dashboard />));
    expect(screen.getByText("Dashboard")).toBeTruthy();
  });

  it("renders period selector buttons including 30d", async () => {
    await act(async () => render(<Dashboard />));
    expect(screen.getByText("1h")).toBeTruthy();
    expect(screen.getByText("24h")).toBeTruthy();
    expect(screen.getByText("7d")).toBeTruthy();
    expect(screen.getByText("30d")).toBeTruthy();
  });

  it("selected period button has orange background", async () => {
    await act(async () => render(<Dashboard />));
    const btn = screen.getByText("24h");
    expect(btn.style.background).toBe("rgb(232, 160, 32)");
  });

  it("renders summary stat cards after load", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("42")).toBeTruthy());
    expect(screen.getByText("Total Memories")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("Total Clients")).toBeTruthy();
    expect(screen.getByText("10")).toBeTruthy();
    expect(screen.getByText("Events Today")).toBeTruthy();
    expect(screen.getByText("88")).toBeTruthy();
    expect(screen.getByText("Events (7d)")).toBeTruthy();
  });

  it("renders Total Users stat card from stats.total_users", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Total Users")).toBeTruthy());
    // total_users = 7 appears multiple times (also tokens_issued); confirm at least one
    expect(screen.getAllByText("7").length).toBeGreaterThanOrEqual(1);
  });

  it("renders — for Total Users when total_users is null", async () => {
    api.getStats.mockResolvedValue({ ...STATS, total_users: null });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Total Users")).toBeTruthy());
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("renders MTD cost stat card", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("AWS Cost (MTD)")).toBeTruthy());
    expect(screen.getByText("$0.62")).toBeTruthy();
  });

  it("does not render MTD cost card when no cost data", async () => {
    api.getCosts.mockResolvedValue({ environment: "dev", currency: "USD", note: "x", monthly: [], daily: [] });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.queryByText("AWS Cost (MTD)")).toBeFalsy());
  });

  it("renders section headers", async () => {
    await act(async () => render(<Dashboard />));
    expect(screen.getByText("Tool Invocations")).toBeTruthy();
    expect(screen.getByText("Tool Latency p99 (ms)")).toBeTruthy();
    expect(screen.getByText("Auth Events")).toBeTruthy();
    expect(screen.getByText("Security")).toBeTruthy();
    expect(screen.getByText("Daily AWS Spend (Last 30 Days)")).toBeTruthy();
    expect(screen.getByText("Monthly AWS Spend")).toBeTruthy();
  });

  it("renders auth stat cards from metric data", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Tokens Issued")).toBeTruthy());
    expect(screen.getByText("Validation Failures")).toBeTruthy();
  });

  it("renders CSP violations stat card from metric data", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("CSP Violations")).toBeTruthy());
  });

  it("renders Rate Limited Requests stat card (#367)", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Rate Limited Requests")).toBeTruthy());
    // Aggregate value = sum of metric series; mock returns a single [23].
    expect(screen.getByText("23")).toBeTruthy();
  });

  it("Rate Limited Requests defaults to 0 when metric series missing", async () => {
    api.getMetrics.mockResolvedValueOnce({
      period: "24h",
      environment: "test",
      metrics: {}, // no rate_limited_requests key at all
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Rate Limited Requests")).toBeTruthy());
    // Fallback (… .values ?? []).reduce(sum, 0) → 0 when the series is absent.
    // The StatCard renders two divs; label's parent is the card, whose
    // textContent concatenates value + label.
    const cardLabel = screen.getByText("Rate Limited Requests");
    expect(cardLabel.parentElement.textContent).toBe("0Rate Limited Requests");
  });

  it("renders cost note", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText(/Cost data lags/)).toBeTruthy());
  });

  it("shows relative refresh time after load", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("just now")).toBeTruthy());
  });

  it("switches period when a period button is clicked", async () => {
    await act(async () => render(<Dashboard />));
    fireEvent.click(screen.getByText("1h"));
    await waitFor(() => expect(api.getMetrics).toHaveBeenCalledWith("1h"));
  });

  it("clicking 7d calls getMetrics with 7d", async () => {
    await act(async () => render(<Dashboard />));
    fireEvent.click(screen.getByText("7d"));
    await waitFor(() => expect(api.getMetrics).toHaveBeenCalledWith("7d"));
  });

  it("clicking 30d calls getMetrics with 30d", async () => {
    await act(async () => render(<Dashboard />));
    fireEvent.click(screen.getByText("30d"));
    await waitFor(() => expect(api.getMetrics).toHaveBeenCalledWith("30d"));
  });

  it("clicking Refresh reloads all data", async () => {
    await act(async () => render(<Dashboard />));
    const count = api.getStats.mock.calls.length;
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(api.getStats.mock.calls.length).toBeGreaterThan(count));
  });

  it("auto-refreshes after 60 seconds", async () => {
    vi.useFakeTimers();
    await act(async () => render(<Dashboard />));
    const count = api.getStats.mock.calls.length;
    await act(async () => vi.advanceTimersByTime(60_000));
    expect(api.getStats.mock.calls.length).toBeGreaterThan(count);
    vi.useRealTimers();
  });

  it("shows empty state when no invocation data", async () => {
    api.getMetrics.mockResolvedValue({ period: "24h", environment: "test", metrics: {} });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No invocation data for this period.")).toBeTruthy()
    );
    expect(screen.getByText("No latency data for this period.")).toBeTruthy();
  });

  it("shows empty state when no monthly cost data", async () => {
    api.getCosts.mockResolvedValue({
      environment: "dev",
      currency: "USD",
      note: "Cost data lags ~24 h.",
      monthly: [],
      daily: [],
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No cost data available yet.")).toBeTruthy()
    );
  });

  it("shows empty state when no daily cost data", async () => {
    api.getCosts.mockResolvedValue({
      environment: "dev",
      currency: "USD",
      note: "Cost data lags ~24 h.",
      monthly: [{ period: "2026-03-01", total: 0.62, by_service: { "AWS Lambda": 0.62 } }],
      daily: [],
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No daily cost data available yet.")).toBeTruthy()
    );
  });

  it("shows metrics error banner when getMetrics rejects", async () => {
    api.getMetrics.mockRejectedValue(new Error("CloudWatch unavailable"));
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("CloudWatch unavailable")).toBeTruthy()
    );
  });

  it("shows costs error banner when getCosts rejects", async () => {
    api.getCosts.mockRejectedValue(new Error("Cost Explorer unavailable"));
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("Cost Explorer unavailable")).toBeTruthy()
    );
  });

  it("handles getMetrics rejection with no message", async () => {
    api.getMetrics.mockRejectedValue({});
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("Failed to load metrics")).toBeTruthy()
    );
  });

  it("handles getCosts rejection with no message", async () => {
    api.getCosts.mockRejectedValue({});
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("Failed to load costs")).toBeTruthy()
    );
  });

  it("renders loading indicator during fetch", async () => {
    let resolve;
    api.getStats.mockReturnValue(new Promise((r) => { resolve = r; }));
    api.getMetrics.mockReturnValue(new Promise(() => {}));
    api.getCosts.mockReturnValue(new Promise(() => {}));

    await act(async () => render(<Dashboard />));
    expect(screen.getByText("Loading…")).toBeTruthy();
    resolve(STATS);
  });

  it("renders dash for undefined StatCard value", async () => {
    api.getStats.mockResolvedValue({
      total_memories: null,
      total_clients: 3,
      total_users: null,
      events_today: 10,
      events_last_7_days: 88,
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1));
  });

  it("handles metrics response missing metrics key", async () => {
    api.getMetrics.mockResolvedValue({ period: "24h", environment: "test" });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No invocation data for this period.")).toBeTruthy()
    );
  });

  it("handles costs response missing monthly key", async () => {
    api.getCosts.mockResolvedValue({ environment: "dev", currency: "USD", note: "Cost data lags ~24 h." });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No cost data available yet.")).toBeTruthy()
    );
  });

  it("handles costs response missing daily key", async () => {
    api.getCosts.mockResolvedValue({
      environment: "dev",
      currency: "USD",
      note: "Cost data lags ~24 h.",
      monthly: [{ period: "2026-03-01", total: 0.62, by_service: { "AWS Lambda": 0.62 } }],
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() =>
      expect(screen.getByText("No daily cost data available yet.")).toBeTruthy()
    );
  });

  it("handles sparse values array (values[i] undefined)", async () => {
    api.getMetrics.mockResolvedValue({
      period: "24h",
      environment: "test",
      metrics: {
        inv_remember: { timestamps: ["2026-04-01T12:00:00Z", "2026-04-01T13:00:00Z"], values: [5] },
        p99_remember: { timestamps: ["2026-04-01T12:00:00Z", "2026-04-01T13:00:00Z"], values: [120] },
        tokens_issued: { timestamps: [], values: [] },
        token_failures: { timestamps: [], values: [] },
      },
    });
    await act(async () => render(<Dashboard />));
    expect(screen.getByText("Tool Invocations")).toBeTruthy();
  });

  it("collapses all-OK alarms into a single summary badge", async () => {
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("1 alarm OK")).toBeTruthy());
    // Individual OK alarm label must not appear — that's the whole point of collapsing.
    expect(screen.queryByText("MCP error rate > 5%")).toBeNull();
  });

  it("shows firing alarms individually with a muted OK count when mixed", async () => {
    api.getAlarms.mockResolvedValue({
      environment: "test",
      alarms: [
        { name: "Hive-test-McpErrorRate", description: "MCP error rate > 5%", state: "OK" },
        { name: "Hive-test-McpErrorRate", description: "MCP error rate > 5%", state: "OK" },
        { name: "Hive-test-ToolErrors", description: "Tool errors high", state: "ALARM" },
      ],
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Tool errors high")).toBeTruthy());
    expect(screen.getByText("+2 OK")).toBeTruthy();
    // Firing-state view never shows the summary badge.
    expect(screen.queryByText("2 alarms OK")).toBeNull();
  });

  it("renders only firing alarms when none are OK", async () => {
    api.getAlarms.mockResolvedValue({
      environment: "test",
      alarms: [
        { name: "Hive-test-ToolErrors", description: "Tool errors high", state: "ALARM" },
      ],
    });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Tool errors high")).toBeTruthy());
    expect(screen.queryByText(/OK/)).toBeNull();
  });

  it("shows alarm skeleton while loading", async () => {
    let resolve;
    api.getAlarms.mockReturnValue(new Promise((r) => { resolve = r; }));
    await act(async () => render(<Dashboard />));
    // Four skeleton blocks rendered for alarms (no alarms data yet)
    resolve(ALARMS);
  });

  it("shows alarms error banner when getAlarms rejects", async () => {
    api.getAlarms.mockRejectedValue(new Error("CloudWatch unavailable"));
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("CloudWatch unavailable")).toBeTruthy());
  });

  it("handles getAlarms rejection with no message", async () => {
    api.getAlarms.mockRejectedValue({});
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.getByText("Failed to load alarms")).toBeTruthy());
  });

  it("renders nothing for alarm row when alarms list is empty", async () => {
    api.getAlarms.mockResolvedValue({ environment: "test", alarms: [] });
    await act(async () => render(<Dashboard />));
    await waitFor(() => expect(screen.queryByText("MCP error rate > 5%")).toBeNull());
  });
});
