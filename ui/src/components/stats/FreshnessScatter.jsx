// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo } from "react";
import PropTypes from "prop-types";
import {
  CartesianGrid,
  Cell,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

// #538 — freshness scatter: x = days since created, y = days since last
// accessed. The stale-quadrant (upper-right) highlights memories that
// are both old and have not been touched recently — candidate cleanup.
// A scatter needs enough points to read as a distribution; when the
// user has fewer than MIN_POINTS memories this component renders its
// own min-points prompt instead of the chart (GraphCard's empty copy
// only fires for a truly empty `data` prop, not for 1–9 entries).

const MIN_POINTS = 10;
const STALE_THRESHOLD_DAYS = 30;
const STALE_FILL = "var(--danger)";
const FRESH_FILL = "var(--accent)";

export function isStale(point) {
  return (
    point.days_since_created >= STALE_THRESHOLD_DAYS &&
    point.days_since_accessed >= STALE_THRESHOLD_DAYS
  );
}

export function formatScatterTooltip(value, name, entry) {
  const p = entry?.payload ?? {};
  if (name === "days_since_created") return [`${value} days old`, p.key ?? ""];
  if (name === "days_since_accessed") {
    return [`${value} days since access`, p.key ?? ""];
  }
  return [value, name];
}

// Renders the hover card's full body (key + tags + both day counts) so
// the tooltip reads like a memory detail card rather than a bare
// x/y readout. Exported so tests can exercise the key/tag rendering
// without walking recharts' internal tooltip tree.
export function ScatterTooltipContent({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload ?? {};
  return (
    <div
      className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
      data-testid="freshness-tooltip"
    >
      <div className="font-semibold text-[var(--text)]">{p.key}</div>
      {p.tags && p.tags.length > 0 && (
        <div className="text-[var(--text-muted)]">{p.tags.join(", ")}</div>
      )}
      <div className="text-[var(--text-muted)]">
        {p.days_since_created} days old · {p.days_since_accessed} days since access
      </div>
    </div>
  );
}

ScatterTooltipContent.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.array,
};

export function openMemory(point) {
  const data = point?.payload ?? point;
  if (!data || typeof data.key !== "string" || data.key.length === 0) return;
  if (typeof globalThis.dispatchEvent !== "function") return;
  // Dispatch order matches TopRecalled.openMemory — switch tabs first so
  // MemoryBrowser mounts and attaches its listener before the deep-link
  // event fires. Defer by one tick to let React commit the mount.
  globalThis.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "memories" }));
  globalThis.setTimeout(() => {
    globalThis.dispatchEvent(
      new CustomEvent("hive:memory-browser", { detail: { search: data.key } }),
    );
  }, 0);
}

export default function FreshnessScatter({ data }) {
  const { points, hasEnough, maxAxis } = useMemo(() => {
    const list = data ?? [];
    const enough = list.length >= MIN_POINTS;
    const max = list.reduce(
      (m, p) => Math.max(m, p.days_since_created, p.days_since_accessed),
      STALE_THRESHOLD_DAYS,
    );
    return { points: list, hasEnough: enough, maxAxis: max };
  }, [data]);

  if (!hasEnough) {
    return (
      <div className="text-xs text-[var(--text-muted)] italic py-2">
        Freshness needs at least {MIN_POINTS} memories to chart — keep remembering.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <ResponsiveContainer width="100%" height={240}>
        <ScatterChart margin={{ top: 10, right: 12, left: 4, bottom: 28 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          {/* Stale quadrant shading — visible on both themes. */}
          <ReferenceArea
            x1={STALE_THRESHOLD_DAYS}
            x2={maxAxis}
            y1={STALE_THRESHOLD_DAYS}
            y2={maxAxis}
            fill={STALE_FILL}
            fillOpacity={0.08}
            stroke={STALE_FILL}
            strokeOpacity={0.25}
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <XAxis
            type="number"
            dataKey="days_since_created"
            name="days_since_created"
            domain={[0, maxAxis]}
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            label={{
              value: "Days since created",
              position: "insideBottom",
              offset: -12,
              fill: "var(--text-muted)",
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="days_since_accessed"
            name="days_since_accessed"
            domain={[0, maxAxis]}
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            label={{
              value: "Days since access",
              angle: -90,
              position: "insideLeft",
              fill: "var(--text-muted)",
              fontSize: 11,
            }}
          />
          <ZAxis range={[40, 40]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={<ScatterTooltipContent />}
            formatter={formatScatterTooltip}
          />
          <Scatter data={points} onClick={openMemory} cursor="pointer">
            {points.map((p) => {
              const stale = isStale(p);
              return (
                <Cell
                  key={p.memory_id}
                  fill={stale ? STALE_FILL : FRESH_FILL}
                  // Shape differs per-quadrant so users relying on
                  // high-contrast or colour-blind mode still see the
                  // stale distinction without depending on hue alone.
                  stroke={stale ? STALE_FILL : FRESH_FILL}
                  strokeWidth={stale ? 2 : 0}
                  fillOpacity={stale ? 0.95 : 0.75}
                />
              );
            })}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-[var(--text-muted)]">
        <span className="flex items-center gap-1">
          <span
            aria-hidden="true"
            className="inline-block w-2 h-2 rounded-full"
            style={{ backgroundColor: FRESH_FILL }}
          />
          Active (&lt; {STALE_THRESHOLD_DAYS} days since access or creation)
        </span>
        <span className="flex items-center gap-1">
          <span
            aria-hidden="true"
            className="inline-block w-2 h-2 rounded-full ring-1 ring-[var(--danger)]"
            style={{ backgroundColor: STALE_FILL }}
          />
          Stale (≥ {STALE_THRESHOLD_DAYS} days on both axes — candidate cleanup)
        </span>
      </div>
    </div>
  );
}

FreshnessScatter.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      memory_id: PropTypes.string.isRequired,
      key: PropTypes.string.isRequired,
      tags: PropTypes.arrayOf(PropTypes.string),
      days_since_created: PropTypes.number.isRequired,
      days_since_accessed: PropTypes.number.isRequired,
    }),
  ),
};

FreshnessScatter.MIN_POINTS = MIN_POINTS;
FreshnessScatter.STALE_THRESHOLD_DAYS = STALE_THRESHOLD_DAYS;
