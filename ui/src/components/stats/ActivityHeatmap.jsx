// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo } from "react";
import PropTypes from "prop-types";

// #536 — GitHub-style 7×N calendar grid: one cell per day for the past
// 12 months. Colour intensity scales with event count; older days
// outside the 90-day activity-log retention simply render as empty.

const HEATMAP_DAYS = 365;
const CELL_PX = 11;
const CELL_GAP_PX = 3;
const DAY_LABELS = ["Mon", "Wed", "Fri"];

// Five opacity stops — mirrors GitHub's five-tier heatmap.
const OPACITY_STOPS = [0.3, 0.5, 0.7, 0.85, 1.0];

export function opacityForCount(count, max) {
  if (count <= 0) return 0;
  if (max <= 0) return 0;
  const ratio = count / max;
  // Map ratio ∈ (0, 1] onto the five stops.
  for (let i = 0; i < OPACITY_STOPS.length - 1; i++) {
    if (ratio <= (i + 1) / OPACITY_STOPS.length) return OPACITY_STOPS[i];
  }
  return OPACITY_STOPS[OPACITY_STOPS.length - 1];
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

export function buildGrid(data, today = new Date()) {
  const byDate = new Map((data ?? []).map((d) => [d.date, d.count]));
  const cells = [];
  for (let i = HEATMAP_DAYS - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    cells.push({
      date: isoDate(d),
      count: byDate.get(isoDate(d)) ?? 0,
      dayOfWeek: d.getDay(), // Sunday=0 … Saturday=6
    });
  }
  // Arrange into columns of seven rows (Sun–Sat). Pad the first column
  // with nulls so the calendar aligns to the real weekday of the oldest
  // rendered day.
  const weeks = [];
  let col = new Array(7).fill(null);
  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i];
    col[cell.dayOfWeek] = cell;
    if (cell.dayOfWeek === 6) {
      weeks.push(col);
      col = new Array(7).fill(null);
    }
  }
  // Flush trailing partial column.
  if (col.some((c) => c !== null)) weeks.push(col);
  return { cells, weeks };
}

export default function ActivityHeatmap({ data }) {
  const { cells, weeks } = useMemo(() => buildGrid(data), [data]);
  const maxCount = useMemo(
    () => Math.max(0, ...cells.map((c) => c.count)),
    [cells],
  );
  const totalEvents = useMemo(
    () => cells.reduce((s, c) => s + c.count, 0),
    [cells],
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="inline-flex gap-[3px]" role="grid" aria-label="Activity heatmap">
          {/* Day-of-week labels column */}
          <div
            className="flex flex-col gap-[3px] pr-1 text-[9px] text-[var(--text-muted)] select-none"
            aria-hidden="true"
          >
            {[0, 1, 2, 3, 4, 5, 6].map((dow) => (
              <div
                key={dow}
                className="flex items-center"
                style={{ height: CELL_PX }}
              >
                {DAY_LABELS.includes(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][dow])
                  ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][dow]
                  : ""}
              </div>
            ))}
          </div>
          {weeks.map((col, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]" role="row">
              {col.map((cell, dow) => {
                if (!cell) {
                  return (
                    <div
                      key={dow}
                      role="gridcell"
                      className="rounded-[2px]"
                      style={{ width: CELL_PX, height: CELL_PX }}
                    />
                  );
                }
                const opacity = opacityForCount(cell.count, maxCount);
                const background =
                  cell.count > 0
                    ? `color-mix(in srgb, var(--accent) ${Math.round(opacity * 100)}%, transparent)`
                    : "var(--surface)";
                return (
                  <div
                    key={dow}
                    role="gridcell"
                    title={`${cell.date}: ${cell.count} event${cell.count === 1 ? "" : "s"}`}
                    aria-label={`${cell.date}: ${cell.count} events`}
                    data-count={cell.count}
                    className="rounded-[2px] border border-[var(--border)]"
                    style={{
                      width: CELL_PX,
                      height: CELL_PX,
                      backgroundColor: background,
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[10px] text-[var(--text-muted)]">
        <span>
          {totalEvents} event{totalEvents === 1 ? "" : "s"} in the past year.
        </span>
        <span className="flex items-center gap-1">
          <span>Less</span>
          {OPACITY_STOPS.map((op) => (
            <span
              key={op}
              className="rounded-[2px] border border-[var(--border)]"
              style={{
                width: CELL_PX,
                height: CELL_PX,
                backgroundColor: `color-mix(in srgb, var(--accent) ${Math.round(op * 100)}%, transparent)`,
              }}
            />
          ))}
          <span>More</span>
        </span>
      </div>
      <div className="text-[10px] text-[var(--text-muted)] italic">
        Activity log retention is 90 days — older months render as empty until retention extends.
      </div>
    </div>
  );
}

ActivityHeatmap.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      count: PropTypes.number.isRequired,
    }),
  ),
};

ActivityHeatmap.HEATMAP_DAYS = HEATMAP_DAYS;
