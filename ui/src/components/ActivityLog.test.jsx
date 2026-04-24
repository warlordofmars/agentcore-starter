// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ActivityLog from "./ActivityLog.jsx";

vi.mock("../api.js", () => ({
  api: {
    getActivity: vi.fn(),
    getStats: vi.fn(),
  },
}));

import { api } from "../api.js";

const makeStats = () => ({
  total_memories: 10,
  total_clients: 3,
  events_today: 5,
  events_last_7_days: 42,
});

const makeEvent = (overrides = {}) => ({
  event_id: "ev1",
  timestamp: new Date("2026-01-01T12:00:00Z").toISOString(),
  event_type: "memory_created",
  client_id: "abc123def456",
  metadata: { key: "foo", count: 1 },
  ...overrides,
});

describe("ActivityLog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getActivity.mockResolvedValue({ items: [], has_more: false });
    api.getStats.mockResolvedValue(makeStats());
  });

  it("renders heading", async () => {
    await act(async () => render(<ActivityLog />));
    expect(screen.getByText("Activity Log")).toBeTruthy();
  });

  it("shows stats bar after load", async () => {
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText("Total Memories")).toBeTruthy());
    expect(screen.getByText("10")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
  });

  it("shows empty state when no events", async () => {
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText("No activity in this period")).toBeTruthy());
  });

  it("renders event rows", async () => {
    api.getActivity.mockResolvedValue({ items: [makeEvent()], has_more: false });
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText("memory_created")).toBeTruthy());
    expect(screen.getByText("abc123de…")).toBeTruthy();
  });

  it("shows 'more available' text when has_more is true", async () => {
    api.getActivity.mockResolvedValue({ items: [makeEvent()], has_more: true });
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText(/more available/)).toBeTruthy());
  });

  it("shows no 'more available' text when has_more is false", async () => {
    api.getActivity.mockResolvedValue({ items: [makeEvent()], has_more: false });
    await act(async () => render(<ActivityLog />));
    await waitFor(() => screen.getByText("memory_created"));
    expect(screen.queryByText(/more available/)).toBeNull();
  });

  it("renders unknown event_type with fallback colour", async () => {
    api.getActivity.mockResolvedValue({
      items: [makeEvent({ event_type: "unknown_event_xyz" })],
      has_more: false,
    });
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText("unknown_event_xyz")).toBeTruthy());
  });

  it("renders metadata as key: value pairs", async () => {
    api.getActivity.mockResolvedValue({
      items: [makeEvent({ metadata: { topic: "foo" } })],
      has_more: false,
    });
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText(/topic/)).toBeTruthy());
  });

  it("shows error when API fails", async () => {
    api.getActivity.mockRejectedValue(new Error("Service down"));
    api.getStats.mockRejectedValue(new Error("Service down"));
    await act(async () => render(<ActivityLog />));
    await waitFor(() => expect(screen.getByText("Service down")).toBeTruthy());
  });

  it("hides stats bar when stats not yet loaded", async () => {
    api.getStats.mockResolvedValue(null);
    await act(async () => render(<ActivityLog />));
    await waitFor(() => {});
    expect(screen.queryByText("Total Memories")).toBeNull();
  });

  it("reloads when Refresh is clicked", async () => {
    await act(async () => render(<ActivityLog />));
    await waitFor(() => screen.getByText("Refresh"));
    await act(async () => fireEvent.click(screen.getByText("Refresh")));
    expect(api.getActivity).toHaveBeenCalledTimes(2);
  });

  it("reloads when days select changes", async () => {
    await act(async () => render(<ActivityLog />));
    await waitFor(() => screen.getByText("Refresh"));
    const selects = screen.getAllByRole("combobox");
    await act(async () => fireEvent.change(selects[0], { target: { value: "1" } }));
    expect(api.getActivity).toHaveBeenCalledWith(1, expect.anything());
  });

  it("reloads when limit select changes", async () => {
    await act(async () => render(<ActivityLog />));
    await waitFor(() => screen.getByText("Refresh"));
    const selects = screen.getAllByRole("combobox");
    await act(async () => fireEvent.change(selects[1], { target: { value: "500" } }));
    expect(api.getActivity).toHaveBeenCalledWith(expect.anything(), { limit: 500 });
  });
});
