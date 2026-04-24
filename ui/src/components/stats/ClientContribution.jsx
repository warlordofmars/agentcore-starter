// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo } from "react";
import PropTypes from "prop-types";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SLICE_COLORS } from "../../lib/chartPalette.js";

// #539 — stacked bar chart of activity events per day, segmented by
// OAuth client (reads, writes, deletes — anything that shows up in the
// activity log). Auto-hides with an explanatory caption when the user
// has only one OAuth client actor, since a single-colour stack reads
// as noise.

// Short fallback label when we have no display name for a client id —
// the first 8 chars keeps client ids distinguishable on the legend
// without overflowing to a long uuid.
export function resolveClientName(clientId, nameMap) {
  const name = nameMap?.[clientId];
  if (typeof name === "string" && name.length > 0) return name;
  if (typeof clientId !== "string" || clientId.length === 0) return "unknown";
  return clientId.slice(0, 8);
}

// Recharts calls Tooltip/Legend formatters once per rendered segment;
// jsdom doesn't paint the SVG so those inline arrows would never fire
// from a component render test. Extract named factories so tests hit
// them directly (same pattern as TagDistribution.handlePieSliceClick).
export function makeTooltipFormatter(nameMap) {
  return (value, name) => [value, resolveClientName(name, nameMap)];
}

export function makeLegendFormatter(nameMap) {
  return (value) => resolveClientName(value, nameMap);
}

// Pivot the flat `[{date, client_id, count}]` entries into
// `[{date, <client_id>: count, ...}]` rows so recharts' Bar stacking
// works (recharts needs one column per stack key).
export function pivotByDate(data) {
  const byDate = new Map();
  const clientIds = new Set();
  for (const entry of data ?? []) {
    clientIds.add(entry.client_id);
    // Resolve the row via a single Map read so we don't chain a
    // nullable .get() into a property write — keeps SonarCloud's
    // null-deref check happy without changing behaviour (the row
    // always exists after the ?? below).
    const row = byDate.get(entry.date) ?? { date: entry.date };
    row[entry.client_id] = entry.count;
    byDate.set(entry.date, row);
  }
  return {
    rows: Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date)),
    clientIds: Array.from(clientIds).sort((a, b) => a.localeCompare(b)),
  };
}

export default function ClientContribution({ data, clientNames }) {
  const { rows, clientIds } = useMemo(() => pivotByDate(data), [data]);

  if (clientIds.length < 2) {
    return (
      <div className="text-xs text-[var(--text-muted)] italic py-2">
        Contribution breakdown appears once two or more OAuth clients have
        recorded activity on your behalf.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 30 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          angle={-45}
          textAnchor="end"
          height={60}
          minTickGap={32}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
        />
        <Tooltip
          cursor={{ fill: "var(--surface)" }}
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
          formatter={makeTooltipFormatter(clientNames)}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: "var(--text-muted)" }}
          formatter={makeLegendFormatter(clientNames)}
        />
        {clientIds.map((cid, i) => (
          <Bar
            key={cid}
            dataKey={cid}
            name={cid}
            stackId="events"
            fill={SLICE_COLORS[i % SLICE_COLORS.length]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

ClientContribution.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      client_id: PropTypes.string.isRequired,
      count: PropTypes.number.isRequired,
    }),
  ),
  clientNames: PropTypes.objectOf(PropTypes.string),
};
