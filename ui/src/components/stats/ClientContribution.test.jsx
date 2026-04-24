// Copyright (c) 2026 John Carter. All rights reserved.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ClientContribution, {
  makeLegendFormatter,
  makeTooltipFormatter,
  pivotByDate,
  resolveClientName,
} from "./ClientContribution.jsx";

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const TWO_CLIENT_DATA = [
  { date: "2026-04-01", client_id: "c1", count: 3 },
  { date: "2026-04-01", client_id: "c2", count: 2 },
  { date: "2026-04-02", client_id: "c1", count: 1 },
];

describe("resolveClientName", () => {
  it("returns the display name when present", () => {
    expect(resolveClientName("c1", { c1: "Claude Code" })).toBe("Claude Code");
  });

  it("falls back to the first 8 chars of the client id", () => {
    expect(resolveClientName("abcdefghij", {})).toBe("abcdefgh");
  });

  it("handles missing name map and missing id gracefully", () => {
    expect(resolveClientName("c1")).toBe("c1");
    expect(resolveClientName("", { c1: "n" })).toBe("unknown");
    expect(resolveClientName(undefined, { c1: "n" })).toBe("unknown");
  });

  it("treats empty-string display name as missing", () => {
    // A blank `client_name` (seen when a client is registered without
    // one) shouldn't surface as a blank legend entry — fall back to id.
    expect(resolveClientName("abcdefgh9", { abcdefgh9: "" })).toBe("abcdefgh");
  });
});

describe("pivotByDate", () => {
  it("pivots flat entries into per-date rows keyed by client id", () => {
    const { rows, clientIds } = pivotByDate(TWO_CLIENT_DATA);
    expect(clientIds).toEqual(["c1", "c2"]);
    expect(rows).toEqual([
      { date: "2026-04-01", c1: 3, c2: 2 },
      { date: "2026-04-02", c1: 1 },
    ]);
  });

  it("returns empty rows + empty ids for missing/empty input", () => {
    expect(pivotByDate(undefined)).toEqual({ rows: [], clientIds: [] });
    expect(pivotByDate([])).toEqual({ rows: [], clientIds: [] });
  });

  it("sorts rows ascending by date even when input is out of order", () => {
    const { rows } = pivotByDate([
      { date: "2026-04-03", client_id: "c1", count: 1 },
      { date: "2026-04-01", client_id: "c1", count: 2 },
    ]);
    expect(rows.map((r) => r.date)).toEqual(["2026-04-01", "2026-04-03"]);
  });
});

describe("makeTooltipFormatter / makeLegendFormatter", () => {
  it("tooltip formatter wraps value + resolved name tuple", () => {
    const fmt = makeTooltipFormatter({ c1: "Claude Code" });
    expect(fmt(5, "c1")).toEqual([5, "Claude Code"]);
  });

  it("tooltip formatter falls back to id prefix when no name map", () => {
    const fmt = makeTooltipFormatter();
    expect(fmt(1, "abcdefghijkl")).toEqual([1, "abcdefgh"]);
  });

  it("legend formatter resolves the value against the name map", () => {
    const fmt = makeLegendFormatter({ c1: "Claude Code" });
    expect(fmt("c1")).toBe("Claude Code");
  });

  it("legend formatter falls back for unknown ids", () => {
    const fmt = makeLegendFormatter({});
    expect(fmt("cursorclient")).toBe("cursorcl");
  });
});

describe("ClientContribution", () => {
  it("renders an explanatory caption when fewer than 2 clients", () => {
    render(<ClientContribution data={[{ date: "d", client_id: "c1", count: 1 }]} />);
    expect(
      screen.getByText(/two or more OAuth clients have recorded activity/),
    ).toBeTruthy();
  });

  it("renders the caption when data is missing", () => {
    render(<ClientContribution />);
    expect(
      screen.getByText(/two or more OAuth clients have recorded activity/),
    ).toBeTruthy();
  });

  it("renders the chart container when 2+ clients are present", () => {
    const { container } = render(
      <ClientContribution
        data={TWO_CLIENT_DATA}
        clientNames={{ c1: "Claude Code", c2: "Cursor" }}
      />,
    );
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
