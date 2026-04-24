// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import LogViewer from "./LogViewer.jsx";

vi.mock("../api.js", () => ({
  api: { getLogs: vi.fn() },
}));

import { api } from "../api.js";

const makeEvent = (overrides = {}) => ({
  timestamp: Date.now() - 5000,
  message: '{"level":"INFO","message":"tool called"}',
  log_group: "/aws/lambda/hive-dev-mcp",
  log_stream: "2026/04/11/[$LATEST]abc",
  event_id: "evt-001",
  ...overrides,
});

describe("LogViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getLogs.mockResolvedValue({ events: [], next_token: null });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ---------------------------------------------------------------------------
  // Initial render
  // ---------------------------------------------------------------------------

  it("renders heading and controls", async () => {
    await act(async () => render(<LogViewer />));
    expect(screen.getByText("Logs")).toBeTruthy();
    expect(screen.getByLabelText("Log group")).toBeTruthy();
    expect(screen.getByLabelText("Time window")).toBeTruthy();
    expect(screen.getByPlaceholderText("Filter pattern…")).toBeTruthy();
  });

  it("shows empty message when no events", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText("No log events found.")).toBeTruthy());
  });

  it("calls getLogs on mount with defaults", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() =>
      expect(api.getLogs).toHaveBeenCalledWith({ group: "all", window: "1h", filter: "" }),
    );
  });

  // ---------------------------------------------------------------------------
  // Log event rendering
  // ---------------------------------------------------------------------------

  it("renders a log event row", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText("tool called")).toBeTruthy());
    // toolbar has one INFO button + row has one INFO badge = 2 total
    expect(screen.getAllByText("INFO").length).toBe(2);
    expect(screen.getByText("hive-dev-mcp")).toBeTruthy(); // group suffix
  });

  it("renders ERROR level badge", async () => {
    const event = makeEvent({ message: '{"level":"ERROR","message":"something broke"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    // toolbar button + row badge = 2
    await waitFor(() => expect(screen.getAllByText("ERROR").length).toBe(2));
  });

  it("renders WARNING level badge", async () => {
    const event = makeEvent({ message: '{"level":"WARNING","message":"heads up"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("WARNING").length).toBe(2));
  });

  it("renders DEBUG level badge", async () => {
    const event = makeEvent({ message: '{"level":"DEBUG","message":"debug info"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("DEBUG").length).toBe(2));
  });

  it("falls back to INFO for unknown JSON level", async () => {
    const event = makeEvent({ message: '{"level":"TRACE","message":"trace msg"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("INFO").length).toBe(2));
  });

  it("detects ERROR level from plain text", async () => {
    const event = makeEvent({ message: "ERROR something went wrong" });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("ERROR").length).toBe(2));
  });

  it("detects WARNING level from plain text", async () => {
    const event = makeEvent({ message: "WARN something is fishy" });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("WARNING").length).toBe(2));
  });

  it("detects DEBUG level from plain text", async () => {
    const event = makeEvent({ message: "DEBUG verbose stuff" });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("DEBUG").length).toBe(2));
  });

  it("falls back to INFO for plain text with no level keyword", async () => {
    const event = makeEvent({ message: "something happened" });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("INFO").length).toBe(2));
  });

  it("uses msg field when message field is absent", async () => {
    const event = makeEvent({ message: '{"level":"INFO","msg":"alt field"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText("alt field")).toBeTruthy());
  });

  it("detects level from levelname field", async () => {
    const event = makeEvent({ message: '{"levelname":"ERROR","message":"from levelname"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("ERROR").length).toBe(2));
  });

  it("detects level from severity field", async () => {
    const event = makeEvent({ message: '{"severity":"WARNING","message":"from severity"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("WARNING").length).toBe(2));
  });

  it("falls back to INFO when JSON has no level/levelname/severity field", async () => {
    const event = makeEvent({ message: '{"data":"no level field"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getAllByText("INFO").length).toBe(2));
  });

  it("falls back to raw message when neither message nor msg is present in JSON", async () => {
    const event = makeEvent({ message: '{"level":"INFO","data":"no text field"}' });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText('{"level":"INFO","data":"no text field"}')).toBeTruthy());
  });

  // ---------------------------------------------------------------------------
  // Expand / collapse row
  // ---------------------------------------------------------------------------

  it("expands row on click to show full JSON", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getByText("tool called"));

    const row = screen.getByText("tool called").closest("button");
    fireEvent.click(row);
    await waitFor(() => expect(screen.getByText(/"message": "tool called"/)).toBeTruthy());
  });

  it("expands row via keyboard Enter", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getByText("tool called"));

    const row = screen.getByText("tool called").closest("button");
    fireEvent.keyDown(row, { key: "Enter" });
    await waitFor(() => expect(screen.getByText(/"message": "tool called"/)).toBeTruthy());
  });

  it("expands row via keyboard Space", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getByText("tool called"));

    const row = screen.getByText("tool called").closest("button");
    fireEvent.keyDown(row, { key: " " });
    await waitFor(() => expect(screen.getByText(/"message": "tool called"/)).toBeTruthy());
  });

  it("collapses row on second click", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getByText("tool called"));

    const row = screen.getByText("tool called").closest("button");
    fireEvent.click(row);
    await waitFor(() => screen.getByText(/"message": "tool called"/));
    fireEvent.click(row);
    await waitFor(() =>
      expect(screen.queryByText(/"message": "tool called"/)).toBeNull(),
    );
  });

  it("shows raw text in expanded view for non-JSON message", async () => {
    const event = makeEvent({ message: "plain text log line" });
    api.getLogs.mockResolvedValue({ events: [event], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getAllByText("plain text log line"));

    const row = screen.getAllByText("plain text log line")[0].closest("button");
    fireEvent.click(row);
    // raw text appears in the expanded <pre>
    await waitFor(() => expect(screen.getAllByText("plain text log line").length).toBeGreaterThan(1));
  });

  // ---------------------------------------------------------------------------
  // Controls
  // ---------------------------------------------------------------------------

  it("changes group and reloads", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());
    api.getLogs.mockClear();

    await act(async () =>
      fireEvent.change(screen.getByLabelText("Log group"), { target: { value: "mcp" } }),
    );
    await waitFor(() =>
      expect(api.getLogs).toHaveBeenCalledWith(expect.objectContaining({ group: "mcp" })),
    );
  });

  it("changes window and reloads", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());
    api.getLogs.mockClear();

    await act(async () =>
      fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "3h" } }),
    );
    await waitFor(() =>
      expect(api.getLogs).toHaveBeenCalledWith(expect.objectContaining({ window: "3h" })),
    );
  });

  it("debounces filter input and reloads", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());
    api.getLogs.mockClear();

    await act(async () =>
      fireEvent.change(screen.getByPlaceholderText("Filter pattern…"), {
        target: { value: "ERROR" },
      }),
    );
    await waitFor(
      () => expect(api.getLogs).toHaveBeenCalledWith(expect.objectContaining({ filter: "ERROR" })),
      { timeout: 1000 },
    );
  });

  it("level toggle hides events of that level", async () => {
    const infoEvent = makeEvent({ event_id: "e1", message: '{"level":"INFO","message":"info msg"}' });
    const errorEvent = makeEvent({ event_id: "e2", message: '{"level":"ERROR","message":"error msg"}' });
    api.getLogs.mockResolvedValue({ events: [infoEvent, errorEvent], next_token: null });

    await act(async () => render(<LogViewer />));
    await waitFor(() => screen.getByText("info msg"));

    // Deactivate INFO
    fireEvent.click(screen.getAllByText("INFO")[0]);
    await waitFor(() => expect(screen.queryByText("info msg")).toBeNull());
    expect(screen.getByText("error msg")).toBeTruthy();

    // Reactivate INFO
    fireEvent.click(screen.getAllByText("INFO")[0]);
    await waitFor(() => expect(screen.getByText("info msg")).toBeTruthy());
  });

  it("pause button stops polling", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Pause"));
    expect(screen.getByText("Resume")).toBeTruthy();
  });

  it("resume button re-enables polling", async () => {
    await act(async () => render(<LogViewer />));
    fireEvent.click(screen.getByText("Pause"));
    fireEvent.click(screen.getByText("Resume"));
    expect(screen.getByText("Pause")).toBeTruthy();
  });

  it("refresh button triggers reload", async () => {
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());
    api.getLogs.mockClear();

    await act(async () => fireEvent.click(screen.getByText("Refresh")));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalled());
  });

  it("shows error when getLogs fails", async () => {
    api.getLogs.mockRejectedValue(new Error("fetch failed"));
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText("fetch failed")).toBeTruthy());
  });

  it("shows event count in footer", async () => {
    api.getLogs.mockResolvedValue({ events: [makeEvent()], next_token: null });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText(/1 event shown/)).toBeTruthy());
  });

  it("shows plural event count", async () => {
    api.getLogs.mockResolvedValue({
      events: [makeEvent({ event_id: "e1" }), makeEvent({ event_id: "e2" })],
      next_token: null,
    });
    await act(async () => render(<LogViewer />));
    await waitFor(() => expect(screen.getByText(/2 events shown/)).toBeTruthy());
  });

  it("shows paused in footer when paused", async () => {
    await act(async () => render(<LogViewer />));
    fireEvent.click(screen.getByText("Pause"));
    expect(screen.getByText(/paused/)).toBeTruthy();
  });
});
