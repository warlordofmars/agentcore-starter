// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    listUsers: vi.fn(),
    updateUserRole: vi.fn(),
    getUserStats: vi.fn(),
    getUserLimits: vi.fn(),
    updateUserLimits: vi.fn(),
    deleteUser: vi.fn(),
  },
}));

import { api } from "../api.js";
import UsersPanel from "./UsersPanel.jsx";

const SAMPLE_USERS = [
  {
    user_id: "u1",
    email: "alice@example.com",
    display_name: "Alice",
    role: "admin",
    created_at: "2026-01-01T00:00:00Z",
    last_login_at: "2026-04-01T12:00:00Z",
  },
  {
    user_id: "u2",
    email: "bob@example.com",
    display_name: "Bob",
    role: "user",
    created_at: "2026-02-01T00:00:00Z",
    last_login_at: "2026-04-02T08:30:00Z",
  },
];

describe("UsersPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", async () => {
    api.listUsers.mockReturnValue(new Promise(() => {}));
    render(<UsersPanel />);
    expect(screen.getByText("Loading…")).toBeTruthy();
  });

  it("renders user rows after loading", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("alice@example.com")).toBeTruthy();
    expect(screen.getByText("bob@example.com")).toBeTruthy();
  });

  it("shows empty state when no users", async () => {
    api.listUsers.mockResolvedValue({ items: [] });
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("No users found")).toBeTruthy();
  });

  it("shows error when listUsers fails", async () => {
    api.listUsers.mockRejectedValue(new Error("Forbidden"));
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("Forbidden")).toBeTruthy();
  });

  it("renders the Users heading", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("Users")).toBeTruthy();
  });

  it("shows empty state when listUsers returns null", async () => {
    api.listUsers.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("No users found")).toBeTruthy();
  });

  it("filters users by email", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));
    fireEvent.change(screen.getByTestId("email-search"), { target: { value: "alice" } });
    expect(screen.getByText("alice@example.com")).toBeTruthy();
    expect(screen.queryByText("bob@example.com")).toBeNull();
  });

  it("filters users by role", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));
    fireEvent.change(screen.getByTestId("role-filter"), { target: { value: "admin" } });
    expect(screen.getByText("alice@example.com")).toBeTruthy();
    expect(screen.queryByText("bob@example.com")).toBeNull();
  });

  it("shows no-match message when filters exclude all users", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));
    fireEvent.change(screen.getByTestId("email-search"), { target: { value: "zzz" } });
    expect(screen.getByText("No users match your filters.")).toBeTruthy();
  });

  it("opens confirm dialog when Delete clicked", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));

    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[0]));

    expect(screen.getByText("Delete user?")).toBeTruthy();
  });

  it("deletes user on confirm and removes row", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.deleteUser.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));

    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[0]));

    // Confirm in the dialog — last "Delete" button is the confirm
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));

    expect(api.deleteUser).toHaveBeenCalledWith("u1");
    await waitFor(() => expect(screen.queryByText("alice@example.com")).toBeNull());
  });

  it("does not delete when dialog is cancelled", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    await act(async () => render(<UsersPanel />));

    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[0]));
    await act(async () => fireEvent.click(screen.getByText("Cancel")));

    expect(api.deleteUser).not.toHaveBeenCalled();
    expect(screen.getByText("alice@example.com")).toBeTruthy();
  });

  it("shows error when delete fails", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.deleteUser.mockRejectedValue(new Error("Delete failed"));
    await act(async () => render(<UsersPanel />));

    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[0]));
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));

    await waitFor(() => expect(screen.getByText("Delete failed")).toBeTruthy());
  });

  it("shows Load more button when has_more is true", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS, has_more: true, next_cursor: "tok1" });
    await act(async () => render(<UsersPanel />));
    expect(screen.getByText("Load more")).toBeTruthy();
  });

  it("does not show Load more button when has_more is false", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS, has_more: false });
    await act(async () => render(<UsersPanel />));
    expect(screen.queryByText("Load more")).toBeNull();
  });

  it("loads more users on button click", async () => {
    const extra = [{
      user_id: "u3",
      email: "carol@example.com",
      display_name: "Carol",
      role: "user",
      created_at: "2026-03-01T00:00:00Z",
      last_login_at: "2026-04-03T00:00:00Z",
    }];
    api.listUsers
      .mockResolvedValueOnce({ items: SAMPLE_USERS, has_more: true, next_cursor: "tok1" })
      .mockResolvedValueOnce({ items: extra, has_more: false, next_cursor: null });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("Load more")));
    expect(screen.getByText("carol@example.com")).toBeTruthy();
  });

  it("shows error when loadMore fails", async () => {
    api.listUsers
      .mockResolvedValueOnce({ items: SAMPLE_USERS, has_more: true, next_cursor: "tok1" })
      .mockRejectedValueOnce(new Error("Load failed"));
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("Load more")));
    await waitFor(() => expect(screen.getByText("Load failed")).toBeTruthy());
  });

  it("handles loadMore returning null gracefully", async () => {
    api.listUsers
      .mockResolvedValueOnce({ items: SAMPLE_USERS, has_more: true, next_cursor: "tok1" })
      .mockResolvedValueOnce(null);
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("Load more")));
    // no crash; original users still visible
    expect(screen.getByText("alice@example.com")).toBeTruthy();
  });

  it("deletes user without open detail panel does not crash", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.deleteUser.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));
    // Delete without opening detail panel first
    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[0]));
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));
    await waitFor(() => expect(screen.queryByText("alice@example.com")).toBeNull());
  });

  it("deletes a different user while detail panel is open does not close panel", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.deleteUser.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));
    // Open detail for alice
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    // Delete bob (not alice) — via table button
    const deleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(deleteButtons[1]));
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));
    await waitFor(() => expect(screen.queryByText("bob@example.com")).toBeNull());
    // Alice's detail panel should still be open
    expect(screen.getByTestId("user-detail")).toBeTruthy();
  });

  it("closes detail panel when deleting the same user via table row button", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.deleteUser.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));
    // Open alice's detail panel
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    expect(screen.getByTestId("user-detail")).toBeTruthy();
    // Delete alice via the TABLE row Delete button (not the panel button)
    const tableDeleteButtons = screen.getAllByText("Delete");
    await act(async () => fireEvent.click(tableDeleteButtons[0]));
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));
    await waitFor(() => expect(screen.queryByTestId("user-detail")).toBeNull());
  });

  it("opens detail panel when row is clicked", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 5, client_count: 2 });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    expect(screen.getByTestId("user-detail")).toBeTruthy();
    expect(screen.getByText("Alice")).toBeTruthy();
  });

  it("shows stats in detail panel", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 5, client_count: 2 });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByText("Memories")).toBeTruthy());
    expect(screen.getByText("Clients")).toBeTruthy();
  });

  it("hides stats section when getUserStats fails", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockRejectedValue(new Error("Stats unavailable"));
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.queryByText("Memories")).toBeNull());
  });

  it("closes detail panel on X click", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await act(async () => fireEvent.click(screen.getByLabelText("Close detail panel")));
    expect(screen.queryByTestId("user-detail")).toBeNull();
  });

  it("updates role when changed in detail panel", async () => {
    const updatedAlice = { ...SAMPLE_USERS[0], role: "user" };
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.updateUserRole.mockResolvedValue(updatedAlice);
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    const detailPanel = screen.getByTestId("user-detail");
    const roleSelect = detailPanel.querySelector("select");
    await act(async () => fireEvent.change(roleSelect, { target: { value: "user" } }));
    expect(api.updateUserRole).toHaveBeenCalledWith("u1", "user");
  });

  it("shows error when role update fails", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.updateUserRole.mockRejectedValue(new Error("Role update failed"));
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    const detailPanel = screen.getByTestId("user-detail");
    const roleSelect = detailPanel.querySelector("select");
    await act(async () => fireEvent.change(roleSelect, { target: { value: "user" } }));
    await waitFor(() => expect(screen.getByText("Role update failed")).toBeTruthy());
  });

  it("opens delete dialog from detail panel delete button", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await act(async () => fireEvent.click(screen.getByText("Delete user")));
    expect(screen.getByText("Delete user?")).toBeTruthy();
  });

  it("closes detail panel after deleting from it", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.deleteUser.mockResolvedValue(null);
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await act(async () => fireEvent.click(screen.getByText("Delete user")));
    // Confirm
    await act(async () => fireEvent.click(screen.getAllByText("Delete").at(-1)));
    await waitFor(() => expect(screen.queryByTestId("user-detail")).toBeNull());
  });

  it("shows limits section when getUserLimits returns data", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 5, client_count: 2 });
    api.getUserLimits.mockResolvedValue({
      user_id: "u1",
      memory_limit: null,
      storage_bytes_limit: null,
      effective_memory_limit: 500,
      effective_storage_bytes_limit: 104857600,
    });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByTestId("limits-section")).toBeTruthy());
    expect(screen.getByText(/Quota overrides/)).toBeTruthy();
    expect(screen.getByTestId("memory-limit-input")).toBeTruthy();
    expect(screen.getByTestId("storage-limit-input")).toBeTruthy();
    expect(screen.getByTestId("save-limits-btn")).toBeTruthy();
  });

  it("hides limits section when getUserLimits fails", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockRejectedValue(new Error("fail"));
    api.getUserLimits.mockRejectedValue(new Error("fail"));
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.queryByTestId("limits-section")).toBeNull());
  });

  it("saves limits on Save limits button click", async () => {
    const updatedLimits = {
      user_id: "u1",
      memory_limit: 200,
      storage_bytes_limit: null,
      effective_memory_limit: 200,
      effective_storage_bytes_limit: 104857600,
    };
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.getUserLimits.mockResolvedValue({
      user_id: "u1",
      memory_limit: null,
      storage_bytes_limit: null,
      effective_memory_limit: 500,
      effective_storage_bytes_limit: 104857600,
    });
    api.updateUserLimits.mockResolvedValue(updatedLimits);

    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByTestId("limits-section")).toBeTruthy());

    fireEvent.change(screen.getByTestId("memory-limit-input"), { target: { value: "200" } });
    await act(async () => fireEvent.click(screen.getByTestId("save-limits-btn")));

    expect(api.updateUserLimits).toHaveBeenCalledWith("u1", {
      memory_limit: 200,
      storage_bytes_limit: null,
    });
  });

  it("shows error when save limits fails", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.getUserLimits.mockResolvedValue({
      user_id: "u1",
      memory_limit: null,
      storage_bytes_limit: null,
      effective_memory_limit: 500,
      effective_storage_bytes_limit: 104857600,
    });
    api.updateUserLimits.mockRejectedValue(new Error("Save failed"));

    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByTestId("limits-section")).toBeTruthy());
    await act(async () => fireEvent.click(screen.getByTestId("save-limits-btn")));

    await waitFor(() => expect(screen.getByText("Save failed")).toBeTruthy());
  });

  it("populates input fields with existing overrides on open", async () => {
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.getUserLimits.mockResolvedValue({
      user_id: "u1",
      memory_limit: 250,
      storage_bytes_limit: 52428800,
      effective_memory_limit: 250,
      effective_storage_bytes_limit: 52428800,
    });
    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByTestId("limits-section")).toBeTruthy());
    expect(screen.getByTestId("memory-limit-input").value).toBe("250");
    expect(screen.getByTestId("storage-limit-input").value).toBe("52428800");
  });

  it("saves limits with non-empty storage bytes value", async () => {
    const updatedLimits = {
      user_id: "u1",
      memory_limit: null,
      storage_bytes_limit: 52428800,
      effective_memory_limit: 500,
      effective_storage_bytes_limit: 52428800,
    };
    api.listUsers.mockResolvedValue({ items: SAMPLE_USERS });
    api.getUserStats.mockResolvedValue({ user_id: "u1", memory_count: 0, client_count: 0 });
    api.getUserLimits.mockResolvedValue({
      user_id: "u1",
      memory_limit: null,
      storage_bytes_limit: null,
      effective_memory_limit: 500,
      effective_storage_bytes_limit: 104857600,
    });
    api.updateUserLimits.mockResolvedValue(updatedLimits);

    await act(async () => render(<UsersPanel />));
    await act(async () => fireEvent.click(screen.getByText("alice@example.com")));
    await waitFor(() => expect(screen.getByTestId("limits-section")).toBeTruthy());

    fireEvent.change(screen.getByTestId("storage-limit-input"), { target: { value: "52428800" } });
    await act(async () => fireEvent.click(screen.getByTestId("save-limits-btn")));

    expect(api.updateUserLimits).toHaveBeenCalledWith("u1", {
      memory_limit: null,
      storage_bytes_limit: 52428800,
    });
  });
});
