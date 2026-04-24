// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import PropTypes from "prop-types";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// #537 — horizontal bar chart of the top-N most-recalled memories.
// Clicking a bar dispatches a `hive:memory-browser` event (search mode
// set to the memory's key) and a `hive:switch-tab` event to jump to the
// Memories tab.

export function formatRecallTooltip(value) {
  return [`${value} recalls`, ""];
}

export function openMemory(memory) {
  // Recharts event handlers wrap the original datum in a `.payload`
  // field; accept either shape defensively so the click-through works
  // regardless of which recharts version is installed.
  const data = memory?.payload ?? memory;
  if (!data || typeof data.key !== "string" || data.key.length === 0) return;
  if (typeof globalThis.dispatchEvent !== "function") return;
  // Dispatch order matters: the tab-switch fires first so MemoryBrowser
  // actually mounts (it's conditionally rendered in App.jsx) and its
  // `hive:memory-browser` listener is attached before the deep-link
  // event fires. Defer the listener-targeted event by one tick to let
  // React commit the mount.
  globalThis.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "memories" }));
  globalThis.setTimeout(() => {
    globalThis.dispatchEvent(
      new CustomEvent("hive:memory-browser", { detail: { search: data.key } }),
    );
  }, 0);
}

export default function TopRecalled({ data }) {
  // Empty handling lives on the parent <GraphCard> — when `data` is
  // empty/missing it never renders children, so this component always
  // has at least one bar to draw.

  // Recharts BarChart with `layout='vertical'` draws horizontal bars. Keep
  // bars at a fixed 18px, full-width container, YAxis as the category axis.
  const height = Math.max(120, data.length * 26);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 5, right: 16, left: 8, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
        <YAxis
          type="category"
          dataKey="key"
          width={140}
          tick={{ fontSize: 11, fill: "var(--text)" }}
          interval={0}
        />
        <Tooltip
          cursor={{ fill: "var(--surface)" }}
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 12 }}
          formatter={formatRecallTooltip}
        />
        <Bar
          dataKey="recall_count"
          fill="var(--accent)"
          radius={[0, 4, 4, 0]}
          onClick={openMemory}
          cursor="pointer"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

TopRecalled.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      memory_id: PropTypes.string.isRequired,
      key: PropTypes.string.isRequired,
      recall_count: PropTypes.number.isRequired,
    }),
  ),
};
