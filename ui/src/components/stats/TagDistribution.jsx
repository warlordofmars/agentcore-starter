// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { SLICE_COLORS } from "../../lib/chartPalette.js";

// #537 — donut chart of memory counts per tag. Clicking a slice jumps to
// the Memories tab pre-filtered by that tag.

const TOP_N = 8;
const OTHER_COLOR = "var(--text-muted)";

export function buildSlices(data) {
  const sorted = [...(data ?? [])].sort((a, b) => b.count - a.count);
  const head = sorted.slice(0, TOP_N);
  const tail = sorted.slice(TOP_N);
  const slices = head.map((d) => ({ tag: d.tag, count: d.count }));
  if (tail.length > 0) {
    const otherCount = tail.reduce((sum, d) => sum + d.count, 0);
    slices.push({ tag: "Other", count: otherCount, isOther: true });
  }
  return slices;
}

export function filterByTag(tag) {
  if (typeof globalThis.dispatchEvent !== "function") return;
  // Tab-switch first so MemoryBrowser mounts and attaches its
  // `hive:memory-browser` listener before we fire the deep-link event —
  // otherwise the event is dispatched before the listener exists and is
  // silently dropped. Same reasoning as TopRecalled.openMemory.
  globalThis.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "memories" }));
  globalThis.setTimeout(() => {
    globalThis.dispatchEvent(
      new CustomEvent("hive:memory-browser", { detail: { tag } }),
    );
  }, 0);
}

export function formatTagTooltip(value, name) {
  return [`${value} memories`, name];
}

// Extracted for direct testability — recharts doesn't actually paint the
// slices in jsdom, so the inline Pie `onClick` would never fire from a
// render-level test. Accepts both raw slice objects and Recharts-style
// `{ payload }` wrappers.
export function handlePieSliceClick(arg) {
  const slice = arg?.payload ?? arg;
  if (!slice || slice.isOther || typeof slice.tag !== "string" || !slice.tag) {
    return;
  }
  filterByTag(slice.tag);
}

export default function TagDistribution({ data }) {
  const slices = useMemo(() => buildSlices(data), [data]);
  // Empty handling lives on the parent <GraphCard> — when `data` is
  // empty/missing it never renders children, so this component always
  // has at least one slice to draw.

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={slices}
          dataKey="count"
          nameKey="tag"
          innerRadius={50}
          outerRadius={90}
          paddingAngle={2}
          onClick={handlePieSliceClick}
          cursor="pointer"
        >
          {slices.map((s, i) => (
            <Cell
              key={s.tag}
              fill={s.isOther ? OTHER_COLOR : SLICE_COLORS[i % SLICE_COLORS.length]}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 12 }}
          formatter={formatTagTooltip}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "var(--text-muted)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

TagDistribution.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      tag: PropTypes.string.isRequired,
      count: PropTypes.number.isRequired,
    }),
  ),
};
