// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useCallback, useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Play, Pause, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../api.js";

const WINDOWS = ["15m", "1h", "3h", "24h"];
const GROUPS = ["all", "mcp", "api"];
const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];
const POLL_INTERVAL_MS = 10_000;

const LEVEL_STYLES = {
  ERROR:   { background: "rgba(239,68,68,.15)",   color: "var(--danger)",       border: "1px solid rgba(239,68,68,.3)" },
  WARNING: { background: "rgba(234,179,8,.15)",   color: "#ca8a04",             border: "1px solid rgba(234,179,8,.3)" },
  INFO:    { background: "rgba(59,130,246,.12)",  color: "#3b82f6",             border: "1px solid rgba(59,130,246,.3)" },
  DEBUG:   { background: "var(--surface)",        color: "var(--text-muted)",   border: "1px solid var(--border)" },
};

function levelOf(message) {
  try {
    const parsed = JSON.parse(message);
    const raw = (parsed.level || parsed.levelname || parsed.severity || "").toUpperCase();
    return LEVELS.includes(raw) ? raw : "INFO";
  } catch {
    if (/\bERROR\b/i.test(message)) return "ERROR";
    if (/\bWARN/i.test(message)) return "WARNING";
    if (/\bDEBUG\b/i.test(message)) return "DEBUG";
    return "INFO";
  }
}

function formatTs(ms) {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function LogRow({ event }) {
  const [expanded, setExpanded] = useState(false);
  const level = levelOf(event.message);
  const levelStyle = LEVEL_STYLES[level];

  let parsed = null;
  try { parsed = JSON.parse(event.message); } catch { /* not JSON */ }

  const summary = parsed
    ? (parsed.message || parsed.msg || event.message).slice(0, 200)
    : event.message.slice(0, 200);

  return (
    <div
      style={{
        borderBottom: "1px solid var(--border)",
        fontSize: 12,
        fontFamily: "ui-monospace, monospace",
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setExpanded((v) => !v)}
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          padding: "6px 10px",
          cursor: "pointer",
          background: expanded ? "var(--surface)" : "transparent",
          width: "100%",
          border: "none",
          textAlign: "left",
        }}
        className="log-row"
      >
        <span className="log-row-ts" style={{ color: "var(--text-muted)", whiteSpace: "nowrap", flexShrink: 0 }}>
          {formatTs(event.timestamp)}
        </span>
        <span
          style={{
            ...levelStyle,
            borderRadius: 4,
            padding: "1px 6px",
            fontSize: 10,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {level}
        </span>
        <span className="log-row-group" style={{ color: "var(--text-muted)", flexShrink: 0, fontSize: 10 }}>
          {event.log_group.split("/").pop()}
        </span>
        <span className="log-row-msg" style={{ flex: 1, minWidth: 0, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {summary}
        </span>
        <span className="log-row-chev" style={{ color: "var(--text-muted)", flexShrink: 0 }}>
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {expanded && (
        <pre
          style={{
            margin: 0,
            padding: "8px 10px 10px 10px",
            background: "var(--surface)",
            color: "var(--text)",
            overflowX: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {parsed ? JSON.stringify(parsed, null, 2) : event.message}
        </pre>
      )}
    </div>
  );
}

LogRow.propTypes = {
  event: PropTypes.shape({
    timestamp: PropTypes.number.isRequired,
    message: PropTypes.string.isRequired,
    log_group: PropTypes.string.isRequired,
    log_stream: PropTypes.string.isRequired,
    event_id: PropTypes.string.isRequired,
  }).isRequired,
};

export default function LogViewer() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [group, setGroup] = useState("all");
  const [window, setWindow] = useState("1h");
  const [filter, setFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState(new Set(LEVELS));
  const [paused, setPaused] = useState(false);
  const [filterInput, setFilterInput] = useState("");
  const intervalRef = useRef(null);
  const debounceRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getLogs({ group, window, filter });
      setEvents(data.events);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [group, window, filter]);

  // Initial load and refresh when params change
  useEffect(() => {
    load();
  }, [load]);

  // Polling
  useEffect(() => {
    if (paused) {
      clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [load, paused]);

  // Debounce free-text filter input
  function handleFilterInput(e) {
    const val = e.target.value;
    setFilterInput(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setFilter(val), 400);
  }

  function toggleLevel(level) {
    setLevelFilter((prev) => {
      const next = new Set(prev);
      if (next.has(level)) {
        next.delete(level);
      } else {
        next.add(level);
      }
      return next;
    });
  }

  const visibleEvents = events.filter((e) => levelFilter.has(levelOf(e.message)));

  return (
    <div>
      <style>{`
        /* On narrow viewports, restack the log row onto three lines:
             Row 1: timestamp + level pill + chevron (pushed right)
             Row 2: Lambda log-group (small, muted, truncated)
             Row 3: summary (line-clamped to 2 lines with ellipsis)
           Line-clamp keeps the collapsed row compact so long JSON messages
           don't look like the row is permanently expanded. Tap still
           expands to the full pretty-printed JSON in the <pre> below.
           Desktop layout is unchanged. */
        @media (max-width: 640px) {
          .log-row { flex-wrap: wrap !important; }
          .log-row-chev { margin-left: auto !important; }
          .log-row-group {
            flex-basis: 100% !important;
            order: 10 !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
          }
          .log-row-msg {
            flex-basis: 100% !important;
            order: 20 !important;
            display: -webkit-box !important;
            -webkit-line-clamp: 2 !important;
            -webkit-box-orient: vertical !important;
            overflow: hidden !important;
            white-space: normal !important;
            word-break: break-word !important;
          }
        }
      `}</style>

      {/* Toolbar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ fontSize: 18, marginRight: 4 }}>Logs</h2>

        {/* Group selector */}
        <select
          aria-label="Log group"
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          style={{ fontSize: 13 }}
        >
          {GROUPS.map((g) => (
            <option key={g} value={g}>{g === "all" ? "All groups" : g.toUpperCase()}</option>
          ))}
        </select>

        {/* Window selector */}
        <select
          aria-label="Time window"
          value={window}
          onChange={(e) => setWindow(e.target.value)}
          style={{ fontSize: 13 }}
        >
          {WINDOWS.map((w) => <option key={w} value={w}>Last {w}</option>)}
        </select>

        {/* Free-text filter */}
        <input
          style={{ width: 200, fontSize: 13 }}
          placeholder="Filter pattern…"
          value={filterInput}
          onChange={handleFilterInput}
        />

        {/* Level toggles */}
        <div style={{ display: "flex", gap: 4 }}>
          {LEVELS.map((level) => {
            const active = levelFilter.has(level);
            const style = LEVEL_STYLES[level];
            return (
              <button
                key={level}
                onClick={() => toggleLevel(level)}
                style={{
                  ...( active ? style : { background: "transparent", color: "var(--text-muted)", border: "1px solid var(--border)" }),
                  borderRadius: 4,
                  padding: "2px 8px",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {level}
              </button>
            );
          })}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {loading && <RefreshCw size={14} style={{ color: "var(--text-muted)", animation: "spin 1s linear infinite" }} />}
          <button
            onClick={() => setPaused((v) => !v)}
            title={paused ? "Resume live tail" : "Pause live tail"}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 13,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            {paused ? <Play size={13} /> : <Pause size={13} />}
            {paused ? "Resume" : "Pause"}
          </button>
          <button
            onClick={load}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {error && <p style={{ color: "var(--danger)", marginBottom: 10, fontSize: 13 }}>{error}</p>}

      {/* Event list */}
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          overflow: "hidden",
          maxHeight: "calc(100vh - 260px)",
          overflowY: "auto",
        }}
      >
        {!loading && visibleEvents.length === 0 && (
          <p style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
            No log events found.
          </p>
        )}
        {visibleEvents.map((event) => (
          <LogRow key={`${event.log_group}:${event.event_id}:${event.timestamp}`} event={event} />
        ))}
      </div>

      <p style={{ marginTop: 8, fontSize: 11, color: "var(--text-muted)" }}>
        {visibleEvents.length} event{visibleEvents.length === 1 ? "" : "s"} shown
        {paused ? " · paused" : " · live (10 s)"}
      </p>
    </div>
  );
}
