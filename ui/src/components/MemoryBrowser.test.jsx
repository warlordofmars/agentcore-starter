// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MemoryBrowser, { MemoryImage, TagPicker, formatBytes, typeBadgeLabel } from "./MemoryBrowser.jsx";

vi.mock("../api.js", () => ({
  api: {
    listMemories: vi.fn(),
    searchMemories: vi.fn(),
    createMemory: vi.fn(),
    updateMemory: vi.fn(),
    deleteMemory: vi.fn(),
    listMemoryVersions: vi.fn(),
    restoreMemoryVersion: vi.fn(),
    listClients: vi.fn(),
    getMemoryContent: vi.fn(),
  },
}));

import { api } from "../api.js";

const makeMemory = (overrides = {}) => ({
  memory_id: "m1",
  key: "test-key",
  value: "test-value",
  tags: ["tag1"],
  ...overrides,
});

// ------------------------------------------------------------------
// TagPicker — isolated unit tests
// ------------------------------------------------------------------

describe("TagPicker", () => {
  const tags = ["alpha", "beta", "gamma"];

  it("renders input when no value is selected", () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    expect(screen.getByPlaceholderText("Filter by tag")).toBeTruthy();
  });

  it("renders chip when a value is selected", () => {
    render(<TagPicker knownTags={tags} value="alpha" onSelect={vi.fn()} />);
    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.queryByPlaceholderText("Filter by tag")).toBeNull();
  });

  it("clear button calls onSelect with empty string", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="alpha" onSelect={onSelect} />);
    fireEvent.click(screen.getByLabelText("Clear tag filter"));
    expect(onSelect).toHaveBeenCalledWith("");
  });

  it("shows all suggestions on focus", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    fireEvent.focus(screen.getByPlaceholderText("Filter by tag"));
    await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });

  it("filters suggestions based on typed input", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("Filter by tag"), {
      target: { value: "al" },
    });
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "alpha" })).toBeTruthy();
      expect(screen.queryByRole("option", { name: "beta" })).toBeNull();
    });
  });

  it("mousedown on suggestion calls onSelect", async () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    fireEvent.focus(screen.getByPlaceholderText("Filter by tag"));
    await waitFor(() => screen.getByRole("option", { name: "alpha" }));
    fireEvent.mouseDown(screen.getByRole("option", { name: "alpha" }));
    expect(onSelect).toHaveBeenCalledWith("alpha");
  });

  it("ArrowDown highlights next suggestion and cannot go past last", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("option", { name: "alpha" }));

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: "alpha" }).getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: "beta" }).getAttribute("aria-selected")).toBe("true");

    // Past last item — stays on last
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: "gamma" }).getAttribute("aria-selected")).toBe("true");
  });

  it("ArrowUp highlights previous suggestion and cannot go before first", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("option", { name: "alpha" }));

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: "beta" }).getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(screen.getByRole("option", { name: "alpha" }).getAttribute("aria-selected")).toBe("true");

    // Cannot go before first
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(screen.getByRole("option", { name: "alpha" }).getAttribute("aria-selected")).toBe("true");
  });

  it("Enter with active item selects it", async () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("option", { name: "alpha" }));
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("alpha");
  });

  it("Enter with no active item does nothing", async () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("option", { name: "alpha" }));
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Enter with typed value and no suggestions commits the typed value", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.change(input, { target: { value: "new-tag" } }); // no matches → no suggestions
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("new-tag");
  });

  it("Enter with empty input and no suggestions does nothing", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.change(input, { target: { value: "zzz" } }); // no matches → no suggestions
    fireEvent.change(input, { target: { value: "" } }); // clear
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Enter with typed value matching suggestions commits the typed value", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.change(input, { target: { value: "new-unique-tag" } }); // no match → no suggestions, first branch
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("new-unique-tag");
  });

  it("Enter with typed value matching suggestions (dropdown open) commits typed value", async () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    // Wrap in act so React flushes state (open=true, suggestions populated) before keyDown
    await act(async () => {
      fireEvent.change(input, { target: { value: "alpha" } });
    });
    // Now open=true, suggestions=["alpha"], activeIndex=-1 → second branch (line 64)
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("alpha");
  });

  it("Enter with empty input when suggestions are open does nothing", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.change(input, { target: { value: "tag1" } }); // open suggestions
    fireEvent.change(input, { target: { value: "" } }); // clear input
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Escape when suggestions are open closes the dropdown", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("listbox"));
    fireEvent.keyDown(input, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  });

  it("Escape when no suggestions still closes open state", () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    // "zzz" has no matches but sets open=true; Escape should close
    fireEvent.change(input, { target: { value: "zzz" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("non-navigation key when no suggestions does nothing", () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.change(input, { target: { value: "zzz" } }); // no matches
    fireEvent.keyDown(input, { key: "a" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("non-navigation key when dropdown is open does nothing", async () => {
    const onSelect = vi.fn();
    render(<TagPicker knownTags={tags} value="" onSelect={onSelect} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("listbox"));
    fireEvent.keyDown(input, { key: "Tab" });
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("listbox")).toBeTruthy();
  });

  it("blur closes dropdown after delay", async () => {
    render(<TagPicker knownTags={tags} value="" onSelect={vi.fn()} />);
    const input = screen.getByPlaceholderText("Filter by tag");
    fireEvent.focus(input);
    await waitFor(() => screen.getByRole("listbox"));
    fireEvent.blur(input);
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull(), { timeout: 500 });
  });

  it("shows no dropdown when knownTags is empty", () => {
    render(<TagPicker knownTags={[]} value="" onSelect={vi.fn()} />);
    fireEvent.focus(screen.getByPlaceholderText("Filter by tag"));
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});

// ------------------------------------------------------------------
// MemoryBrowser
// ------------------------------------------------------------------

describe("MemoryBrowser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage flags between tests so the
    // first-memory celebration toast fires for the test that
    // expects it (otherwise a previous test's create leaves the
    // flag set and the toast suppresses).
    localStorage.removeItem("hive_first_memory");
    localStorage.removeItem("hive_first_memory_skipped");
    localStorage.removeItem("hive_tour_dismissed");
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });
    api.searchMemories.mockResolvedValue({ items: [], count: 0 });
    // Default to a shape without `items` so the `?? []` fallback is exercised.
    api.listClients.mockResolvedValue({});
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem("hive_first_memory");
    localStorage.removeItem("hive_first_memory_skipped");
    localStorage.removeItem("hive_tour_dismissed");
  });

  // Helpers
  function getCard() { return screen.getByTestId("memory-card"); }
  function getAllCards() { return screen.getAllByTestId("memory-card"); }

  // ---------------------------------------------------------------------------
  // Initial render
  // ---------------------------------------------------------------------------

  it("renders heading and New button", async () => {
    await act(async () => render(<MemoryBrowser />));
    expect(screen.getByText("Memories")).toBeTruthy();
    expect(screen.getByText("+ New")).toBeTruthy();
  });

  it("toolbar row wraps on narrow screens so the New button stays in view", async () => {
    const { container } = await act(async () => render(<MemoryBrowser />));
    // The heading + search + tag picker + New button share a flex row that
    // must `flex-wrap` (below sm) so the rightmost button doesn't clip when
    // the viewport is 375px.
    const heading = container.querySelector("h2");
    const toolbar = heading.parentElement;
    expect(toolbar.className).toMatch(/flex-wrap/);
  });

  it("renders empty state after load", async () => {
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("No memories yet")).toBeTruthy());
  });

  it("empty-state Open Setup CTA dispatches the tab-switch event", async () => {
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("No memories yet")).toBeTruthy());
    const dispatchSpy = vi.spyOn(globalThis, "dispatchEvent");
    fireEvent.click(screen.getByRole("button", { name: "Open Setup" }));
    const switchEvents = dispatchSpy.mock.calls
      .map((call) => call[0])
      .filter((evt) => evt && evt.type === "hive:switch-tab");
    expect(switchEvents.at(-1).detail).toBe("setup");
    dispatchSpy.mockRestore();
  });

  it("renders loaded memories", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("test-key")).toBeTruthy());
    expect(screen.getByText("test-value")).toBeTruthy();
    expect(screen.getByText("tag1")).toBeTruthy();
  });

  it("truncates values longer than 160 characters", async () => {
    const longValue = "x".repeat(200);
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ value: longValue })],
      next_cursor: null,
    });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText(/x{160}…/)).toBeTruthy());
  });

  it("shows error when listMemories fails", async () => {
    api.listMemories.mockRejectedValue(new Error("Load failed"));
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("Load failed")).toBeTruthy());
  });

  it("passes tag filter to listMemories when a tag is selected", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ tags: ["mytag"] })],
      next_cursor: null,
    });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));

    // Type to surface suggestion then select it
    const filterInput = screen.getByPlaceholderText("Filter by tag");
    await act(async () => fireEvent.focus(filterInput));
    await act(async () =>
      fireEvent.change(filterInput, { target: { value: "my" } }),
    );
    await waitFor(() => screen.getByRole("option", { name: "mytag" }));
    await act(async () =>
      fireEvent.mouseDown(screen.getByRole("option", { name: "mytag" })),
    );

    await waitFor(() =>
      expect(api.listMemories).toHaveBeenCalledWith("mytag"),
    );
  });

  it("passes undefined tag when filter is empty", async () => {
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() =>
      expect(api.listMemories).toHaveBeenCalledWith(undefined),
    );
  });

  // ---------------------------------------------------------------------------
  // Pagination
  // ---------------------------------------------------------------------------

  it("shows Load more button when next_cursor is set", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory()],
      next_cursor: "cursor1",
    });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("Load more")).toBeTruthy());
  });

  it("does not show Load more when next_cursor is null", async () => {
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => {});
    expect(screen.queryByText("Load more")).toBeNull();
  });

  it("loads more memories and appends them", async () => {
    const m1 = makeMemory({ memory_id: "m1", key: "key1" });
    const m2 = makeMemory({ memory_id: "m2", key: "key2" });
    api.listMemories
      .mockResolvedValueOnce({ items: [m1], next_cursor: "cursor1" })
      .mockResolvedValueOnce({ items: [m2], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("Load more"));
    await act(async () => fireEvent.click(screen.getByText("Load more")));
    await waitFor(() => expect(screen.getByText("key2")).toBeTruthy());
    expect(screen.getByText("key1")).toBeTruthy();
  });

  it("shows error when loadMore fails", async () => {
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: "c1" })
      .mockRejectedValueOnce(new Error("Load more failed"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("Load more"));
    await act(async () => fireEvent.click(screen.getByText("Load more")));
    await waitFor(() => expect(screen.getByText("Load more failed")).toBeTruthy());
  });

  // ---------------------------------------------------------------------------
  // Create
  // ---------------------------------------------------------------------------

  it("opens create form on + New click", async () => {
    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    expect(screen.getByText("New Memory")).toBeTruthy();
    expect(screen.getByPlaceholderText("unique-key")).toBeTruthy();
  });

  it("closes create form on Cancel", async () => {
    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("New Memory")).toBeNull();
  });

  it("creates memory and closes form on success", async () => {
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories
      .mockResolvedValueOnce({ items: [], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));

    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "my-key" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "my-value" },
    });
    fireEvent.change(screen.getByPlaceholderText("tag1, tag2"), {
      target: { value: "t1, t2" },
    });

    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(api.createMemory).toHaveBeenCalledWith({
      key: "my-key",
      value: "my-value",
      tags: ["t1", "t2"],
    });
    await waitFor(() => expect(screen.queryByText("New Memory")).toBeNull());
  });

  it("first successful create fires the celebration toast and sets the localStorage flag", async () => {
    const sonner = await import("sonner");
    const toastSuccess = vi.spyOn(sonner.toast, "success").mockImplementation(() => {});
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    // Post-create reload returns the single new memory — that's the
    // server-side "first in store" signal the toast gates on.
    api.listMemories
      .mockResolvedValueOnce({ items: [], next_cursor: null })
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(toastSuccess).toHaveBeenCalledWith(
      "First memory saved",
      expect.objectContaining({ description: expect.any(String) }),
    );
    expect(localStorage.getItem("hive_first_memory")).toBe("1");
    toastSuccess.mockRestore();
  });

  it("does not fire the celebration toast when the store already has other memories", async () => {
    // Existing user / multi-browser case: localStorage flag isn't
    // set yet (this browser is fresh), but the workspace already
    // has more than one memory. The toast must stay silent — and
    // the flag should still flip so we don't keep re-checking.
    const sonner = await import("sonner");
    const toastSuccess = vi.spyOn(sonner.toast, "success").mockImplementation(() => {});
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory(), makeMemory()], next_cursor: null })
      .mockResolvedValueOnce({
        items: [makeMemory(), makeMemory(), makeMemory()],
        next_cursor: null,
      });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(toastSuccess).not.toHaveBeenCalled();
    // Celebration flag must NOT flip — that would suppress a real
    // future first-memory celebration if the workspace ever drops
    // back to a single item.
    expect(localStorage.getItem("hive_first_memory")).toBeNull();
    // But the "skipped" flag MUST flip so subsequent creates don't
    // re-probe the unfiltered list on every save.
    expect(localStorage.getItem("hive_first_memory_skipped")).toBe("1");
    toastSuccess.mockRestore();
  });

  it("respects the cached 'skipped' flag and doesn't re-probe on later creates", async () => {
    // Iter-3 fix: existing-workspace users used to pay for an
    // unfiltered listMemories on every create. The skipped flag
    // suppresses the probe entirely until they clear it.
    const sonner = await import("sonner");
    const toastSuccess = vi.spyOn(sonner.toast, "success").mockImplementation(() => {});
    localStorage.setItem("hive_first_memory_skipped", "1");
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    api.listMemories.mockClear(); // ignore the initial mount fetch
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(toastSuccess).not.toHaveBeenCalled();
    // Only the load() refresh should fire — no probe call.
    expect(api.listMemories).toHaveBeenCalledTimes(1);
    toastSuccess.mockRestore();
  });

  it("does not surface a create error when the post-create first-memory check fails", async () => {
    // Iter-2 fix: the post-create listMemories was throwing as a
    // create failure — wrap the first-memory probe in its own
    // try/catch and fall back to the normal refresh path.
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    // First listMemories (mount) succeeds with empty page; second
    // call (the first-memory probe) blows up; load() is then called
    // and we let it succeed.
    api.listMemories
      .mockResolvedValueOnce({ items: [], next_cursor: null })
      .mockRejectedValueOnce(new Error("transient list failure"))
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    // No "transient list failure" surfaced as an error — the create
    // succeeded and the form closed.
    expect(screen.queryByText("transient list failure")).toBeNull();
    await waitFor(() => expect(screen.queryByText("New Memory")).toBeNull());
  });

  it("first-memory probe doesn't clobber the user's filtered view", async () => {
    // Iter-2 fix: when a tag filter is active, the post-create
    // probe must not call setMemories(fresh.items) — that would
    // jump the user out of their filter back to the unfiltered
    // first page. Instead the path falls through to load() which
    // re-fetches the current slice.
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    // mount: filter "alpha" returns one memory.
    // probe: unfiltered fetch returns 5 memories (some from other tags).
    // post-create load: filter "alpha" returns the new + one existing.
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory({ tags: ["alpha"] })], next_cursor: null })
      .mockResolvedValueOnce({
        items: [
          makeMemory({ tags: ["alpha"] }),
          makeMemory({ tags: ["beta"] }),
          makeMemory({ tags: ["beta"] }),
          makeMemory({ tags: ["beta"] }),
          makeMemory({ tags: ["beta"] }),
        ],
        next_cursor: null,
      })
      .mockResolvedValueOnce({
        items: [makeMemory({ tags: ["alpha"] }), makeMemory({ tags: ["alpha"] })],
        next_cursor: null,
      });

    await act(async () => render(<MemoryBrowser />));
    // Apply the alpha tag filter via the existing TagPicker — but
    // we can also simulate it by dispatching the hive:memory-browser
    // event the component listens for in production. For test
    // simplicity, mount with a known tag filter via the event.
    await act(async () => {
      globalThis.dispatchEvent(
        new CustomEvent("hive:memory-browser", { detail: { tag: "alpha" } }),
      );
    });

    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    // The third call (load() with filter) was made — listMemories
    // received the "alpha" tag, not undefined.
    const lastListCall = api.listMemories.mock.calls.at(-1);
    expect(lastListCall[0]).toBe("alpha");
  });

  it("handles a probe response with missing items/next_cursor via the nullish fallbacks", async () => {
    // Defensive — covers the `?? 0` / `?? null` branches on line 384
    // when the server returns a sparse payload (older API version,
    // or a proxy that strips fields).
    const sonner = await import("sonner");
    const toastSuccess = vi.spyOn(sonner.toast, "success").mockImplementation(() => {});
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories
      .mockResolvedValueOnce({ items: [], next_cursor: null })
      .mockResolvedValueOnce({}); // no items, no next_cursor

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    // items undefined → items?.length === undefined → ?? 0 →
    // 0 === 1 is false, so isFirstInStore is false and the toast
    // does NOT fire.
    expect(toastSuccess).not.toHaveBeenCalled();
    expect(localStorage.getItem("hive_first_memory_skipped")).toBe("1");
    toastSuccess.mockRestore();
  });

  it("subsequent creates don't re-fire the celebration toast once the flag is set", async () => {
    const sonner = await import("sonner");
    const toastSuccess = vi.spyOn(sonner.toast, "success").mockImplementation(() => {});
    localStorage.setItem("hive_first_memory", "1");
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(toastSuccess).not.toHaveBeenCalled();
    toastSuccess.mockRestore();
    localStorage.removeItem("hive_first_memory");
  });

  it("shows error when createMemory fails", async () => {
    api.createMemory.mockRejectedValue(new Error("Create error"));
    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );
    await waitFor(() => expect(screen.getByText("Create error")).toBeTruthy());
  });

  it("surfaces a quota banner with a Setup link when createMemory returns 429", async () => {
    const quotaErr = new Error("Memory quota of 500 reached.");
    quotaErr.status = 429;
    api.createMemory.mockRejectedValue(quotaErr);
    const dispatchSpy = vi.spyOn(globalThis, "dispatchEvent");

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    const banner = await screen.findByTestId("quota-banner");
    expect(banner.textContent).toContain("Quota or rate limit reached");
    expect(banner.textContent).toContain("Memory quota of 500 reached.");
    expect(banner.textContent).toContain("Try again later");
    // Generic error text MUST NOT also surface — banner replaces it.
    expect(screen.queryByText("Memory quota of 500 reached.", { selector: "p" })).toBeNull();

    // Clicking "Open Setup" dispatches the tab-switch event the App
    // shell listens for; banner should clear so it doesn't stick on
    // the new tab. Scope to the banner because the empty-state CTA
    // also has an "Open Setup" link when no memories exist.
    fireEvent.click(within(banner).getByText("Open Setup"));
    const switchEvents = dispatchSpy.mock.calls
      .map((call) => call[0])
      .filter((evt) => evt && evt.type === "hive:switch-tab");
    expect(switchEvents.length).toBeGreaterThan(0);
    expect(switchEvents.at(-1).detail).toBe("setup");
    expect(screen.queryByTestId("quota-banner")).toBeNull();
    dispatchSpy.mockRestore();
  });

  it("scrolls the #usage anchor into view after switching to Setup", async () => {
    // Banner copy points users at "open Setup to review your current
    // usage" — verify the click actually deep-links to the anchor,
    // not just the tab. Use a real timeout (setTimeout delay of 0)
    // instead of fake timers because fake timers + initial React
    // effects don't mix (see §UI conventions in CLAUDE.md).
    const quotaErr = new Error("Memory quota of 500 reached.");
    quotaErr.status = 429;
    api.createMemory.mockRejectedValue(quotaErr);

    const scrollIntoView = vi.fn();
    const realGetElementById = document.getElementById.bind(document);
    const getByIdSpy = vi
      .spyOn(document, "getElementById")
      .mockImplementation((id) => {
        if (id === "usage") return { scrollIntoView };
        return realGetElementById(id);
      });

    try {
      await act(async () => render(<MemoryBrowser />));
      fireEvent.click(screen.getByText("+ New"));
      fireEvent.change(screen.getByPlaceholderText("unique-key"), {
        target: { value: "k" },
      });
      fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
        target: { value: "v" },
      });
      await act(async () => {
        fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form"));
      });
      const banner = await screen.findByTestId("quota-banner");

      fireEvent.click(within(banner).getByText("Open Setup"));
      // Real setTimeout(0) — flush the macrotask queue.
      await new Promise((resolve) => globalThis.setTimeout(resolve, 0));

      expect(scrollIntoView).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "start",
      });
    } finally {
      getByIdSpy.mockRestore();
    }
  });

  it("no-ops scroll when the #usage anchor isn't present", async () => {
    // Defensive — covers the `if (target)` guard so the timer
    // callback can't NPE when SetupPanel hasn't mounted. The test
    // DOM has no #usage element (SetupPanel isn't mounted), so the
    // deferred scrollIntoView must short-circuit cleanly.
    const quotaErr = new Error("Memory quota of 500 reached.");
    quotaErr.status = 429;
    api.createMemory.mockRejectedValue(quotaErr);

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () => {
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form"));
    });
    const banner = await screen.findByTestId("quota-banner");
    fireEvent.click(within(banner).getByText("Open Setup"));
    // Flush the macrotask queue — the deferred `if (target)` branch
    // must no-op without throwing when #usage doesn't exist.
    await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
    // Banner cleared on tab-switch click, confirming the click
    // handler still ran even without a scroll target.
    expect(screen.queryByTestId("quota-banner")).toBeNull();
  });

  it("clears stale generic error when a follow-up 429 fires", async () => {
    // Sequence: first create fails generically, then a retry hits the
    // quota wall. The banner must take over and the inline error
    // paragraph must clear so the two never render together.
    const genericErr = new Error("Server hiccup");
    const quotaErr = new Error("Memory quota of 500 reached.");
    quotaErr.status = 429;
    api.createMemory.mockRejectedValueOnce(genericErr).mockRejectedValueOnce(quotaErr);

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );
    await waitFor(() => expect(screen.getByText("Server hiccup")).toBeTruthy());
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    await screen.findByTestId("quota-banner");
    expect(screen.queryByText("Server hiccup")).toBeNull();
  });

  it("clears stale quota banner when a follow-up generic error fires", async () => {
    const quotaErr = new Error("Memory quota of 500 reached.");
    quotaErr.status = 429;
    const genericErr = new Error("Server hiccup");
    api.createMemory.mockRejectedValueOnce(quotaErr).mockRejectedValueOnce(genericErr);

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );
    await screen.findByTestId("quota-banner");
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    await waitFor(() => expect(screen.getByText("Server hiccup")).toBeTruthy());
    expect(screen.queryByTestId("quota-banner")).toBeNull();
  });

  it("falls back to a generic message on 429 with no detail body", async () => {
    const quotaErr = new Error("");
    quotaErr.status = 429;
    api.createMemory.mockRejectedValue(quotaErr);

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));
    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "k" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "v" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    const banner = await screen.findByTestId("quota-banner");
    expect(banner.textContent).toContain("Quota or rate limit reached.");
  });

  // ---------------------------------------------------------------------------
  // Edit / Update
  // ---------------------------------------------------------------------------

  it("opens edit form when memory card is clicked", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());
    expect(screen.getByText("Edit: test-key")).toBeTruthy();
    expect(screen.queryByPlaceholderText("unique-key")).toBeNull(); // key field hidden in edit
  });

  it("opens edit form when memory card is activated via keyboard Enter or Space", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    const card = getCard();
    // Enter opens the form
    fireEvent.keyDown(card, { key: "Enter" });
    expect(screen.getByText("Edit: test-key")).toBeTruthy();
    // Close form; Space also opens it
    fireEvent.click(screen.getByText("Cancel"));
    fireEvent.keyDown(card, { key: " " });
    expect(screen.getByText("Edit: test-key")).toBeTruthy();
    // Other keys are ignored
    fireEvent.click(screen.getByText("Cancel"));
    fireEvent.keyDown(card, { key: "Tab" });
    expect(screen.queryByText("Edit: test-key")).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // List keyboard navigation (#257)
  // ---------------------------------------------------------------------------

  it("ArrowDown moves focus to next card", async () => {
    const m1 = makeMemory({ memory_id: "m1", key: "key1" });
    const m2 = makeMemory({ memory_id: "m2", key: "key2" });
    api.listMemories.mockResolvedValue({ items: [m1, m2], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("key1"));

    const [card1, card2] = getAllCards();

    // Focus card1 then press ArrowDown → card2 gets focus
    await act(async () => fireEvent.focus(card1));
    await act(async () => fireEvent.keyDown(card1, { key: "ArrowDown" }));
    await waitFor(() => expect(card2).toHaveFocus());
  });

  it("ArrowUp moves focus to previous card", async () => {
    const m1 = makeMemory({ memory_id: "m1", key: "key1" });
    const m2 = makeMemory({ memory_id: "m2", key: "key2" });
    api.listMemories.mockResolvedValue({ items: [m1, m2], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("key2"));

    const [card1, card2] = getAllCards();

    // Focus card2 then press ArrowUp → card1 gets focus
    await act(async () => fireEvent.focus(card2));
    await act(async () => fireEvent.keyDown(card2, { key: "ArrowUp" }));
    await waitFor(() => expect(card1).toHaveFocus());
  });

  it("Delete key on focused card triggers delete", async () => {
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });
    api.deleteMemory.mockResolvedValue(null);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    const card = getCard();
    await act(async () => fireEvent.keyDown(card, { key: "Delete" }));
    expect(api.deleteMemory).toHaveBeenCalledWith("m1");
  });

  it("Backspace key on focused card triggers delete", async () => {
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });
    api.deleteMemory.mockResolvedValue(null);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    const card = getCard();
    await act(async () => fireEvent.keyDown(card, { key: "Backspace" }));
    expect(api.deleteMemory).toHaveBeenCalledWith("m1");
  });

  it("Escape key on card closes the edit panel", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));

    // Open edit panel
    fireEvent.click(getCard());
    expect(screen.getByText("Edit: test-key")).toBeTruthy();

    // Escape closes it
    const card = getCard();
    await act(async () => fireEvent.keyDown(card, { key: "Escape" }));
    expect(screen.queryByText("Edit: test-key")).toBeNull();
  });

  it("onFocus on card tracks focusedIndex (ArrowDown starts from focused card)", async () => {
    const m1 = makeMemory({ memory_id: "m1", key: "key1" });
    const m2 = makeMemory({ memory_id: "m2", key: "key2" });
    const m3 = makeMemory({ memory_id: "m3", key: "key3" });
    api.listMemories.mockResolvedValue({ items: [m1, m2, m3], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("key2"));

    const [, card2, card3] = getAllCards();

    // Focus card2 (index 1) then ArrowDown → card3 (index 2)
    await act(async () => fireEvent.focus(card2));
    await act(async () => fireEvent.keyDown(card2, { key: "ArrowDown" }));
    await waitFor(() => expect(card3).toHaveFocus());
  });

  it("updates memory and closes form on success", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.updateMemory.mockResolvedValue({});

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());

    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "new-value" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("Memory content…").closest("form")),
    );

    expect(api.updateMemory).toHaveBeenCalledWith(
      "m1",
      expect.objectContaining({ value: "new-value" }),
    );
    await waitFor(() => expect(screen.queryByText("Edit: test-key")).toBeNull());
  });

  it("shows error when updateMemory fails", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.updateMemory.mockRejectedValue(new Error("Update error"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("Memory content…").closest("form")),
    );
    await waitFor(() => expect(screen.getByText("Update error")).toBeTruthy());
  });

  it("opening create while editing replaces edit panel with create", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());
    expect(screen.getByText("Edit: test-key")).toBeTruthy();
    fireEvent.click(screen.getByText("+ New"));
    expect(screen.getByText("New Memory")).toBeTruthy();
    expect(screen.queryByText("Edit: test-key")).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------

  it("opens confirm dialog when Delete button clicked", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    expect(screen.getByText("Delete this memory?")).toBeTruthy();
  });

  it("deletes memory when confirmed", async () => {
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });
    api.deleteMemory.mockResolvedValue(null);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () =>
      fireEvent.click(screen.getAllByText("Delete").at(-1)),
    );
    expect(api.deleteMemory).toHaveBeenCalledWith("m1");
  });

  it("does not delete when dialog is cancelled", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () => fireEvent.click(screen.getByText("Cancel")));
    expect(api.deleteMemory).not.toHaveBeenCalled();
  });

  it("shows error when deleteMemory fails", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.deleteMemory.mockRejectedValue(new Error("Delete failed"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    await act(async () =>
      fireEvent.click(screen.getAllByText("Delete").at(-1)),
    );
    await waitFor(() => expect(screen.getByText("Delete failed")).toBeTruthy());
  });

  it("delete button does not open edit form", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("Delete")));
    expect(screen.queryByText("Edit: test-key")).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // Semantic search
  // ---------------------------------------------------------------------------

  it("renders Search by meaning input", async () => {
    await act(async () => render(<MemoryBrowser />));
    expect(screen.getByPlaceholderText("Search by meaning…")).toBeTruthy();
  });

  it("calls searchMemories after debounce when query is typed", async () => {
    const m = makeMemory({ memory_id: "s1", key: "semantic-key" });
    api.searchMemories.mockResolvedValue({ items: [m], count: 1 });

    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "semantic" } }),
    );
    await waitFor(
      () =>
        expect(api.searchMemories).toHaveBeenCalledWith("semantic", { limit: 50 }),
      { timeout: 1000 },
    );
  });

  it("exposes a Top-K slider only when search mode is active", async () => {
    api.searchMemories.mockResolvedValue({ items: [], count: 0 });

    await act(async () => render(<MemoryBrowser />));
    // No search query typed yet → slider hidden.
    expect(screen.queryByTestId("search-topk-control")).toBeNull();

    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () => fireEvent.change(searchInput, { target: { value: "q" } }));

    expect(screen.getByTestId("search-topk-control")).toBeTruthy();
    expect(screen.getByLabelText("Maximum number of search results")).toBeTruthy();
  });

  it("updating the Top-K slider re-runs search with the new limit", async () => {
    api.searchMemories.mockResolvedValue({ items: [], count: 0 });
    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () => fireEvent.change(searchInput, { target: { value: "q" } }));
    await waitFor(() =>
      expect(api.searchMemories).toHaveBeenCalledWith("q", { limit: 50 }),
    );

    const slider = screen.getByLabelText("Maximum number of search results");
    await act(async () => fireEvent.change(slider, { target: { value: "20" } }));

    await waitFor(
      () => expect(api.searchMemories).toHaveBeenCalledWith("q", { limit: 20 }),
      { timeout: 1000 },
    );
  });

  it("slider clamp: value displayed matches the current Top-K", async () => {
    api.searchMemories.mockResolvedValue({ items: [], count: 0 });
    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () => fireEvent.change(searchInput, { target: { value: "q" } }));

    // Default K=50 rendered in the live region.
    const control = screen.getByTestId("search-topk-control");
    expect(within(control).getByText("50")).toBeTruthy();

    const slider = screen.getByLabelText("Maximum number of search results");
    await act(async () => fireEvent.change(slider, { target: { value: "7" } }));
    expect(within(control).getByText("7")).toBeTruthy();
  });

  it("renders score badge on search results", async () => {
    const m = makeMemory({ memory_id: "s2", score: 0.87 });
    api.searchMemories.mockResolvedValue({ items: [m], count: 1 });

    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "anything" } }),
    );
    await waitFor(() => expect(screen.getByText("87% match")).toBeTruthy(), { timeout: 1000 });
  });

  it("clears tag filter chip when search query is typed", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ tags: ["mytag"] })],
      next_cursor: null,
    });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));

    // Select tag via TagPicker
    const filterInput = screen.getByPlaceholderText("Filter by tag");
    await act(async () => fireEvent.focus(filterInput));
    await act(async () =>
      fireEvent.change(filterInput, { target: { value: "my" } }),
    );
    await waitFor(() => screen.getByRole("option", { name: "mytag" }));
    await act(async () =>
      fireEvent.mouseDown(screen.getByRole("option", { name: "mytag" })),
    );

    // Chip is now shown; input is gone
    expect(screen.queryByPlaceholderText("Filter by tag")).toBeNull();

    // Type in search — tag chip should clear (input reappears)
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "query" } }),
    );
    expect(screen.getByPlaceholderText("Filter by tag")).toBeTruthy();
  });

  it("clears search query when tag is selected from picker", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ tags: ["mytag"] })],
      next_cursor: null,
    });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));

    // Enter search mode
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "query" } }),
    );

    // Select tag via TagPicker
    const filterInput = screen.getByPlaceholderText("Filter by tag");
    await act(async () => fireEvent.focus(filterInput));
    await act(async () =>
      fireEvent.change(filterInput, { target: { value: "my" } }),
    );
    await waitFor(() => screen.getByRole("option", { name: "mytag" }));
    await act(async () =>
      fireEvent.mouseDown(screen.getByRole("option", { name: "mytag" })),
    );

    expect(searchInput.value).toBe("");
  });

  it("does not call searchMemories when search is cleared", async () => {
    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");

    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "" } }),
    );
    // searchMemories should not be called for empty query
    expect(api.searchMemories).not.toHaveBeenCalled();
  });

  it("clears search mode when search input is cleared", async () => {
    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");

    // Type something to enter search mode
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "query" } }),
    );
    // Clear it — should exit search mode (isSearchMode = false)
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "" } }),
    );
    // Tag filter should still work (list mode re-engaged)
    await waitFor(() =>
      expect(api.listMemories).toHaveBeenCalled(),
    );
  });

  it("shows error when searchMemories fails", async () => {
    api.searchMemories.mockRejectedValue(new Error("Search error"));

    await act(async () => render(<MemoryBrowser />));
    const searchInput = screen.getByPlaceholderText("Search by meaning…");
    await act(async () =>
      fireEvent.change(searchInput, { target: { value: "bad query" } }),
    );
    await waitFor(() => expect(screen.getByText("Search error")).toBeTruthy(), {
      timeout: 1000,
    });
  });

  // ---------------------------------------------------------------------------
  // TTL / expiry
  // ---------------------------------------------------------------------------

  it("shows expiry badge for memories with expires_at", async () => {
    const expiry = new Date("2027-01-15T00:00:00.000Z").toISOString();
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ expires_at: expiry })],
      next_cursor: null,
    });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    expect(screen.getByText(/Expires/)).toBeTruthy();
  });

  it("creates memory with TTL when Expires In is set", async () => {
    api.createMemory.mockResolvedValue({ memory_id: "new" });
    api.listMemories
      .mockResolvedValueOnce({ items: [], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    fireEvent.click(screen.getByText("+ New"));

    fireEvent.change(screen.getByPlaceholderText("unique-key"), {
      target: { value: "ttl-key" },
    });
    fireEvent.change(screen.getByPlaceholderText("Memory content…"), {
      target: { value: "ttl-val" },
    });
    fireEvent.change(screen.getByLabelText("Expires in"), {
      target: { value: "3600" },
    });

    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("unique-key").closest("form")),
    );

    expect(api.createMemory).toHaveBeenCalledWith(
      expect.objectContaining({ ttl_seconds: 3600 }),
    );
  });

  it("updates memory with ttl_seconds 0 to clear TTL when form.ttl is empty", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.updateMemory.mockResolvedValue({});

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());

    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("Memory content…").closest("form")),
    );

    expect(api.updateMemory).toHaveBeenCalledWith(
      "m1",
      expect.objectContaining({ ttl_seconds: 0 }),
    );
  });

  it("updates memory with parsed ttl_seconds when TTL is set", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.updateMemory.mockResolvedValue({});

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    fireEvent.click(getCard());

    fireEvent.change(screen.getByLabelText("Expires in"), {
      target: { value: "86400" },
    });
    await act(async () =>
      fireEvent.submit(screen.getByPlaceholderText("Memory content…").closest("form")),
    );

    expect(api.updateMemory).toHaveBeenCalledWith(
      "m1",
      expect.objectContaining({ ttl_seconds: 86400 }),
    );
  });

  // ---------------------------------------------------------------------------
  // Version history
  // ---------------------------------------------------------------------------

  it("opens history panel on History button click with no versions", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));

    await waitFor(() => expect(screen.getByText("History: test-key")).toBeTruthy());
    expect(screen.getByText("No previous versions.")).toBeTruthy();
  });

  it("shows versions in history panel and truncates long values", async () => {
    const shortVersion = {
      version_timestamp: "20260412T120000000000",
      value: "old value",
      tags: [],
      recorded_at: "2026-04-12T12:00:00.000Z",
    };
    const longVersion = {
      version_timestamp: "20260412T110000000000",
      value: "x".repeat(200),
      tags: [],
      recorded_at: "2026-04-12T11:00:00.000Z",
    };
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([shortVersion, longVersion]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));

    await waitFor(() => expect(screen.getByText("old value")).toBeTruthy());
    // Long value gets truncated with ellipsis
    expect(screen.getByText(/x{120}…/)).toBeTruthy();
    expect(screen.getAllByText("Restore")).toHaveLength(2);
  });

  it("toggles the diff view when 'Show diff' is clicked", async () => {
    // #383: each history row gets a diff toggle that compares the
    // version against the current live value. Toggle on → replaces
    // the truncated value with a diff; toggle off → back to the
    // truncated summary.
    const version = {
      version_timestamp: "20260412T120000000000",
      value: "hello old world",
      tags: [],
      recorded_at: "2026-04-12T12:00:00.000Z",
    };
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ value: "hello new world" })],
      next_cursor: null,
    });
    api.listMemoryVersions.mockResolvedValue([version]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("Show diff"));

    // Initially truncated value is visible, diff testid is not.
    expect(screen.getByText("hello old world")).toBeTruthy();
    expect(screen.queryByTestId("memory-diff")).toBeNull();

    fireEvent.click(screen.getByText("Show diff"));
    expect(screen.getByTestId("memory-diff")).toBeTruthy();
    // Toggle button flips label.
    expect(screen.getByText("Hide diff")).toBeTruthy();

    // Diff renders the before→after words via <ins>/<del>.
    const diff = screen.getByTestId("memory-diff");
    expect(diff.querySelector("ins").textContent).toContain("new");
    expect(diff.querySelector("del").textContent).toContain("old");

    fireEvent.click(screen.getByText("Hide diff"));
    expect(screen.queryByTestId("memory-diff")).toBeNull();
  });

  it("closing history clears the expanded diff state", async () => {
    // Defensive — expandedVersion must reset when the panel
    // closes, otherwise reopening history would land in diff mode
    // even though the user dismissed it.
    const version = {
      version_timestamp: "20260412T120000000000",
      value: "hello old world",
      tags: [],
      recorded_at: "2026-04-12T12:00:00.000Z",
    };
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ value: "hello new world" })],
      next_cursor: null,
    });
    api.listMemoryVersions.mockResolvedValue([version]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("Show diff"));
    fireEvent.click(screen.getByText("Show diff"));
    expect(screen.getByTestId("memory-diff")).toBeTruthy();

    fireEvent.click(screen.getByText("Close"));
    await waitFor(() => expect(screen.queryByText("History: test-key")).toBeNull());
    // Re-open: should land on the truncated list view, not stay in
    // diff mode from the previous session.
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("Show diff"));
    expect(screen.queryByTestId("memory-diff")).toBeNull();
  });

  it("restores a version and closes history panel", async () => {
    const version = {
      version_timestamp: "20260412T120000000000",
      value: "old value",
      tags: [],
      recorded_at: "2026-04-12T12:00:00.000Z",
    };
    api.listMemories
      .mockResolvedValueOnce({ items: [makeMemory()], next_cursor: null })
      .mockResolvedValue({ items: [], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([version]);
    api.restoreMemoryVersion.mockResolvedValue({});

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("Restore"));
    await act(async () => fireEvent.click(screen.getByText("Restore")));

    expect(api.restoreMemoryVersion).toHaveBeenCalledWith("m1", "20260412T120000000000");
    await waitFor(() => expect(screen.queryByText("History: test-key")).toBeNull());
  });

  it("shows error when restore fails", async () => {
    const version = {
      version_timestamp: "20260412T120000000000",
      value: "old value",
      tags: [],
      recorded_at: "2026-04-12T12:00:00.000Z",
    };
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([version]);
    api.restoreMemoryVersion.mockRejectedValue(new Error("Restore failed"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("Restore"));
    await act(async () => fireEvent.click(screen.getByText("Restore")));

    await waitFor(() => expect(screen.getByText("Restore failed")).toBeTruthy());
  });

  it("closes history panel on Close button click", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("History: test-key"));
    fireEvent.click(screen.getByText("Close"));
    expect(screen.queryByText("History: test-key")).toBeNull();
  });

  it("shows error when listMemoryVersions fails", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockRejectedValue(new Error("History load failed"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));

    await waitFor(() => expect(screen.getByText("History load failed")).toBeTruthy());
  });

  it("opening create form clears history panel", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([]);
    api.createMemory.mockResolvedValue({ memory_id: "new" });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("History: test-key"));
    fireEvent.click(screen.getByText("+ New"));
    expect(screen.queryByText("History: test-key")).toBeNull();
    expect(screen.getByText("New Memory")).toBeTruthy();
  });

  it("opening edit form clears history panel", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listMemoryVersions.mockResolvedValue([]);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    await act(async () => fireEvent.click(screen.getByText("History")));
    await waitFor(() => screen.getByText("History: test-key"));
    fireEvent.click(getCard());
    expect(screen.queryByText("History: test-key")).toBeNull();
    expect(screen.getByText("Edit: test-key")).toBeTruthy();
  });

  it("renders attribution badge with client name when client is known", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ owner_client_id: "client-123" })],
      next_cursor: null,
    });
    api.listClients.mockResolvedValue({
      items: [{ client_id: "client-123", client_name: "My Agent" }],
    });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("by My Agent")).toBeTruthy());
  });

  it("falls back to client id when name is not yet loaded", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory({ owner_client_id: "client-xyz" })],
      next_cursor: null,
    });
    api.listClients.mockResolvedValue({ items: [] });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => expect(screen.getByText("by client-xyz")).toBeTruthy());
  });

  it("omits attribution badge when owner_client_id is missing", async () => {
    api.listMemories.mockResolvedValue({
      items: [makeMemory()],
      next_cursor: null,
    });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
    expect(screen.queryByText(/^by /)).toBeNull();
  });

  it("swallows listClients errors and still renders memories", async () => {
    api.listMemories.mockResolvedValue({ items: [makeMemory()], next_cursor: null });
    api.listClients.mockRejectedValue(new Error("network"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("test-key"));
  });

  // #537 — Stats charts dispatch `hive:memory-browser` events to deep-link
  // into this component. A tag detail pre-sets the tag filter; a search
  // detail pre-sets the search query (and clears any lingering tag).
  it("hive:memory-browser event with tag pre-filters the list", async () => {
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    api.listMemories.mockClear();
    await act(async () => {
      globalThis.dispatchEvent(
        new CustomEvent("hive:memory-browser", { detail: { tag: "work" } }),
      );
    });
    await waitFor(() => expect(api.listMemories).toHaveBeenCalledWith("work"));
  });

  it("hive:memory-browser event without a detail payload is a no-op", async () => {
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    api.listMemories.mockClear();
    await act(async () => {
      // Event with no `detail` at all — covers the `?? {}` fallback so
      // the handler doesn't blow up if dispatched unqualified.
      globalThis.dispatchEvent(new Event("hive:memory-browser"));
    });
    // Neither tag filter nor search ran — no additional list fetches.
    expect(api.listMemories).not.toHaveBeenCalled();
  });

  it("hive:memory-browser event with search pre-sets the search query", async () => {
    api.listMemories.mockResolvedValue({ items: [], next_cursor: null });
    api.searchMemories.mockResolvedValue({ items: [], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await act(async () => {
      globalThis.dispatchEvent(
        new CustomEvent("hive:memory-browser", { detail: { search: "my-key" } }),
      );
    });
    const input = await screen.findByPlaceholderText(/search by meaning/i);
    expect(input.value).toBe("my-key");
  });
});

// ------------------------------------------------------------------
// typeBadgeLabel helper
// ------------------------------------------------------------------

describe("typeBadgeLabel", () => {
  it("returns 'Large text' for text-large", () => {
    expect(typeBadgeLabel("text-large")).toBe("Large text");
  });

  it("returns 'Image' for image", () => {
    expect(typeBadgeLabel("image")).toBe("Image");
  });

  it("returns 'Blob' for blob", () => {
    expect(typeBadgeLabel("blob")).toBe("Blob");
  });

  it("returns the raw type for unknown values", () => {
    expect(typeBadgeLabel("video")).toBe("video");
  });
});

// ------------------------------------------------------------------
// formatBytes helper
// ------------------------------------------------------------------

describe("formatBytes", () => {
  it("shows bytes below 1 KB", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("shows KB between 1024 and 1 MB", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
  });

  it("shows MB for 1 MB and above", () => {
    expect(formatBytes(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});

// ------------------------------------------------------------------
// MemoryImage component
// ------------------------------------------------------------------

describe("MemoryImage", () => {
  beforeEach(() => {
    URL.createObjectURL.mockReturnValue("blob:fake-url");
    URL.revokeObjectURL.mockClear();
  });

  afterEach(() => {
    URL.createObjectURL.mockReset();
    URL.revokeObjectURL.mockReset();
    URL.createObjectURL.mockReturnValue("blob:test-url");
  });

  it("shows loading state while fetch is pending", async () => {
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));
    await act(async () =>
      render(<MemoryImage memoryId="m1" alt="img" className="rounded" />),
    );
    expect(screen.getByText("Loading preview…")).toBeTruthy();
  });

  it("renders img element after successful fetch", async () => {
    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" });
    api.getMemoryContent.mockResolvedValue(blob);
    await act(async () =>
      render(<MemoryImage memoryId="m1" alt="my image" className="rounded" />),
    );
    await waitFor(() => expect(screen.getByRole("img")).toBeTruthy());
    expect(screen.getByRole("img").getAttribute("src")).toBe("blob:fake-url");
    expect(screen.getByRole("img").getAttribute("alt")).toBe("my image");
  });

  it("shows error state when fetch fails", async () => {
    api.getMemoryContent.mockRejectedValue(new Error("S3 error"));
    await act(async () =>
      render(<MemoryImage memoryId="m1" alt="img" />),
    );
    await waitFor(() => expect(screen.getByText("Preview unavailable")).toBeTruthy());
  });

  it("revokes object URL on unmount", async () => {
    const blob = new Blob([], { type: "image/png" });
    api.getMemoryContent.mockResolvedValue(blob);
    const { unmount } = await act(async () =>
      render(<MemoryImage memoryId="m1" alt="img" />),
    );
    await waitFor(() => screen.getByRole("img"));
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
  });
});

// ------------------------------------------------------------------
// Binary memory type rendering in list view
// ------------------------------------------------------------------

describe("Binary memory list view", () => {
  beforeEach(() => {
    api.listClients.mockResolvedValue({ items: [] });
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:fake-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows type badge for image memory", async () => {
    const img = makeMemory({ value_type: "image", value: "", content_type: "image/png", size_bytes: 2048 });
    api.listMemories.mockResolvedValue({ items: [img], next_cursor: null });
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("type-badge"));
    expect(screen.getByTestId("type-badge").textContent).toBe("Image");
  });

  it("shows type badge for blob memory", async () => {
    const blob = makeMemory({ value_type: "blob", value: "", content_type: "application/pdf", size_bytes: 4096 });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("type-badge"));
    expect(screen.getByTestId("type-badge").textContent).toBe("Blob");
  });

  it("shows type badge for text-large memory", async () => {
    const large = makeMemory({ value_type: "text-large", value: "", size_bytes: 150000 });
    api.listMemories.mockResolvedValue({ items: [large], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("type-badge"));
    expect(screen.getByTestId("type-badge").textContent).toBe("Large text");
  });

  it("shows no type badge for regular text memory", async () => {
    const text = makeMemory({ value_type: "text", value: "hello" });
    api.listMemories.mockResolvedValue({ items: [text], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("hello"));
    expect(screen.queryByTestId("type-badge")).toBeNull();
  });

  it("shows no type badge when value_type is absent (legacy memory)", async () => {
    const text = makeMemory({ value: "legacy" });
    api.listMemories.mockResolvedValue({ items: [text], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("legacy"));
    expect(screen.queryByTestId("type-badge")).toBeNull();
  });

  it("truncates text value longer than 160 chars in list view", async () => {
    const longValue = "a".repeat(200);
    const text = makeMemory({ value_type: "text", value: longValue });
    api.listMemories.mockResolvedValue({ items: [text], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText(/a{160}…/));
    expect(screen.queryByText(longValue)).toBeNull();
  });

  it("shows empty string for text memory with null value in list view", async () => {
    const text = makeMemory({ value_type: "text", value: null });
    api.listMemories.mockResolvedValue({ items: [text], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    // No crash; the memory card renders with an empty value paragraph
    await waitFor(() => screen.getByTestId("memory-card"));
    expect(screen.queryByTestId("type-badge")).toBeNull();
  });

  it("shows blob content type and formatted size for blob memory", async () => {
    const blob = makeMemory({ value_type: "blob", value: "", content_type: "application/pdf", size_bytes: 4096 });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText(/application\/pdf/));
    expect(screen.getByText(/4\.0 KB/)).toBeTruthy();
  });

  it("shows 'Binary file' when blob has no content_type", async () => {
    const blob = makeMemory({ value_type: "blob", value: "", size_bytes: null });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("Binary file"));
  });

  it("shows large text placeholder with size for text-large memory", async () => {
    const large = makeMemory({ value_type: "text-large", value: "", size_bytes: 150000 });
    api.listMemories.mockResolvedValue({ items: [large], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    // "Large text" appears in both the type badge and the placeholder; wait for the unique size text
    await waitFor(() => screen.getByText(/146\.5 KB/));
    expect(screen.getByText(/146\.5 KB/)).toBeTruthy();
  });

  it("shows large text without size when size_bytes is null", async () => {
    const large = makeMemory({ value_type: "text-large", value: "", size_bytes: null });
    api.listMemories.mockResolvedValue({ items: [large], next_cursor: null });
    await act(async () => render(<MemoryBrowser />));
    // "Large text" appears in both the type badge and the placeholder — assert no size is shown
    await waitFor(() => screen.getByTestId("type-badge"));
    expect(screen.queryByText(/KB/)).toBeNull();
  });

  it("shows MemoryImage loading state for image memory", async () => {
    const img = makeMemory({ value_type: "image", value: "", content_type: "image/png" });
    api.listMemories.mockResolvedValue({ items: [img], next_cursor: null });
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));
    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByText("Loading preview…"));
  });
});

// ------------------------------------------------------------------
// Binary memory edit panel
// ------------------------------------------------------------------

describe("Binary memory edit panel", () => {
  beforeEach(() => {
    api.listClients.mockResolvedValue({ items: [] });
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:fake-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clicking image memory shows image detail panel", async () => {
    const img = makeMemory({
      value_type: "image",
      value: "",
      content_type: "image/png",
      size_bytes: 2048,
      tags: ["photo"],
    });
    api.listMemories.mockResolvedValue({ items: [img], next_cursor: null });
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => screen.getByText(/Image: test-key/));
    expect(screen.getByText("image/png · 2.0 KB")).toBeTruthy();
    // "photo" tag appears in both list card and detail panel — just assert it's present
    expect(screen.getAllByText("photo").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  });

  it("image panel with no content_type or size_bytes shows only the image", async () => {
    const img = makeMemory({ value_type: "image", value: "", tags: [] });
    api.listMemories.mockResolvedValue({ items: [img], next_cursor: null });
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => screen.getByText(/Image: test-key/));
    // No metadata line, no tags
    expect(screen.queryByText(/KB/)).toBeNull();
  });

  it("clicking blob memory shows blob detail panel with download button", async () => {
    const blob = makeMemory({
      value_type: "blob",
      value: "",
      content_type: "application/pdf",
      size_bytes: 8192,
      tags: ["docs"],
    });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => screen.getByText(/Blob: test-key/));
    expect(screen.getByText("application/pdf")).toBeTruthy();
    expect(screen.getByText("8.0 KB")).toBeTruthy();
    // "docs" tag appears in both list card and detail panel — just assert it's present
    expect(screen.getAllByText("docs").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Download/ })).toBeTruthy();
  });

  it("blob panel without size_bytes omits the size line", async () => {
    const blob = makeMemory({ value_type: "blob", value: "", tags: [] });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    // "Binary file" appears in both list and detail panel; wait for the panel heading instead
    await waitFor(() => screen.getByText(/Blob: test-key/));
    expect(screen.queryByText(/KB/)).toBeNull();
  });

  it("blob download triggers file download via anchor click", async () => {
    const blob = makeMemory({
      value_type: "blob",
      value: "",
      content_type: "application/pdf",
      tags: [],
    });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });
    const fakeBlob = new Blob(["pdf"], { type: "application/pdf" });
    api.getMemoryContent.mockResolvedValue(fakeBlob);

    // Render first so React's own createElement calls are not intercepted by our spy
    await act(async () => render(<MemoryBrowser />));

    const fakeAnchor = { href: "", download: "", click: vi.fn() };
    const origCreateElement = document.createElement.bind(document);
    const createElementSpy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag, ...args) =>
        tag === "a" ? fakeAnchor : origCreateElement(tag, ...args),
      );
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));
    await waitFor(() => screen.getByRole("button", { name: /Download/ }));
    await act(async () =>
      fireEvent.click(screen.getByRole("button", { name: /Download/ })),
    );

    await waitFor(() => expect(fakeAnchor.click).toHaveBeenCalled());
    expect(fakeAnchor.download).toBe("test-key");
    expect(fakeAnchor.href).toBe("blob:fake-url");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
    createElementSpy.mockRestore();
  });

  it("blob download error shows error message", async () => {
    const blob = makeMemory({ value_type: "blob", value: "", tags: [] });
    api.listMemories.mockResolvedValue({ items: [blob], next_cursor: null });
    api.getMemoryContent.mockRejectedValue(new Error("S3 failure"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));
    await waitFor(() => screen.getByRole("button", { name: /Download/ }));
    await act(async () =>
      fireEvent.click(screen.getByRole("button", { name: /Download/ })),
    );

    await waitFor(() => screen.getByText("S3 failure"));
  });

  it("clicking text-large memory shows loading then populated textarea", async () => {
    const large = makeMemory({ value_type: "text-large", value: "", size_bytes: 200000 });
    api.listMemories.mockResolvedValue({ items: [large], next_cursor: null });

    let resolveBlob;
    const blobPromise = new Promise((res) => { resolveBlob = res; });
    api.getMemoryContent.mockReturnValue(blobPromise);

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    act(() => { fireEvent.click(screen.getByTestId("memory-card")); });

    await waitFor(() => screen.getByText("Loading content…"));

    const fakeBlob = { text: () => Promise.resolve("the full text content") };
    await act(async () => { resolveBlob(fakeBlob); });

    await waitFor(() => {
      const ta = screen.getByRole("textbox", { name: /Value/ });
      expect(ta.value).toBe("the full text content");
    });
  });

  it("text-large content fetch error still shows editable textarea", async () => {
    const large = makeMemory({ value_type: "text-large", value: "" });
    api.listMemories.mockResolvedValue({ items: [large], next_cursor: null });
    api.getMemoryContent.mockRejectedValue(new Error("S3 error"));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => {
      const ta = screen.queryByRole("textbox", { name: /Value/ });
      expect(ta).toBeTruthy();
    });
  });

  it("opening a text memory with null value populates form with empty string", async () => {
    const mem = makeMemory({ value: null, value_type: "text" });
    api.listMemories.mockResolvedValue({ items: [mem], next_cursor: null });

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => {
      const ta = screen.getByRole("textbox", { name: /Value/ });
      expect(ta.value).toBe("");
    });
  });

  it("image panel with content_type but no size_bytes shows type without size", async () => {
    const img = makeMemory({
      value_type: "image",
      value: "",
      content_type: "image/png",
      size_bytes: null,
      tags: [],
    });
    api.listMemories.mockResolvedValue({ items: [img], next_cursor: null });
    api.getMemoryContent.mockReturnValue(new Promise(() => {}));

    await act(async () => render(<MemoryBrowser />));
    await waitFor(() => screen.getByTestId("memory-card"));
    await act(async () => fireEvent.click(screen.getByTestId("memory-card")));

    await waitFor(() => screen.getByText(/Image: test-key/));
    expect(screen.getByText("image/png")).toBeTruthy();
    expect(screen.queryByText(/KB/)).toBeNull();
  });
});
