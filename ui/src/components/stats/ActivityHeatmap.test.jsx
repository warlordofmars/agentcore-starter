// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ActivityHeatmap, { buildGrid, opacityForCount } from "./ActivityHeatmap.jsx";

describe("opacityForCount", () => {
  it("returns 0 for zero count", () => {
    expect(opacityForCount(0, 10)).toBe(0);
  });

  it("returns 0 when max is 0 even if count > 0", () => {
    // Defensive — max should be >= count, but guard against degenerate data.
    expect(opacityForCount(3, 0)).toBe(0);
  });

  it("returns smallest stop for the lightest bucket", () => {
    expect(opacityForCount(1, 10)).toBe(0.3);
  });

  it("returns highest stop for count === max", () => {
    expect(opacityForCount(10, 10)).toBe(1);
  });

  it("monotonically increases across the five stops", () => {
    const opacities = [2, 4, 6, 8, 10].map((c) => opacityForCount(c, 10));
    for (let i = 1; i < opacities.length; i++) {
      expect(opacities[i]).toBeGreaterThanOrEqual(opacities[i - 1]);
    }
  });
});

describe("buildGrid", () => {
  it("produces 365 cells for the default HEATMAP_DAYS span", () => {
    const { cells } = buildGrid([]);
    expect(cells).toHaveLength(365);
  });

  it("puts today's cell at the end of the cells array", () => {
    const today = new Date("2026-04-19T12:00:00Z");
    const { cells } = buildGrid([{ date: "2026-04-19", count: 7 }], today);
    expect(cells[cells.length - 1].date).toBe("2026-04-19");
    expect(cells[cells.length - 1].count).toBe(7);
  });

  it("leaves cells without matching data at count 0", () => {
    const today = new Date("2026-04-19T12:00:00Z");
    const { cells } = buildGrid([{ date: "2026-04-19", count: 3 }], today);
    const hit = cells.filter((c) => c.count > 0);
    expect(hit).toHaveLength(1);
  });

  it("arranges cells into columns of seven days each", () => {
    const { weeks } = buildGrid([]);
    // 365 days across 7-day columns = 53 partial/full columns.
    expect(weeks.length).toBeGreaterThanOrEqual(52);
    expect(weeks.length).toBeLessThanOrEqual(54);
    // Every column has exactly 7 slots (some may be null for partial weeks).
    for (const col of weeks) {
      expect(col).toHaveLength(7);
    }
  });
});

const _sampleData = [
  { date: "2026-04-19", count: 10 },
  { date: "2026-04-18", count: 3 },
  { date: "2026-04-17", count: 1 },
];

describe("ActivityHeatmap", () => {
  it("renders the calendar grid with role='grid'", () => {
    render(<ActivityHeatmap data={_sampleData} />);
    expect(screen.getByRole("grid", { name: /activity heatmap/i })).toBeTruthy();
  });

  it("renders the 90-day retention footnote", () => {
    render(<ActivityHeatmap data={_sampleData} />);
    expect(
      screen.getByText(/activity log retention is 90 days/i),
    ).toBeTruthy();
  });

  it("renders a Less/More legend with one swatch per opacity stop", () => {
    const { container } = render(<ActivityHeatmap data={_sampleData} />);
    expect(screen.getByText("Less")).toBeTruthy();
    expect(screen.getByText("More")).toBeTruthy();
    // 5 opacity stops in the legend, plus the cells in the grid. Count the
    // legend swatches specifically: they're the siblings of the Less label.
    const legendLabel = screen.getByText("Less");
    const legend = legendLabel.parentElement;
    const swatches = legend.querySelectorAll("span.rounded-\\[2px\\]");
    expect(swatches.length).toBe(5);
    // Sanity check — should find both spans in document.
    expect(container.textContent).toMatch(/Less.*More/);
  });

  it("shows a total-events summary (pluralised)", () => {
    render(<ActivityHeatmap data={_sampleData} />);
    // 10 + 3 + 1 = 14
    expect(screen.getByText(/14 events in the past year/i)).toBeTruthy();
  });

  it("uses singular 'event' when total is 1", () => {
    render(<ActivityHeatmap data={[{ date: "2026-04-19", count: 1 }]} />);
    expect(screen.getByText(/1 event in the past year/i)).toBeTruthy();
  });

  it("handles undefined data without error", () => {
    render(<ActivityHeatmap />);
    expect(screen.getByText(/0 events in the past year/i)).toBeTruthy();
  });

  it("handles empty data array without error", () => {
    render(<ActivityHeatmap data={[]} />);
    expect(screen.getByText(/0 events in the past year/i)).toBeTruthy();
  });

  it("sets a tooltip title with date and singular event for count=1", () => {
    render(<ActivityHeatmap data={[{ date: "2026-04-19", count: 1 }]} />);
    const cell = document.querySelector('[data-count="1"]');
    expect(cell).toBeTruthy();
    expect(cell.getAttribute("title")).toBe("2026-04-19: 1 event");
  });

  it("uses plural 'events' in the tooltip for count>1", () => {
    render(<ActivityHeatmap data={[{ date: "2026-04-19", count: 5 }]} />);
    const cell = document.querySelector('[data-count="5"]');
    expect(cell.getAttribute("title")).toBe("2026-04-19: 5 events");
  });

  it("applies color-mix accent background to non-zero cells", () => {
    render(<ActivityHeatmap data={[{ date: "2026-04-19", count: 10 }]} />);
    const cell = document.querySelector('[data-count="10"]');
    // The inline style string is set verbatim by React even if jsdom doesn't
    // evaluate color-mix — assert the substring is present.
    expect(cell.getAttribute("style")).toContain("color-mix");
    expect(cell.getAttribute("style")).toContain("var(--accent)");
  });

  it("zero-count cells do NOT carry the accent color-mix", () => {
    render(<ActivityHeatmap data={[{ date: "2026-04-19", count: 5 }]} />);
    // Find any cell with data-count="0"; there should be plenty (365 - 1).
    const cell = document.querySelector('[data-count="0"]');
    expect(cell).toBeTruthy();
    expect(cell.getAttribute("style")).not.toContain("color-mix");
  });
});
