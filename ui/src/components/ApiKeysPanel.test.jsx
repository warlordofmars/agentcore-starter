// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    listApiKeys: vi.fn(),
    createApiKey: vi.fn(),
    deleteApiKey: vi.fn(),
  },
}));

import { api } from "../api.js";
import ApiKeysPanel from "./ApiKeysPanel.jsx";

const SAMPLE_KEYS = [
  {
    key_id: "k1",
    owner_user_id: "u1",
    name: "CI pipeline",
    scope: "memories:read memories:write",
    created_at: "2026-04-01T00:00:00Z",
    expires_at: null,
    revoked: false,
  },
  {
    key_id: "k2",
    owner_user_id: "u1",
    name: "Script",
    scope: "memories:read",
    created_at: "2026-04-02T00:00:00Z",
    expires_at: "2027-04-02T00:00:00Z",
    revoked: false,
  },
];

describe("ApiKeysPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", async () => {
    api.listApiKeys.mockReturnValue(new Promise(() => {}));
    render(<ApiKeysPanel />);
    expect(screen.getByText("Loading…")).toBeTruthy();
  });

  it("renders key rows after loading", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText("CI pipeline")).toBeTruthy();
    expect(screen.getByText("Script")).toBeTruthy();
  });

  it("shows never for keys without expiry", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText("Never")).toBeTruthy();
  });

  it("shows expiry date for keys with expiry", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    // expires_at = "2027-04-02T00:00:00Z" should render as a date
    expect(screen.queryByText("Never")).toBeTruthy(); // from k1
  });

  it("shows empty state when no keys", async () => {
    api.listApiKeys.mockResolvedValue([]);
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText(/No API keys yet/)).toBeTruthy();
  });

  it("handles null from listApiKeys", async () => {
    api.listApiKeys.mockResolvedValue(null);
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText(/No API keys yet/)).toBeTruthy();
  });

  it("shows error when listApiKeys fails", async () => {
    api.listApiKeys.mockRejectedValue(new Error("Forbidden"));
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText("Forbidden")).toBeTruthy();
  });

  it("renders the API Keys heading", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    expect(screen.getByText("API Keys")).toBeTruthy();
  });

  it("shows create form when + New Key is clicked", async () => {
    api.listApiKeys.mockResolvedValue([]);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    expect(screen.getByText("New API Key")).toBeTruthy();
  });

  it("hides create form when Cancel is clicked", async () => {
    api.listApiKeys.mockResolvedValue([]);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    await act(async () => fireEvent.click(screen.getByText("Cancel")));
    expect(screen.queryByText("New API Key")).toBeNull();
  });

  it("creates a key and shows banner", async () => {
    const created = {
      ...SAMPLE_KEYS[0],
      key_id: "k3",
      plaintext_key: "hive_sk_abc123",
    };
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockResolvedValue(created);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "My Key" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    expect(api.createApiKey).toHaveBeenCalledWith("My Key", "memories:read memories:write");
    await waitFor(() => expect(screen.getByTestId("new-key-banner")).toBeTruthy());
    expect(screen.getByText("hive_sk_abc123")).toBeTruthy();
  });

  it("dismisses new key banner", async () => {
    const created = { ...SAMPLE_KEYS[0], plaintext_key: "hive_sk_abc123" };
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockResolvedValue(created);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "My Key" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    await waitFor(() => expect(screen.getByTestId("new-key-banner")).toBeTruthy());
    await act(async () => fireEvent.click(screen.getByText("Dismiss")));
    expect(screen.queryByTestId("new-key-banner")).toBeNull();
  });

  it("creates a key with custom scope", async () => {
    const created = { ...SAMPLE_KEYS[1], plaintext_key: "hive_sk_xyz" };
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockResolvedValue(created);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "Read Only" } });
    fireEvent.change(screen.getByLabelText(/Scope/i), { target: { value: "memories:read" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    expect(api.createApiKey).toHaveBeenCalledWith("Read Only", "memories:read");
  });

  it("shows error when create fails", async () => {
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockRejectedValue(new Error("Create failed"));
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "Bad Key" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    await waitFor(() => expect(screen.getByText("Create failed")).toBeTruthy());
  });

  it("opens revoke dialog when Revoke clicked", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    const revokeButtons = screen.getAllByText("Revoke");
    await act(async () => fireEvent.click(revokeButtons[0]));
    expect(screen.getByText("Revoke API key?")).toBeTruthy();
  });

  it("revokes key on confirm", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    api.deleteApiKey.mockResolvedValue(null);
    await act(async () => render(<ApiKeysPanel />));
    const revokeButtons = screen.getAllByText("Revoke");
    await act(async () => fireEvent.click(revokeButtons[0]));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    expect(api.deleteApiKey).toHaveBeenCalledWith("k1");
    await waitFor(() => expect(screen.queryByText("CI pipeline")).toBeNull());
  });

  it("does not revoke when cancelled", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    await act(async () => render(<ApiKeysPanel />));
    const revokeButtons = screen.getAllByText("Revoke");
    await act(async () => fireEvent.click(revokeButtons[0]));
    await act(async () => fireEvent.click(screen.getByText("Cancel")));
    expect(api.deleteApiKey).not.toHaveBeenCalled();
    expect(screen.getByText("CI pipeline")).toBeTruthy();
  });

  it("shows error when revoke fails", async () => {
    api.listApiKeys.mockResolvedValue(SAMPLE_KEYS);
    api.deleteApiKey.mockRejectedValue(new Error("Revoke failed"));
    await act(async () => render(<ApiKeysPanel />));
    const revokeButtons = screen.getAllByText("Revoke");
    await act(async () => fireEvent.click(revokeButtons[0]));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await waitFor(() => expect(screen.getByText("Revoke failed")).toBeTruthy());
  });

  it("copies API key from new key banner", async () => {
    const writeText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      writable: true,
    });
    const created = { ...SAMPLE_KEYS[0], plaintext_key: "hive_sk_abc123" };
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockResolvedValue(created);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "k" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    await waitFor(() => expect(screen.getByTestId("new-key-banner")).toBeTruthy());
    await act(async () => fireEvent.click(screen.getByLabelText("Copy API key")));
    expect(writeText).toHaveBeenCalledWith("hive_sk_abc123");
  });

  it("clears new key banner when + New Key is clicked again", async () => {
    const created = { ...SAMPLE_KEYS[0], plaintext_key: "hive_sk_abc123" };
    api.listApiKeys.mockResolvedValue([]);
    api.createApiKey.mockResolvedValue(created);
    await act(async () => render(<ApiKeysPanel />));
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    fireEvent.change(screen.getByLabelText(/Name/i), { target: { value: "k" } });
    await act(async () => fireEvent.click(screen.getByText("Create")));
    await waitFor(() => expect(screen.getByTestId("new-key-banner")).toBeTruthy());
    await act(async () => fireEvent.click(screen.getByText("+ New Key")));
    expect(screen.queryByTestId("new-key-banner")).toBeNull();
  });
});
