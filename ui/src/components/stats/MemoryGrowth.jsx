// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo } from "react";
import PropTypes from "prop-types";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// #537 — cumulative memory count over the selected window, with a
// dotted linear projection for the next ~30 days. The projection uses
// the window-average daily growth rate (delta between first and last
// points divided by span), so 90/365-day windows produce a smoother
// long-horizon trend rather than extrapolating from just the most
// recent days. Projection only renders when there's enough history to
// compute a meaningful rate (≥14 days of data spanning a non-zero
// growth delta).

const PROJECTION_DAYS = 30;
const MIN_HISTORY_DAYS = 14;

export function projectGrowth(history, days = PROJECTION_DAYS) {
  if (!history || history.length < MIN_HISTORY_DAYS) return [];
  const first = history[0].cumulative;
  const last = history[history.length - 1].cumulative;
  const delta = last - first;
  if (delta <= 0) return []; // flat / declining history — don't extrapolate
  const perDay = delta / (history.length - 1);
  const projection = [];
  // `YYYY-MM-DD` parses as UTC; use setUTCDate to add days without
  // a local-timezone / DST shift that could produce off-by-one dates.
  const lastDate = new Date(history[history.length - 1].date);
  for (let i = 1; i <= days; i++) {
    const d = new Date(lastDate);
    d.setUTCDate(d.getUTCDate() + i);
    projection.push({
      date: d.toISOString().slice(0, 10),
      projected: Math.round(last + perDay * i),
    });
  }
  return projection;
}

export default function MemoryGrowth({ data }) {
  const { combined, hasProjection } = useMemo(() => {
    const history = (data ?? []).map((p) => ({
      date: p.date,
      cumulative: p.cumulative,
    }));
    const projection = projectGrowth(history);
    if (projection.length === 0) {
      return { combined: history, hasProjection: false };
    }
    // Copy the `projected` value onto the last actual point so the dashed
    // line starts visibly from that datapoint without duplicating the
    // date row in the combined dataset.
    const anchor = history[history.length - 1];
    const historyWithAnchor = [
      ...history.slice(0, -1),
      { ...anchor, projected: anchor.cumulative },
    ];
    return {
      combined: [...historyWithAnchor, ...projection],
      hasProjection: true,
    };
  }, [data]);

  if (!data?.length) return null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={combined} margin={{ top: 5, right: 10, left: 0, bottom: 30 }}>
        <defs>
          <linearGradient id="growth-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.35} />
            <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.04} />
          </linearGradient>
        </defs>
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
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "var(--text-muted)" }} />
        <Area
          type="monotone"
          dataKey="cumulative"
          name="Memories"
          stroke="var(--accent)"
          strokeWidth={2}
          fill="url(#growth-fill)"
        />
        {hasProjection && (
          <Area
            type="monotone"
            dataKey="projected"
            name="Projected"
            stroke="var(--accent)"
            strokeWidth={2}
            strokeDasharray="5 5"
            fill="none"
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}

MemoryGrowth.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      cumulative: PropTypes.number.isRequired,
    }),
  ),
};
