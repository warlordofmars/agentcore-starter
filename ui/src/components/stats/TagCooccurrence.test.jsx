// Copyright (c) 2026 John Carter. All rights reserved.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TagCooccurrence, {
  buildGraph,
  edgeStrokeWidth,
  polarPosition,
} from "./TagCooccurrence.jsx";

// Six distinct tags reaches the MIN_TAGS threshold (5) — pair
// everything up so each tag carries at least one edge.
const SIX_TAG_DATA = [
  { source: "a", target: "b", weight: 3 },
  { source: "a", target: "c", weight: 2 },
  { source: "b", target: "c", weight: 1 },
  { source: "d", target: "e", weight: 1 },
  { source: "e", target: "f", weight: 1 },
];

describe("polarPosition", () => {
  it("places the first node at 12 o'clock", () => {
    // angle = -π/2 → cx = centre, cy = centre - r
    const p = polarPosition(0, 4);
    expect(Math.round(p.cx)).toBe(130);
    expect(Math.round(p.cy)).toBeLessThan(130); // above the centre
    expect(p.angle).toBeCloseTo(-Math.PI / 2);
  });

  it("places the second of four nodes at 3 o'clock", () => {
    const p = polarPosition(1, 4);
    expect(Math.round(p.cy)).toBe(130); // vertical centre
    expect(p.cx).toBeGreaterThan(130); // right of centre
  });

  it("accepts a custom radius for label placement", () => {
    const inner = polarPosition(0, 4, 50);
    const outer = polarPosition(0, 4, 100);
    // Both at 12 o'clock so cy is the only differentiator.
    expect(inner.cy).toBeGreaterThan(outer.cy);
  });
});

describe("buildGraph", () => {
  it("returns sorted nodes + matching edges from flat rows", () => {
    const { nodes, edges } = buildGraph(SIX_TAG_DATA);
    // Six unique tags in the dataset, all within TOP_K_TAGS=15.
    expect(nodes.map((n) => n.tag).sort()).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(edges).toHaveLength(5);
    // Highest-weight tag is "a" (3 + 2 = 5) — should be first node.
    expect(nodes[0].tag).toBe("a");
  });

  it("drops edges whose endpoints fall outside the top-K tag slice", () => {
    // Build 17 tags so the TOP_K_TAGS=15 cap kicks in. The last two
    // tags (p, q) should get dropped and any edges touching them
    // should drop with them.
    const rows = [];
    for (let i = 0; i < 17; i++) {
      const a = `t${i}`;
      const b = `t${(i + 1) % 17}`;
      rows.push({ source: a, target: b, weight: 20 - i });
    }
    const { nodes, edges } = buildGraph(rows);
    expect(nodes).toHaveLength(15);
    const tagSet = new Set(nodes.map((n) => n.tag));
    for (const e of edges) {
      expect(tagSet.has(e.source) && tagSet.has(e.target)).toBe(true);
    }
  });

  it("breaks equal-weight ties by source then target for edge ordering", () => {
    // Two edges share both weight (5) AND source ("a"), so the third
    // tie-breaker (`target.localeCompare`) decides order. Without it
    // the output would depend on input order, which is non-stable
    // once the data comes from a DynamoDB scan.
    const { edges } = buildGraph([
      { source: "a", target: "z", weight: 5 },
      { source: "a", target: "b", weight: 5 },
      { source: "c", target: "d", weight: 1 },
    ]);
    const ab = edges.findIndex((e) => e.source === "a" && e.target === "b");
    const az = edges.findIndex((e) => e.source === "a" && e.target === "z");
    expect(ab).toBeLessThan(az);
  });

  it("returns empty lists for missing / empty input", () => {
    expect(buildGraph()).toEqual({ nodes: [], edges: [], trimmed: false });
    expect(buildGraph([])).toEqual({ nodes: [], edges: [], trimmed: false });
  });
});

describe("edgeStrokeWidth", () => {
  it("returns 1 as the floor for zero max weight", () => {
    expect(edgeStrokeWidth(5, 0)).toBe(1);
  });

  it("scales from 1 to 3 as weight approaches max", () => {
    expect(edgeStrokeWidth(0, 10)).toBe(1);
    expect(edgeStrokeWidth(10, 10)).toBe(3);
    expect(edgeStrokeWidth(5, 10)).toBe(2);
  });

  it("clamps over-max weights to the top of the range", () => {
    // Defensive: callers might feed max that lags behind the edge
    // array on a re-render. Don't let a weight ratio > 1 produce a
    // stroke width > 3.
    expect(edgeStrokeWidth(20, 10)).toBe(3);
  });
});

describe("TagCooccurrence", () => {
  it("renders an explanatory caption when fewer than MIN_TAGS tags", () => {
    render(
      <TagCooccurrence data={[{ source: "a", target: "b", weight: 1 }]} />,
    );
    expect(
      screen.getByText(/Tag co-occurrence appears once at least 5 tags have co-occurred/),
    ).toBeTruthy();
  });

  it("renders the caption for missing data", () => {
    render(<TagCooccurrence />);
    expect(
      screen.getByText(/Tag co-occurrence appears once at least 5 tags have co-occurred/),
    ).toBeTruthy();
  });

  it("renders an SVG with one node per tag when the threshold is met", () => {
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    // Six unique tags across SIX_TAG_DATA → six circles.
    expect(container.querySelectorAll("circle")).toHaveLength(6);
    // All five edges show up as <line> elements.
    expect(container.querySelectorAll("line")).toHaveLength(5);
  });

  it("hover dims unrelated edges and nodes", () => {
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    // Hover node "a". Tags a, b, c are its neighbours; d/e/f are not.
    const aGroup = container.querySelector('g[data-tag="a"]');
    fireEvent.mouseEnter(aGroup);
    // The edge between d and e touches neither "a" nor any of a's
    // neighbours — it should be dimmed (opacity 0.08).
    const edges = container.querySelectorAll("line");
    const deEdge = Array.from(edges).find((line) => {
      const title = line.querySelector("title")?.textContent ?? "";
      return title.includes("d + e") || title.includes("e + d");
    });
    expect(deEdge.getAttribute("stroke-opacity")).toBe("0.08");
    fireEvent.mouseLeave(aGroup);
    // After leave, all edges return to the un-dimmed opacity.
    expect(deEdge.getAttribute("stroke-opacity")).toBe("0.55");
  });

  it("hovering a target-side tag still resolves its source neighbour", () => {
    // Covers the `e.target === hovered` branch — without this, the
    // only path that fires in `SIX_TAG_DATA` is the source-side
    // match because "a" is never on the target side.
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    const cGroup = container.querySelector('g[data-tag="c"]');
    fireEvent.mouseEnter(cGroup);
    const edges = container.querySelectorAll("line");
    // (a, c) edge should stay bright because "a" is a target-side
    // neighbour of "c"; the 117-branch add on source must fire.
    const acEdge = Array.from(edges).find((line) => {
      const title = line.querySelector("title")?.textContent ?? "";
      return title.includes("a + c");
    });
    expect(acEdge.getAttribute("stroke-opacity")).toBe("0.55");
    fireEvent.mouseLeave(cGroup);
  });

  it("keyboard focus also triggers the hover emphasis", () => {
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    const aGroup = container.querySelector('g[data-tag="a"]');
    fireEvent.focus(aGroup);
    const aCircle = aGroup.querySelector("circle");
    // Hovered node's radius bumps from 5 to 7 so screen-reader users
    // navigating via tab can see the current focus.
    expect(aCircle.getAttribute("r")).toBe("7");
    fireEvent.blur(aGroup);
    expect(aCircle.getAttribute("r")).toBe("5");
  });

  it("mentions the top-15 cap only when the chart is actually trimmed", () => {
    const { container: small } = render(
      <TagCooccurrence data={SIX_TAG_DATA} />,
    );
    expect(small.textContent).not.toContain("Showing the top 15");

    // Exactly 15 tags — should NOT read as trimmed, even though
    // `nodes.length === TOP_K_TAGS` (15). Build 15 tags in a ring
    // so each has at least one edge.
    const exactly15 = [];
    for (let i = 0; i < 15; i++) {
      exactly15.push({
        source: `t${i}`,
        target: `t${(i + 1) % 15}`,
        weight: 20 - i,
      });
    }
    const { container: fifteen } = render(<TagCooccurrence data={exactly15} />);
    expect(fifteen.textContent).not.toContain("Showing the top 15");

    // Fill past the cap — 17 tags, TOP_K_TAGS trims to 15.
    const rows = [];
    for (let i = 0; i < 17; i++) {
      rows.push({ source: `t${i}`, target: `t${(i + 1) % 17}`, weight: 20 - i });
    }
    const { container: large } = render(<TagCooccurrence data={rows} />);
    expect(large.textContent).toContain("Showing the top 15");
  });

  it("singular copy when an edge has weight 1", () => {
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    // Edge (b, c, 1) should produce "1 shared memory" (singular), not "memories".
    const edges = container.querySelectorAll("line");
    const bcEdge = Array.from(edges).find((line) => {
      const title = line.querySelector("title")?.textContent ?? "";
      return title.includes("b + c");
    });
    expect(bcEdge.querySelector("title").textContent).toMatch(/1 shared memory/);
  });

  it("label anchors flip between 'start' and 'end' based on hemisphere", () => {
    const { container } = render(<TagCooccurrence data={SIX_TAG_DATA} />);
    const texts = container.querySelectorAll("text");
    const anchors = new Set(
      Array.from(texts).map((t) => t.getAttribute("text-anchor")),
    );
    // With six tags distributed around the ring we expect both
    // anchor values to appear — "end" on the left side, "start" on
    // the right.
    expect(anchors.has("start")).toBe(true);
    expect(anchors.has("end")).toBe(true);
  });
});
