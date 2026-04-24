// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Download, X } from "lucide-react";
import { api } from "../api.js";
import EmptyState from "./EmptyState.jsx";
import MemoryDiff from "./MemoryDiff.jsx";
import { toast } from "sonner";
import { AlertDialog } from "./ui/alert-dialog.jsx";
import { Badge } from "./ui/badge.jsx";
import { Button } from "./ui/button.jsx";
import { Card } from "./ui/card.jsx";
import { Input } from "./ui/input.jsx";
import { Label } from "./ui/label.jsx";
import { Select } from "./ui/select.jsx";
import { Textarea } from "./ui/textarea.jsx";

const TTL_OPTIONS = [
  { label: "Never expires", value: "" },
  { label: "1 hour", value: "3600" },
  { label: "1 day", value: "86400" },
  { label: "1 week", value: "604800" },
  { label: "30 days", value: "2592000" },
];

// ------------------------------------------------------------------
// TagPicker — combobox that shows suggestions from known tags,
// renders the selected tag as a removable chip, and calls
// onSelect(tag | "") when the filter changes.
// ------------------------------------------------------------------

export function TagPicker({ knownTags, value, onSelect }) {
  const [inputValue, setInputValue] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const listRef = useRef(null);

  const suggestions = knownTags.filter(
    (t) => t.toLowerCase().includes(inputValue.toLowerCase()) && t !== value,
  );

  function selectTag(tag) {
    onSelect(tag);
    setInputValue("");
    setOpen(false);
    setActiveIndex(-1);
  }

  function clearTag() {
    onSelect("");
    setInputValue("");
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleInputChange(e) {
    setInputValue(e.target.value);
    setOpen(true);
    setActiveIndex(-1);
  }

  function handleKeyDown(e) {
    if (!open || suggestions.length === 0) {
      if (e.key === "Escape") setOpen(false);
      else if (e.key === "Enter" && e.target.value.trim()) {
        e.preventDefault();
        selectTag(e.target.value.trim());
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0) {
        selectTag(suggestions[activeIndex]);
      } else if (e.target.value.trim()) {
        selectTag(e.target.value.trim());
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const item = listRef.current.children[activeIndex];
      item?.scrollIntoView?.({ block: "nearest" });
    }
  }, [activeIndex]);

  return (
    <div className="relative w-40">
      {value ? (
        // Selected chip
        <div className="inline-flex items-center gap-1 px-2 py-1 bg-[var(--surface)] border border-[var(--border)] rounded-full text-xs font-semibold text-[var(--text)] w-full box-border">
          <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
            {value}
          </span>
          <button
            type="button"
            aria-label="Clear tag filter"
            onClick={clearTag}
            className="bg-transparent border-none p-0 cursor-pointer flex items-center text-[var(--text-muted)] shrink-0"
          >
            <X size={11} />
          </button>
        </div>
      ) : (
        // Input
        <Input
          id="tag-filter-input"
          role="combobox"
          className="w-full"
          placeholder="Filter by tag"
          value={inputValue}
          autoComplete="off"
          onChange={handleInputChange}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={handleKeyDown}
          aria-autocomplete="list"
          aria-expanded={open && suggestions.length > 0}
          aria-controls="tag-suggestions"
          aria-activedescendant={activeIndex >= 0 ? `tag-opt-${activeIndex}` : undefined}
        />
      )}

      {open && suggestions.length > 0 && (
        <div
          id="tag-suggestions"
          ref={listRef}
          role="listbox" /* NOSONAR — ARIA combobox pattern; native <select> cannot serve as a positioned overlay */
          className="absolute top-[calc(100%+4px)] left-0 right-0 bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius)] shadow-lg max-h-48 overflow-y-auto z-[100] py-1"
        >
          {suggestions.map((t, i) => (
            <div
              key={t}
              id={`tag-opt-${i}`}
              role="option"
              tabIndex={-1}
              aria-selected={i === activeIndex}
              onMouseDown={() => selectTag(t)}
              className="px-3 py-1.5 text-[13px] cursor-pointer"
              style={{
                background: i === activeIndex ? "var(--accent)" : "transparent",
                color: i === activeIndex ? "var(--accent-fg)" : "var(--text)",
              }}
            >
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

TagPicker.propTypes = {
  knownTags: PropTypes.arrayOf(PropTypes.string).isRequired,
  value: PropTypes.string.isRequired,
  onSelect: PropTypes.func.isRequired,
};

// ------------------------------------------------------------------
// Helpers for binary memory types
// ------------------------------------------------------------------

const _TYPE_LABELS = { "text-large": "Large text", image: "Image", blob: "Blob" };
export function typeBadgeLabel(vt) {
  return _TYPE_LABELS[vt] ?? vt;
}

export function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function MemoryImage({ memoryId, alt, className }) {
  const [src, setSrc] = useState(null);
  const [imgError, setImgError] = useState(false);

  useEffect(
    function fetchImage() {
      let objectUrl = null;
      api
        .getMemoryContent(memoryId)
        .then(function onBlob(blob) {
          objectUrl = URL.createObjectURL(blob);
          setSrc(objectUrl);
        })
        .catch(function onError() {
          setImgError(true);
        });
      return function cleanup() {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      };
    },
    [memoryId],
  );

  if (imgError)
    return (
      <span className="text-[var(--text-muted)] text-[13px]">Preview unavailable</span>
    );
  if (!src)
    return <span className="text-[var(--text-muted)] text-[13px]">Loading preview…</span>;
  return <img src={src} alt={alt} className={className} />;
}

MemoryImage.propTypes = {
  memoryId: PropTypes.string.isRequired,
  alt: PropTypes.string.isRequired,
  className: PropTypes.string,
};

// ------------------------------------------------------------------
// MemoryBrowser
// ------------------------------------------------------------------

export default function MemoryBrowser() {
  const [memories, setMemories] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [quotaError, setQuotaError] = useState(null);
  const [tagFilter, setTagFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchMode, setIsSearchMode] = useState(false);
  // Top-K slider for the semantic search playground (#384). Default
  // matches the API default (50); clamped 1–100.
  const [searchTopK, setSearchTopK] = useState(50);
  const [editing, setEditing] = useState(null); // memory object or null
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ key: "", value: "", tags: "", ttl: "" });
  const [viewingHistory, setViewingHistory] = useState(null); // memory object or null
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  // Which previous version is currently expanded into the diff view.
  // null = the list-only mode; a timestamp = that version diffed
  // against the live current value.
  const [expandedVersion, setExpandedVersion] = useState(null);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [clientNameById, setClientNameById] = useState({});
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(function loadClientNames() {
    api.listClients()
      .then(function handleClients(data) {
        const map = {};
        for (const c of data.items ?? []) {
          map[c.client_id] = c.client_name;
        }
        setClientNameById(map);
      })
      .catch(function ignore() {});
  }, []);
  const searchDebounceRef = useRef(null);
  const listRef = useRef(null);

  // Quota / rate-limit hits get a richer banner that points back to
  // the Setup tab's Usage section, instead of the bare server detail
  // string. Generic errors still go through `setError`. Each branch
  // clears the other state slot so the banner and the inline error
  // can never render together.
  function handleMutationError(err) {
    if (err && err.status === 429) {
      setQuotaError(err.message || "Quota or rate limit reached.");
      setError("");
      return;
    }
    setError(err.message);
    setQuotaError(null);
  }

  function openSetup() {
    setQuotaError(null);
    globalThis.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "setup" }));
  }

  function goToUsage() {
    openSetup();
    // Setup tab mounts asynchronously after the switch — defer the
    // scroll so the #usage anchor exists by the time we look it up.
    globalThis.setTimeout(function scrollToUsage() {
      const target = globalThis.document?.getElementById("usage");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNextCursor(null);
    try {
      const data = await api.listMemories(tagFilter || undefined);
      setMemories(data.items);
      setNextCursor(data.next_cursor ?? null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [tagFilter]);

  const runSearch = useCallback(async (query, topK) => {
    setLoading(true);
    setError("");
    setNextCursor(null);
    try {
      const data = await api.searchMemories(query, { limit: topK });
      setMemories(data.items);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // When tag filter changes, run list (not search)
  useEffect(() => {
    if (!isSearchMode) load();
  }, [load, isSearchMode]);

  // Debounce search input. Re-runs when topK changes too so the
  // playground reacts to slider tweaks without a page reload.
  useEffect(() => {
    if (!searchQuery) return;
    clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => {
      runSearch(searchQuery, searchTopK);
    }, 400);
    return () => clearTimeout(searchDebounceRef.current);
  }, [searchQuery, searchTopK, runSearch]);

  // #537 — Stats charts click-through: the Stats tab dispatches a
  // `hive:memory-browser` CustomEvent with `{ tag }` or `{ search }` to
  // focus this browser on a specific slice. Followed by a
  // `hive:switch-tab` to jump the active tab.
  useEffect(() => {
    function onFocus(e) {
      const detail = e.detail ?? {};
      if (detail.tag) {
        setSearchQuery("");
        setIsSearchMode(false);
        setTagFilter(detail.tag);
      } else if (detail.search) {
        setTagFilter("");
        // Enter search mode explicitly so the list-load effect doesn't
        // fire an unnecessary listMemories() before the debounced
        // runSearch() kicks in.
        setIsSearchMode(true);
        setSearchQuery(detail.search);
      }
    }
    globalThis.addEventListener("hive:memory-browser", onFocus);
    return () => globalThis.removeEventListener("hive:memory-browser", onFocus);
  }, []);

  // Collect distinct tags from loaded memories for suggestions
  const knownTags = [...new Set(memories.flatMap((m) => m.tags))].sort((a, b) => a.localeCompare(b));

  function handleTagSelect(tag) {
    setTagFilter(tag);
    if (tag) {
      setSearchQuery("");
      setIsSearchMode(false);
    }
  }

  function handleSearchQueryChange(e) {
    const val = e.target.value;
    setSearchQuery(val);
    if (val) {
      setTagFilter("");
      setIsSearchMode(true);
    } else {
      setIsSearchMode(false);
    }
  }

  async function loadMore() {
    if (!nextCursor) return; /* c8 ignore next */
    setLoadingMore(true);
    try {
      const data = await api.listMemories(tagFilter || undefined, { cursor: nextCursor });
      setMemories((prev) => [...prev, ...data.items]);
      setNextCursor(data.next_cursor ?? null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    try {
      const body = {
        key: form.key,
        value: form.value,
        tags: form.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      if (form.ttl) body.ttl_seconds = parseInt(form.ttl, 10);
      await api.createMemory(body);
      setCreating(false);
      setForm({ key: "", value: "", tags: "", ttl: "" });
      // First-memory celebration. Two gates so the toast only fires
      // for the genuine first-ever memory in the workspace:
      //   1. Per-browser localStorage flag (don't repeat on later
      //      creates from this browser).
      //   2. Server-side check that the unfiltered store now has
      //      exactly this one item (so an existing user with
      //      memories from another browser / agent doesn't get a
      //      misleading "first memory" toast).
      // Wrapped in try/catch so a transient list failure doesn't
      // make a successful create look like it failed — the caller
      // still falls through to the normal refresh path. We also
      // only reuse the unfiltered fetch as the visible list when
      // the user isn't currently filtered (search / tag) — otherwise
      // we'd silently jump them out of their current view.
      // Two flags so we don't pay for the probe on every create:
      //   hive_first_memory=1 — we already celebrated; skip.
      //   hive_first_memory_skipped=1 — the workspace already had
      //     other memories the first time we checked, so a "first
      //     memory in store" can't happen here without a wipe;
      //     skip until the user clears it.
      if (
        !localStorage.getItem("hive_first_memory") &&
        !localStorage.getItem("hive_first_memory_skipped")
      ) {
        try {
          const fresh = await api.listMemories(undefined);
          const isFirstInStore =
            (fresh.items?.length ?? 0) === 1 && (fresh.next_cursor ?? null) === null;
          if (isFirstInStore) {
            localStorage.setItem("hive_first_memory", "1");
            toast.success("First memory saved", {
              description: "Your agent can now recall it across sessions.",
            });
          } else {
            // Cache the negative result so we don't re-probe on
            // every subsequent create.
            localStorage.setItem("hive_first_memory_skipped", "1");
          }
          if (!tagFilter && !isSearchMode) {
            setMemories(fresh.items ?? []);
            setNextCursor(fresh.next_cursor ?? null);
            // load() normally clears `error` via setError("") on
            // its happy path. We're skipping load() here, so do the
            // clear explicitly — otherwise a stale error from an
            // earlier failed mutation can stay visible after a
            // successful create.
            setError("");
            return;
          }
          // Filtered view — fall through to load() so we re-fetch
          // the user's current slice instead of clobbering it.
        } catch {
          // Transient list failure shouldn't surface as a create
          // error since the create itself succeeded.
        }
      }
      load();
    } catch (err) {
      handleMutationError(err);
    }
  }

  async function handleUpdate(e) {
    e.preventDefault();
    try {
      const body = {
        value: form.value,
        tags: form.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      body.ttl_seconds = form.ttl === "" ? 0 : parseInt(form.ttl, 10);
      await api.updateMemory(editing.memory_id, body);
      setEditing(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteMemory(id);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setPendingDelete(null);
    }
  }

  async function openEdit(m) {
    setEditing(m);
    setCreating(false);
    setViewingHistory(null);
    setVersions([]);

    if (m.value_type === "text-large") {
      setForm({ key: m.key, value: "", tags: m.tags.join(", "), ttl: "" });
      setContentLoading(true);
      try {
        const blob = await api.getMemoryContent(m.memory_id);
        const text = await blob.text();
        setForm((prev) => ({ ...prev, value: text }));
      } catch {
        // Keep the empty value; user can still save tags or a replacement value
      } finally {
        setContentLoading(false);
      }
    } else {
      setForm({ key: m.key, value: m.value ?? "", tags: m.tags.join(", "), ttl: "" });
    }
  }

  async function handleBlobDownload() {
    try {
      const blob = await api.getMemoryContent(editing.memory_id);
      const url = URL.createObjectURL(blob);
      const a = globalThis.document.createElement("a");
      a.href = url;
      a.download = editing.key;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  function openCreate() {
    setCreating(true);
    setEditing(null);
    setForm({ key: "", value: "", tags: "", ttl: "" });
    setViewingHistory(null);
    setVersions([]);
  }

  function closePanel() {
    setEditing(null);
    setCreating(false);
  }

  async function openHistory(m) {
    setViewingHistory(m);
    setEditing(null);
    setCreating(false);
    setExpandedVersion(null);
    setVersionsLoading(true);
    try {
      const vs = await api.listMemoryVersions(m.memory_id);
      setVersions(vs);
    } catch (err) {
      setError(err.message);
    } finally {
      setVersionsLoading(false);
    }
  }

  function closeHistory() {
    setViewingHistory(null);
    setVersions([]);
    setExpandedVersion(null);
  }

  function toggleDiff(versionTimestamp) {
    setExpandedVersion((prev) =>
      prev === versionTimestamp ? null : versionTimestamp,
    );
  }

  async function handleRestore(versionTimestamp) {
    try {
      await api.restoreMemoryVersion(viewingHistory.memory_id, versionTimestamp);
      closeHistory();
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Programmatically focus the card at focusedIndex when it changes
  useEffect(() => {
    if (focusedIndex >= 0 && listRef.current) {
      const li = listRef.current.children[focusedIndex];
      li?.querySelector("[data-testid='memory-card']")?.focus();
    }
  }, [focusedIndex]);

  function handleCardKeyDown(e, m) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((i) => Math.min(i + 1, memories.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openEdit(m);
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      handleDelete(m.memory_id);
    } else if (e.key === "Escape") {
      closePanel();
    }
  }

  return (
    <div className="flex flex-col md:flex-row gap-5">
      <AlertDialog
        open={pendingDelete !== null}
        title="Delete this memory?"
        description="This action cannot be undone."
        onConfirm={() => handleDelete(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />

      {/* List */}
      <div className="flex-1">
        <div className="flex flex-wrap gap-2.5 mb-4 items-center">
          <h2 className="text-lg font-semibold sm:flex-1 w-full sm:w-auto">Memories</h2>
          <Input
            className="flex-1 min-w-0 sm:flex-none sm:w-44"
            placeholder="Search by meaning…"
            value={searchQuery}
            onChange={handleSearchQueryChange}
          />
          <TagPicker knownTags={knownTags} value={tagFilter} onSelect={handleTagSelect} />
          <Button onClick={openCreate}>+ New</Button>
        </div>
        {isSearchMode && (
          <div
            data-testid="search-topk-control"
            className="flex items-center gap-3 mb-4 text-[13px] text-[var(--text-muted)]"
          >
            <Label htmlFor="search-topk" className="whitespace-nowrap">
              Top K
            </Label>
            <input
              id="search-topk"
              type="range"
              min={1}
              max={100}
              value={searchTopK}
              onChange={(e) => setSearchTopK(Number(e.target.value))}
              className="flex-1 max-w-[200px] cursor-pointer"
              aria-valuemin={1}
              aria-valuemax={100}
              aria-valuenow={searchTopK}
              aria-label="Maximum number of search results"
            />
            <span
              className="font-semibold text-[var(--text)] min-w-[2ch] text-right"
              aria-live="polite"
            >
              {searchTopK}
            </span>
            <span className="text-[11px] text-[var(--text-muted)] hidden sm:inline">
              results
            </span>
          </div>
        )}

        {quotaError && (
          <div
            role="alert"
            data-testid="quota-banner"
            className="mb-3 rounded border p-3 text-[13px]"
            style={{ borderColor: "var(--danger)", color: "var(--danger)" }}
          >
            <strong>Quota or rate limit reached.</strong>{" "}
            <span className="text-[var(--text-muted)]">
              {quotaError} Try again later, or open Setup to review your
              current usage and request more capacity.
            </span>{" "}
            <button
              type="button"
              onClick={goToUsage}
              className="underline cursor-pointer p-0 m-0 font-inherit text-inherit leading-inherit"
              style={{
                color: "var(--danger)",
                background: "transparent",
                border: 0,
                font: "inherit",
              }}
            >
              Open Setup
            </button>
          </div>
        )}
        {error && <p className="text-[var(--danger)] mb-3">{error}</p>}
        {loading && <p className="text-[var(--text-muted)]">Loading…</p>}

        {!loading && memories.length === 0 && (
          <Card className="p-0">
            <EmptyState
              variant="memories"
              title="No memories yet"
              description="Connect an MCP client from the Setup tab — once your agent calls the remember tool, memories show up here. You can also create one by hand below."
              action={
                <div className="flex flex-col sm:flex-row gap-3 items-center">
                  <Button onClick={openCreate}>+ New Memory</Button>
                  <button
                    type="button"
                    onClick={openSetup}
                    className="text-[var(--accent)] underline cursor-pointer bg-transparent border-0 p-0 text-sm font-inherit"
                  >
                    Open Setup
                  </button>
                </div>
              }
            />
          </Card>
        )}

        <ul ref={listRef} className="flex flex-col gap-2.5 list-none m-0 p-0">
          {memories.map((m, i) => (
            <li key={m.memory_id} className="flex items-start">
              <button
                type="button"
                data-testid="memory-card"
                className="bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius)] p-4 cursor-pointer border-l-4 border-l-[var(--accent)] flex-1 text-left"
                onClick={() => openEdit(m)}
                onFocus={() => setFocusedIndex(i)}
                onKeyDown={(e) => handleCardKeyDown(e, m)}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <strong>{m.key}</strong>
                    {m.score !== undefined && (
                      <Badge>{Math.round(m.score * 100)}% match</Badge>
                    )}
                    {m.value_type && m.value_type !== "text" && (
                      <Badge
                        data-testid="type-badge"
                        style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
                      >
                        {typeBadgeLabel(m.value_type)}
                      </Badge>
                    )}
                    {m.expires_at && (
                      <Badge className="border-[var(--amber)] text-[var(--amber)]">Expires {new Date(m.expires_at).toLocaleDateString()}</Badge>
                    )}
                    {m.owner_client_id && (
                      <Badge className="text-[var(--text-muted)]">
                        by {clientNameById[m.owner_client_id] ?? m.owner_client_id}
                      </Badge>
                    )}
                  </div>
                  {m.value_type === "image" ? (
                    <MemoryImage
                      memoryId={m.memory_id}
                      alt={m.key}
                      className="mt-1 max-h-16 object-cover rounded"
                    />
                  ) : m.value_type === "blob" ? (
                    <p className="mt-1 text-[var(--text-muted)] text-[13px]">
                      {m.content_type ?? "Binary file"}
                      {m.size_bytes ? ` · ${formatBytes(m.size_bytes)}` : ""}
                    </p>
                  ) : m.value_type === "text-large" ? (
                    <p className="mt-1 text-[var(--text-muted)] text-[13px] italic">
                      Large text{m.size_bytes ? ` · ${formatBytes(m.size_bytes)}` : ""}
                    </p>
                  ) : (
                    <p className="mt-1 text-[var(--text-muted)] text-[13px] whitespace-pre-wrap">
                      {(m.value ?? "").length > 160
                        ? m.value.slice(0, 160) + "…"
                        : (m.value ?? "")}
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {m.tags.map((t) => (
                      <Badge key={t}>{t}</Badge>
                    ))}
                  </div>
                </div>
              </button>
              <Button
                variant="secondary"
                size="sm"
                className="ml-2 shrink-0 self-center"
                onClick={() => openHistory(m)}
              >
                History
              </Button>
              <Button
                variant="danger"
                size="sm"
                className="ml-2 shrink-0 self-center"
                onClick={() => setPendingDelete(m.memory_id)}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>

        {nextCursor && (
          <div className="text-center mt-4">
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </div>

      {/* Side form */}
      {(creating || editing) && (
        <div className="w-full md:w-[360px]">
          {editing?.value_type === "image" ? (
            <Card>
              <h3 className="mb-4 text-base font-semibold">Image: {editing.key}</h3>
              <MemoryImage
                memoryId={editing.memory_id}
                alt={editing.key}
                className="max-w-full rounded mb-3"
              />
              {(editing.content_type || editing.size_bytes) && (
                <p className="text-[13px] text-[var(--text-muted)] mb-2">
                  {editing.content_type}
                  {editing.size_bytes ? ` · ${formatBytes(editing.size_bytes)}` : ""}
                </p>
              )}
              {editing.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {editing.tags.map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              )}
              <Button variant="secondary" onClick={closePanel}>
                Close
              </Button>
            </Card>
          ) : editing?.value_type === "blob" ? (
            <Card>
              <h3 className="mb-4 text-base font-semibold">Blob: {editing.key}</h3>
              <p className="text-[13px] mb-1">
                {editing.content_type ?? "Binary file"}
              </p>
              {editing.size_bytes && (
                <p className="text-[13px] text-[var(--text-muted)] mb-3">
                  {formatBytes(editing.size_bytes)}
                </p>
              )}
              {editing.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {editing.tags.map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Button onClick={handleBlobDownload}>
                  <Download size={14} className="mr-1" />
                  Download
                </Button>
                <Button variant="secondary" onClick={closePanel}>
                  Close
                </Button>
              </div>
            </Card>
          ) : (
            <Card>
              <h3 className="mb-4 text-base font-semibold">
                {creating ? "New Memory" : `Edit: ${editing.key}`}
              </h3>
              <form onSubmit={creating ? handleCreate : handleUpdate}>
                {creating && (
                  <div className="mb-3">
                    <Label htmlFor="memory-key">Key</Label>
                    <Input
                      id="memory-key"
                      required
                      value={form.key}
                      onChange={(e) => setForm({ ...form, key: e.target.value })}
                      placeholder="unique-key"
                    />
                  </div>
                )}
                <div className="mb-3">
                  <Label htmlFor="memory-value">Value</Label>
                  {contentLoading ? (
                    <p className="text-[var(--text-muted)] text-[13px]">Loading content…</p>
                  ) : (
                    <Textarea
                      id="memory-value"
                      required
                      rows={6}
                      value={form.value}
                      onChange={(e) => setForm({ ...form, value: e.target.value })}
                      placeholder="Memory content…"
                    />
                  )}
                </div>
                <div className="mb-3">
                  <Label htmlFor="memory-tags">Tags (comma-separated)</Label>
                  <Input
                    id="memory-tags"
                    value={form.tags}
                    onChange={(e) => setForm({ ...form, tags: e.target.value })}
                    placeholder="tag1, tag2"
                  />
                </div>
                <div className="mb-4">
                  <Label htmlFor="memory-ttl">Expires in</Label>
                  <Select
                    id="memory-ttl"
                    value={form.ttl}
                    onChange={(e) => setForm({ ...form, ttl: e.target.value })}
                  >
                    {TTL_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </Select>
                </div>
                <div className="flex gap-2">
                  <Button type="submit">Save</Button>
                  <Button variant="secondary" type="button" onClick={closePanel}>
                    Cancel
                  </Button>
                </div>
              </form>
            </Card>
          )}
        </div>
      )}

      {/* Version history panel */}
      {viewingHistory && (
        <div className="w-full md:w-[420px]">
          <Card>
            <h3 className="mb-4 text-base font-semibold">History: {viewingHistory.key}</h3>
            {versionsLoading && <p className="text-[var(--text-muted)]">Loading…</p>}
            {!versionsLoading && versions.length === 0 && (
              <p className="text-[var(--text-muted)] text-sm">No previous versions.</p>
            )}
            <ul className="flex flex-col gap-3 list-none m-0 p-0">
              {versions.map((v) => {
                const isOpen = expandedVersion === v.version_timestamp;
                const truncated =
                  v.value.length > 120 ? v.value.slice(0, 120) + "…" : v.value;
                return (
                  <li
                    key={v.version_timestamp}
                    className="border border-[var(--border)] rounded-[var(--radius)] p-3"
                  >
                    <div className="text-[11px] text-[var(--text-muted)] mb-1">
                      {new Date(v.recorded_at).toLocaleString()}
                    </div>
                    {isOpen ? (
                      <div className="mb-2">
                        <p className="text-[11px] text-[var(--text-muted)] mb-1">
                          Changes vs current
                        </p>
                        <MemoryDiff
                          before={v.value}
                          after={viewingHistory.value}
                        />
                      </div>
                    ) : (
                      <p className="text-[13px] whitespace-pre-wrap mb-2">
                        {truncated}
                      </p>
                    )}
                    <div className="flex gap-2 flex-wrap">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => toggleDiff(v.version_timestamp)}
                        aria-expanded={isOpen}
                        aria-label={
                          isOpen
                            ? "Hide diff against current"
                            : "Show diff against current"
                        }
                      >
                        {isOpen ? "Hide diff" : "Show diff"}
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleRestore(v.version_timestamp)}
                      >
                        Restore
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="mt-4">
              <Button variant="secondary" onClick={closeHistory}>Close</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
