// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import StatusPage from "./StatusPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("StatusPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the heading", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "1.0.0" }),
    });
    await act(async () => renderInRouter(<StatusPage />));
    expect(screen.getByText("Service status")).toBeTruthy();
  });

  it("shows operational status when health check passes", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "1.2.3" }),
    });
    await act(async () => renderInRouter(<StatusPage />));
    await waitFor(() =>
      expect(screen.getByText("All systems operational")).toBeTruthy()
    );
    expect(screen.getByText("Version 1.2.3")).toBeTruthy();
  });

  it("shows error status when health check fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network error"));
    await act(async () => renderInRouter(<StatusPage />));
    await waitFor(() =>
      expect(screen.getByText("Service unavailable")).toBeTruthy()
    );
  });

  it("shows error status when health returns non-ok HTTP status", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    });
    await act(async () => renderInRouter(<StatusPage />));
    await waitFor(() =>
      expect(screen.getByText("Service unavailable")).toBeTruthy()
    );
  });

  it("shows checked-at time after check completes", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "1.0.0" }),
    });
    await act(async () => renderInRouter(<StatusPage />));
    await waitFor(() => expect(screen.getByText(/Checked at/)).toBeTruthy());
  });

  it("refresh button triggers a new health check", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok", version: "1.0.0" }),
    });
    await act(async () => renderInRouter(<StatusPage />));
    await waitFor(() => expect(screen.getByText("Refresh")).toBeTruthy());
    await act(async () => fireEvent.click(screen.getByText("Refresh")));
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("renders GitHub issues link", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok" }),
    });
    await act(async () => renderInRouter(<StatusPage />));
    expect(screen.getByText("GitHub issues")).toBeTruthy();
  });
});
