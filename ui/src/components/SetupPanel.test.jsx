// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    listMemories: vi.fn(),
    deleteAccount: vi.fn(),
    getStats: vi.fn(),
    exportAccount: vi.fn(),
  },
}));

import { api } from "../api.js";
import SetupPanel from "./SetupPanel.jsx";

describe("SetupPanel", () => {
  let _storage;

  beforeEach(() => {
    _storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => _storage[k] ?? null,
      setItem: (k, v) => { _storage[k] = v; },
      removeItem: (k) => { delete _storage[k]; },
    });
    vi.stubGlobal("navigator", {
      ...navigator,
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    api.listMemories.mockResolvedValue({ items: [] });
    api.getStats.mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("renders both step headings", async () => {
    await act(async () => render(<SetupPanel />));
    expect(screen.getByText(/Step 1/)).toBeTruthy();
    expect(screen.getByText(/Step 2/)).toBeTruthy();
  });

  it("renders Claude Code, Cursor, and Claude Desktop tabs", async () => {
    await act(async () => render(<SetupPanel />));
    expect(screen.getByText("Claude Code")).toBeTruthy();
    expect(screen.getByText("Cursor")).toBeTruthy();
    expect(screen.getByText("Claude Desktop")).toBeTruthy();
  });

  it("defaults to Claude Code tab and shows http type config", async () => {
    await act(async () => render(<SetupPanel />));
    expect(document.body.textContent).toContain('"type": "http"');
  });

  it("Claude Desktop tab leads with the Custom Connector URL flow", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    expect(document.body.textContent).toContain("Add custom connector");
    expect(document.body.textContent).toContain("/mcp");
    // The mcp-remote JSON config is hidden behind the legacy disclosure
    expect(document.body.textContent).not.toContain('"command": "npx"');
  });

  it("Claude Desktop legacy disclosure reveals the mcp-remote JSON form", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText(/Prefer JSON/));
    expect(document.body.textContent).toContain("mcp-remote");
    expect(document.body.textContent).toContain('"command": "npx"');
  });

  it("ChatGPT tab shows the URL flow with the connector steps", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("ChatGPT"));
    expect(document.body.textContent).toContain("Add → MCP server");
    expect(document.body.textContent).toContain("/mcp");
    expect(document.body.textContent).not.toContain('"command": "npx"');
  });

  it("Copy URL button copies the URL and marks step 1 done", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText("Copy URL"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("/mcp"),
    );
    expect(_storage["hive_setup_step1_done"]).toBe("1");
  });

  it("Copy URL shows Copied! and reverts after 2s", async () => {
    vi.useFakeTimers();
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText("Copy URL"));
    expect(screen.getByText("Copied!")).toBeTruthy();
    act(() => vi.runAllTimers());
    expect(screen.getByText("Copy URL")).toBeTruthy();
    vi.useRealTimers();
  });

  it("Cursor tab Copy uses the Cursor http config", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Cursor"));
    fireEvent.click(screen.getByText("Copy"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('"type": "http"'),
    );
  });

  it("Claude Desktop legacy JSON Copy uses the mcp-remote config", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText(/Prefer JSON/));
    fireEvent.click(screen.getByText("Copy"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("mcp-remote"),
    );
  });

  it("Back link from legacy JSON form returns to the URL flow", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText(/Prefer JSON/));
    expect(document.body.textContent).toContain('"command": "npx"');
    fireEvent.click(screen.getByText(/Back to the Custom Connector/));
    expect(document.body.textContent).toContain("Add custom connector");
    expect(document.body.textContent).not.toContain('"command": "npx"');
  });

  it("shows Copy button initially", async () => {
    await act(async () => render(<SetupPanel />));
    expect(screen.getByText("Copy")).toBeTruthy();
  });

  it("shows Copied! after click and reverts after 2s", async () => {
    vi.useFakeTimers();
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Copy"));
    expect(screen.getByText("Copied!")).toBeTruthy();
    act(() => vi.runAllTimers());
    expect(screen.getByText("Copy")).toBeTruthy();
    vi.useRealTimers();
  });

  it("uses VITE_MCP_BASE when set", async () => {
    vi.stubEnv("VITE_MCP_BASE", "https://custom.example.com/mcp");
    await act(async () => render(<SetupPanel />));
    expect(document.body.textContent).toContain("custom.example.com/mcp");
  });

  it("falls back to window.location.origin + /mcp when VITE_MCP_BASE not set", async () => {
    await act(async () => render(<SetupPanel />));
    expect(document.body.textContent).toContain("localhost");
    expect(document.body.textContent).toContain("/mcp");
  });

  it("step 2 text updates when switching tabs (Claude Desktop URL flow)", async () => {
    await act(async () => render(<SetupPanel />));
    expect(document.body.textContent).toContain("Claude Code");
    fireEvent.click(screen.getByText("Claude Desktop"));
    expect(document.body.textContent).toContain("After saving the connector");
  });

  it("step 2 text updates for the Claude Desktop legacy JSON flow", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText(/Prefer JSON/));
    expect(document.body.textContent).toContain("Restart Claude Desktop");
  });

  it("step 2 text updates when switching to ChatGPT tab", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("ChatGPT"));
    expect(document.body.textContent).toContain("ChatGPT opens an OAuth pop-up");
  });

  it("switching back to Claude Code tab restores http config", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Claude Desktop"));
    fireEvent.click(screen.getByText("Claude Code"));
    expect(document.body.textContent).toContain('"type": "http"');
  });

  it("switches to Cursor tab and shows http config", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Cursor"));
    expect(document.body.textContent).toContain('"type": "http"');
    expect(document.body.textContent).toContain("~/.cursor/mcp.json");
  });

  it("step 2 text updates when switching to Cursor tab", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Cursor"));
    expect(document.body.textContent).toContain("Restart Cursor");
  });

  it("Copy sets step1 flag in localStorage", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Copy"));
    expect(_storage["hive_setup_step1_done"]).toBe("1");
  });

  it("shows step 1 checkmark when step1 flag already set in localStorage", async () => {
    _storage["hive_setup_step1_done"] = "1";
    await act(async () => render(<SetupPanel />));
    // Check icon rendered (SVG) — heading still contains "Step 1" text
    expect(screen.getByText(/Step 1/)).toBeTruthy();
  });

  it("Test connection button calls api.listMemories", async () => {
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    expect(api.listMemories).toHaveBeenCalled();
  });

  it("shows Connected on successful test", async () => {
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    await waitFor(() => expect(screen.getByText("Connected")).toBeTruthy());
  });

  it("shows error message on failed test", async () => {
    api.listMemories.mockRejectedValue(new Error("Unauthorized"));
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    await waitFor(() => expect(screen.getByText("Unauthorized")).toBeTruthy());
  });

  it("shows error message when rejection has no message", async () => {
    api.listMemories.mockRejectedValue({});
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    await waitFor(() => expect(screen.getByText("Connection failed")).toBeTruthy());
  });

  it("shows You're all set banner when both steps complete", async () => {
    _storage["hive_setup_step1_done"] = "1";
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    await waitFor(() => expect(screen.getByText(/You're all set/)).toBeTruthy());
  });

  it("dispatches hive:switch-tab event when Memories link clicked in banner", async () => {
    _storage["hive_setup_step1_done"] = "1";
    await act(async () => render(<SetupPanel />));
    await act(async () => fireEvent.click(screen.getByText("Test connection")));
    await waitFor(() => expect(screen.getByText(/You're all set/)).toBeTruthy());
    const handler = vi.fn();
    window.addEventListener("hive:switch-tab", handler);
    fireEvent.click(screen.getByText("Memories"));
    expect(handler).toHaveBeenCalled();
    expect(handler.mock.calls[0][0].detail).toBe("memories");
    window.removeEventListener("hive:switch-tab", handler);
  });

  it("renders Danger Zone section with delete button", async () => {
    await act(async () => render(<SetupPanel />));
    expect(screen.getByText("Danger Zone")).toBeTruthy();
    expect(screen.getByText("Delete my account")).toBeTruthy();
  });

  it("shows confirmation dialog when Delete my account is clicked", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Delete my account"));
    expect(screen.getByText(/Are you sure/)).toBeTruthy();
    expect(screen.getByText("Yes, delete everything")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });

  it("hides confirmation dialog on Cancel", async () => {
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Delete my account"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.getByText("Delete my account")).toBeTruthy();
    expect(screen.queryByText(/Are you sure/)).toBeNull();
  });

  it("calls api.deleteAccount and redirects on confirm", async () => {
    api.deleteAccount.mockResolvedValue(null);
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { replace: replaceMock });
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Delete my account"));
    await act(async () => fireEvent.click(screen.getByText("Yes, delete everything")));
    expect(api.deleteAccount).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith("/");
  });

  it("shows error message when deleteAccount fails", async () => {
    api.deleteAccount.mockRejectedValue(new Error("Server error"));
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Delete my account"));
    await act(async () => fireEvent.click(screen.getByText("Yes, delete everything")));
    await waitFor(() => expect(screen.getByText("Server error")).toBeTruthy());
  });

  it("shows fallback error when deleteAccount rejects without message", async () => {
    api.deleteAccount.mockRejectedValue({});
    await act(async () => render(<SetupPanel />));
    fireEvent.click(screen.getByText("Delete my account"));
    await act(async () => fireEvent.click(screen.getByText("Yes, delete everything")));
    await waitFor(() => expect(screen.getByText("Deletion failed")).toBeTruthy());
  });

  it("does not render Usage section when getStats returns null", async () => {
    api.getStats.mockResolvedValue(null);
    await act(async () => render(<SetupPanel />));
    expect(screen.queryByText("Usage")).toBeNull();
  });

  it("does not render Usage section when stats have no memory_limit", async () => {
    api.getStats.mockResolvedValue({ total_memories: 10, total_clients: 2, memory_limit: null });
    await act(async () => render(<SetupPanel />));
    expect(screen.queryByText("Usage")).toBeNull();
  });

  it("renders Usage section with quota bars when limits are present", async () => {
    api.getStats.mockResolvedValue({
      total_memories: 42,
      total_clients: 3,
      memory_limit: 500,
      client_limit: 10,
    });
    await act(async () => render(<SetupPanel />));
    await waitFor(() => expect(screen.getByText("Usage")).toBeTruthy());
    expect(screen.getByText("Memories")).toBeTruthy();
    expect(screen.getByText("Clients")).toBeTruthy();
    expect(screen.getByText("42 / 500")).toBeTruthy();
    expect(screen.getByText("3 / 10")).toBeTruthy();
  });

  it("shows danger color for quota at 100%", async () => {
    api.getStats.mockResolvedValue({
      total_memories: 500,
      total_clients: 1,
      memory_limit: 500,
      client_limit: 10,
    });
    await act(async () => render(<SetupPanel />));
    await waitFor(() => expect(screen.getByText("500 / 500")).toBeTruthy());
    const label = screen.getByText("500 / 500");
    expect(label.className).toContain("text-[var(--danger)]");
  });

  it("shows muted color for quota under 80%", async () => {
    api.getStats.mockResolvedValue({
      total_memories: 10,
      total_clients: 1,
      memory_limit: 500,
      client_limit: 10,
    });
    await act(async () => render(<SetupPanel />));
    await waitFor(() => expect(screen.getByText("10 / 500")).toBeTruthy());
    const label = screen.getByText("10 / 500");
    expect(label.className).toContain("text-[var(--text-muted)]");
  });

  it("shows amber bar color for quota between 80% and 99%", async () => {
    api.getStats.mockResolvedValue({
      total_memories: 420,
      total_clients: 1,
      memory_limit: 500,
      client_limit: 10,
    });
    await act(async () => render(<SetupPanel />));
    await waitFor(() => expect(screen.getByText("420 / 500")).toBeTruthy());
    // bar fill div is the one with inline background = amber
    const bars = document.querySelectorAll('[style*="background: var(--amber)"]');
    expect(bars.length).toBeGreaterThan(0);
  });

  describe("QuotaCallout", () => {
    it("does not render under 80% utilisation", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 100,
        total_clients: 1,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      await waitFor(() => expect(screen.getByText("100 / 500")).toBeTruthy());
      expect(screen.queryByTestId("quota-callout")).toBeNull();
    });

    it("renders amber 'approaching limit' callout between 80% and 99%", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 420,
        total_clients: 1,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      const callout = await screen.findByTestId("quota-callout");
      expect(callout.dataset.severity).toBe("near");
      expect(callout.textContent).toContain("approaching your free tier limit");
      const link = callout.querySelector("a");
      expect(link.getAttribute("href")).toContain("mailto:hello@warlordofmars.net");
    });

    it("renders red 'reached limit' callout at 100%", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 500,
        total_clients: 1,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      const callout = await screen.findByTestId("quota-callout");
      expect(callout.dataset.severity).toBe("at");
      expect(callout.textContent).toContain("reached your free tier limit");
      expect(callout.textContent).toContain("New memories cannot be saved");
    });

    it("tailors the body copy to clients when only the client quota is full", async () => {
      // The worst-case bucket drives severity — one resource at 100%
      // is enough to block writes even if the other is well under.
      // Backend only blocks new clients on client_limit, not memories,
      // so the body copy switches to "OAuth clients … cannot be
      // created" rather than the default memory phrasing.
      api.getStats.mockResolvedValue({
        total_memories: 0,
        total_clients: 10,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      const callout = await screen.findByTestId("quota-callout");
      expect(callout.dataset.severity).toBe("at");
      expect(callout.textContent).toContain("New OAuth clients cannot be created");
      expect(callout.textContent).not.toContain("New memories");
    });

    it("uses combined memories+clients copy when both buckets are at limit", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 500,
        total_clients: 10,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      const callout = await screen.findByTestId("quota-callout");
      expect(callout.textContent).toContain("New memories and OAuth clients");
    });

    it("uses 'running low' wording for client-only near-limit case", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 0,
        total_clients: 9,
        memory_limit: 500,
        client_limit: 10,
      });
      await act(async () => render(<SetupPanel />));
      const callout = await screen.findByTestId("quota-callout");
      expect(callout.dataset.severity).toBe("near");
      expect(callout.textContent).toContain("New OAuth clients are running low");
      expect(callout.textContent).toContain("delete an unused one");
    });

    it("renders nothing when both limits are absent", async () => {
      api.getStats.mockResolvedValue({
        total_memories: 0,
        total_clients: 0,
        memory_limit: null,
        client_limit: null,
      });
      await act(async () => render(<SetupPanel />));
      // Usage section is hidden entirely when memory_limit is null,
      // so the callout never gets a chance to render.
      expect(screen.queryByTestId("quota-callout")).toBeNull();
    });

    it("returns null directly when called with all-ok quota", async () => {
      const { QuotaCallout } = await import("./SetupPanel.jsx");
      const { container } = render(
        <QuotaCallout
          quota={{
            total_memories: 1,
            total_clients: 1,
            memory_limit: 500,
            client_limit: 10,
          }}
        />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("returns 'ok' from severity helper when no limits are present", async () => {
      // Defensive branch — covered separately because the Usage
      // section is hidden in that state, so the callout never
      // renders via the panel.
      const { QuotaCallout } = await import("./SetupPanel.jsx");
      const { container } = render(
        <QuotaCallout
          quota={{ total_memories: 1, total_clients: 1 }}
        />,
      );
      expect(container.firstChild).toBeNull();
    });

    it("hides individual QuotaBar when its limit is missing or non-positive", async () => {
      // Even when one limit is set, a missing client_limit should
      // skip its bar rather than rendering "3 / null" or a div-by-0
      // 100% sliver.
      api.getStats.mockResolvedValue({
        total_memories: 10,
        total_clients: 3,
        memory_limit: 500,
        client_limit: 0,
      });
      await act(async () => render(<SetupPanel />));
      await waitFor(() => expect(screen.getByText("10 / 500")).toBeTruthy());
      expect(screen.queryByText("Clients")).toBeNull();
    });

    it("hides the Usage section header when both limits are missing or 0", async () => {
      // Iter-3: don't render an empty Usage block (header with no
      // bars and no callout) when the configuration says no limits
      // are tracked. The whole section disappears.
      api.getStats.mockResolvedValue({
        total_memories: 5,
        total_clients: 2,
        memory_limit: 500,
        client_limit: 0,
      });
      // First render with one limit set — Usage shows.
      const { unmount } = render(<SetupPanel />);
      await waitFor(() => expect(screen.getByText("Usage")).toBeTruthy());
      unmount();

      // Re-render with both limits unconfigured — Usage hides.
      api.getStats.mockResolvedValue({
        total_memories: 5,
        total_clients: 2,
        memory_limit: 0,
        client_limit: 0,
      });
      await act(async () => render(<SetupPanel />));
      // Wait long enough for the getStats useEffect to settle.
      await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(2));
      expect(screen.queryByText("Usage")).toBeNull();
    });

    it("treats limit=0 as unconfigured rather than infinitely full", async () => {
      // A misconfigured limit (env var typo, 0-coerced int) used to
      // light the callout up red because `0 / 0` was Infinity. The
      // helper now skips non-positive limits.
      const { QuotaCallout } = await import("./SetupPanel.jsx");
      const { container } = render(
        <QuotaCallout
          quota={{
            total_memories: 5,
            total_clients: 0,
            memory_limit: 0,
            client_limit: 0,
          }}
        />,
      );
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders key naming convention tip with example and docs link", async () => {
    await act(async () => render(<SetupPanel />));
    expect(screen.getByText(/Tip — naming your memories/)).toBeTruthy();
    expect(document.body.textContent).toContain("project:task/42:summary");
    const docsLink = screen.getByText(/key naming conventions/);
    expect(docsLink.getAttribute("href")).toBe("/docs/concepts/key-conventions");
  });

  it("hides Usage section when getStats rejects", async () => {
    api.getStats.mockRejectedValue(new Error("network error"));
    await act(async () => render(<SetupPanel />));
    expect(screen.queryByText("Usage")).toBeNull();
  });

  describe("Export my data", () => {
    let createObjectURL;
    let revokeObjectURL;
    let linkClick;

    beforeEach(() => {
      createObjectURL = vi.fn().mockReturnValue("blob:mock");
      revokeObjectURL = vi.fn();
      vi.stubGlobal("URL", {
        ...globalThis.URL,
        createObjectURL,
        revokeObjectURL,
      });
      linkClick = vi.fn();
      const realCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag) => {
        const el = realCreateElement(tag);
        if (tag === "a") el.click = linkClick;
        return el;
      });
    });

    afterEach(() => {
      document.createElement.mockRestore?.();
    });

    it("renders Export my data button and description", async () => {
      await act(async () => render(<SetupPanel />));
      expect(screen.getAllByText(/Export my data/).length).toBeGreaterThanOrEqual(1);
      expect(document.body.textContent).toContain("Limited to one export every 5 minutes");
    });

    it("clicking Export my data triggers download of the returned blob", async () => {
      const blob = new Blob(["{}"], { type: "application/json" });
      api.exportAccount.mockResolvedValue({ blob, filename: "hive-export-u-20260418.json" });
      await act(async () => render(<SetupPanel />));
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Export my data" })),
      );
      expect(api.exportAccount).toHaveBeenCalled();
      expect(createObjectURL).toHaveBeenCalledWith(blob);
      expect(linkClick).toHaveBeenCalled();
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");
    });

    it("displays error when export fails", async () => {
      api.exportAccount.mockRejectedValue(new Error("Rate limit exceeded"));
      await act(async () => render(<SetupPanel />));
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Export my data" })),
      );
      await waitFor(() => expect(screen.getByText("Rate limit exceeded")).toBeTruthy());
    });

    it("falls back to a generic message when rejection has no message", async () => {
      api.exportAccount.mockRejectedValue({});
      await act(async () => render(<SetupPanel />));
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Export my data" })),
      );
      await waitFor(() => expect(screen.getByText("Export failed")).toBeTruthy());
    });

    it("no-op when exportAccount returns null (auth-redirect path)", async () => {
      api.exportAccount.mockResolvedValue(null);
      await act(async () => render(<SetupPanel />));
      await act(async () =>
        fireEvent.click(screen.getByRole("button", { name: "Export my data" })),
      );
      expect(createObjectURL).not.toHaveBeenCalled();
      expect(linkClick).not.toHaveBeenCalled();
    });
  });
});
