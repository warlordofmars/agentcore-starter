// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ClientManager from "./ClientManager.jsx";

vi.mock("../api.js", () => ({
  api: {
    listClients: vi.fn(),
    createClient: vi.fn(),
    deleteClient: vi.fn(),
  },
}));

import { api } from "../api.js";

const makeClient = (overrides = {}) => ({
  client_id: "c1",
  client_name: "Test App",
  token_endpoint_auth_method: "none",
  scope: "memories:read",
  client_id_issued_at: Math.floor(Date.now() / 1000),
  ...overrides,
});

describe("ClientManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listClients.mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders heading and Register button", async () => {
    await act(async () => render(<ClientManager />));
    expect(screen.getByText("OAuth Clients")).toBeTruthy();
    expect(screen.getByText("+ Register Client")).toBeTruthy();
  });

  it("shows empty state when no clients", async () => {
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("No clients registered")).toBeTruthy());
  });

  it("renders loaded clients in table", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("Test App")).toBeTruthy());
  });

  it("shows 'public' for none auth method client", async () => {
    api.listClients.mockResolvedValue({
      items: [makeClient({ token_endpoint_auth_method: "none" })],
    });
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("public")).toBeTruthy());
  });

  it("shows 'confidential' for client_secret_post auth method", async () => {
    api.listClients.mockResolvedValue({
      items: [makeClient({ token_endpoint_auth_method: "client_secret_post" })],
    });
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("confidential")).toBeTruthy());
  });

  it("shows error when listClients fails", async () => {
    api.listClients.mockRejectedValue(new Error("Network error"));
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("Network error")).toBeTruthy());
  });

  // ---------------------------------------------------------------------------
  // Registration form
  // ---------------------------------------------------------------------------

  it("opens registration form on button click", async () => {
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    expect(screen.getByText("Register New Client (RFC 7591)")).toBeTruthy();
  });

  it("closes registration form on Cancel", async () => {
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Register New Client (RFC 7591)")).toBeNull();
  });

  it("creates client and shows credentials on success (no secret)", async () => {
    api.createClient.mockResolvedValue({
      client_id: "new-id",
      client_name: "New App",
      client_secret: null,
    });
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    fireEvent.change(screen.getByPlaceholderText("My Agent"), {
      target: { value: "New App" },
    });
    await act(async () => fireEvent.submit(screen.getByText("Register").closest("form")));
    await waitFor(() => expect(screen.getByText("Client registered successfully.")).toBeTruthy());
    expect(screen.getByText("new-id")).toBeTruthy();
    expect(screen.queryByText(/Client Secret/)).toBeNull();
  });

  it("shows client secret when confidential client created", async () => {
    api.createClient.mockResolvedValue({
      client_id: "new-id",
      client_name: "Conf App",
      client_secret: "super-secret",
    });
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    fireEvent.change(screen.getByPlaceholderText("My Agent"), {
      target: { value: "Conf App" },
    });
    await act(async () => fireEvent.submit(screen.getByText("Register").closest("form")));
    await waitFor(() => expect(screen.getByText("super-secret")).toBeTruthy());
  });

  it("dismisses new-client notification on Dismiss click", async () => {
    api.createClient.mockResolvedValue({ client_id: "x", client_name: "X", client_secret: null });
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    fireEvent.change(screen.getByPlaceholderText("My Agent"), { target: { value: "X" } });
    await act(async () => fireEvent.submit(screen.getByText("Register").closest("form")));
    await waitFor(() => expect(screen.getByText("Dismiss")).toBeTruthy());
    fireEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByText("Client registered successfully.")).toBeNull();
  });

  it("fills all form fields before submitting", async () => {
    api.createClient.mockResolvedValue({ client_id: "x", client_name: "X", client_secret: null });
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));

    fireEvent.change(screen.getByPlaceholderText("My Agent"), { target: { value: "My App" } });
    fireEvent.change(screen.getByPlaceholderText("http://localhost:3000/callback"), {
      target: { value: "https://app.example.com/cb" },
    });
    fireEvent.change(screen.getByDisplayValue("memories:read memories:write"), {
      target: { value: "memories:read" },
    });
    fireEvent.change(screen.getByDisplayValue("none (public)"), {
      target: { value: "client_secret_post" },
    });
    await act(async () => fireEvent.submit(screen.getByText("Register").closest("form")));
    expect(api.createClient).toHaveBeenCalledWith(
      expect.objectContaining({
        client_name: "My App",
        redirect_uris: ["https://app.example.com/cb"],
        scope: "memories:read",
        token_endpoint_auth_method: "client_secret_post",
      }),
    );
  });

  it("handles API returning no items key gracefully", async () => {
    api.listClients.mockResolvedValue({});
    await act(async () => render(<ClientManager />));
    await waitFor(() => expect(screen.getByText("No clients registered")).toBeTruthy());
  });

  it("shows error when createClient fails", async () => {
    api.createClient.mockRejectedValue(new Error("Create failed"));
    await act(async () => render(<ClientManager />));
    fireEvent.click(screen.getByText("+ Register Client"));
    fireEvent.change(screen.getByPlaceholderText("My Agent"), {
      target: { value: "Bad App" },
    });
    await act(async () => fireEvent.submit(screen.getByText("Register").closest("form")));
    await waitFor(() => expect(screen.getByText("Create failed")).toBeTruthy());
  });

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------

  it("opens confirm dialog when Delete clicked", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    expect(screen.getByText("Delete OAuth client?")).toBeTruthy();
  });

  it("deletes a client when confirmed", async () => {
    api.listClients
      .mockResolvedValueOnce({ items: [makeClient()] })
      .mockResolvedValue({ items: [] });
    api.deleteClient.mockResolvedValue(null);
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () =>
      fireEvent.click(screen.getAllByText("Delete").at(-1)),
    );
    expect(api.deleteClient).toHaveBeenCalledWith("c1");
  });

  it("does not delete when dialog is cancelled", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () => fireEvent.click(screen.getByText("Cancel")));
    expect(api.deleteClient).not.toHaveBeenCalled();
  });

  it("shows error when deleteClient fails", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    api.deleteClient.mockRejectedValue(new Error("Delete failed"));
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () =>
      fireEvent.click(screen.getAllByText("Delete").at(-1)),
    );
    await waitFor(() => expect(screen.getByText("Delete failed")).toBeTruthy());
  });

  // ---------------------------------------------------------------------------
  // Copy client ID
  // ---------------------------------------------------------------------------

  it("renders copy button for each client", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    expect(screen.getByRole("button", { name: /copy client id/i })).toBeTruthy();
  });

  it("copies client ID to clipboard and shows check icon on click", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient({ client_id: "abc-123" })] });
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    fireEvent.click(screen.getByRole("button", { name: /copy client id/i }));
    expect(writeText).toHaveBeenCalledWith("abc-123");
  });

  it("copy button reverts after 2 seconds", async () => {
    api.listClients.mockResolvedValue({ items: [makeClient()] });
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    await act(async () => render(<ClientManager />));
    await waitFor(() => screen.getByText("Test App"));
    // Switch to fake timers only after initial load is complete
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: /copy client id/i }));
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByRole("button", { name: /copy client id/i })).toBeTruthy();
    vi.useRealTimers();
  });
});
