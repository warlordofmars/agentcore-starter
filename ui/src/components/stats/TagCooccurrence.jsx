// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { SLICE_COLORS } from "../../lib/chartPalette.js";

// #540 — tag co-occurrence network. Nodes = tags, edges = the number
// of memories that carry both tags. A custom SVG with a circular
// layout keeps the bundle delta at zero (no react-force-graph /
// d3-force dependency) and gives us deterministic positions that
// render identically under jsdom — the acceptance criteria explicitly
// asks to minimise bundle weight, and a force sim would be a bad
// trade for what's a fundamentally small visualisation (≤ TOP_K tags).
//
// Bundle delta: **0 bytes** — everything is custom SVG + React + the
// existing shared colour palette.

const MIN_TAGS = 5;
const TOP_K_TAGS = 15; // keep the chart readable on a sm:col-2 card
const TOP_K_EDGES = 40; // drop the long tail of weight=1 edges past this
const VIEWBOX = 260; // SVG is rendered square; height == width
const NODE_RADIUS = 5;
const RING_RADIUS = VIEWBOX / 2 - 40; // leave room for labels
const LABEL_RADIUS = RING_RADIUS + 14;

// Project a node index onto the ring. Rotate by -π/2 so the first
// node renders at 12 o'clock rather than 3 o'clock (matches how users
// expect a "first" slice to be positioned on a clock face).
export function polarPosition(index, total, radius = RING_RADIUS) {
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
  const cx = VIEWBOX / 2 + radius * Math.cos(angle);
  const cy = VIEWBOX / 2 + radius * Math.sin(angle);
  return { cx, cy, angle };
}

// Build node + edge lists from the raw `[{source, target, weight}]`
// rows. Endpoint already sorts rows weight-desc so trimming the tail
// keeps the most interesting co-occurrences. Each unique tag becomes
// a node; the node's `weight` is the sum of its incident edges (used
// for hover emphasis + colour assignment order).
export function buildGraph(data) {
  const rows = data ?? [];
  const nodeWeights = new Map();
  for (const { source, target, weight } of rows) {
    nodeWeights.set(source, (nodeWeights.get(source) ?? 0) + weight);
    nodeWeights.set(target, (nodeWeights.get(target) ?? 0) + weight);
  }
  // Highest total-weight tags first. Trim to TOP_K so the ring stays
  // readable; edges touching dropped nodes fall away automatically.
  // Ties are broken alphabetically by tag so DynamoDB scan-order
  // shuffling doesn't cause node positions / colours to drift between
  // otherwise-identical requests.
  const topTags = Array.from(nodeWeights.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, TOP_K_TAGS)
    .map(([tag, weight], i) => ({ tag, index: i, weight }));
  const tagSet = new Set(topTags.map((n) => n.tag));
  // Same tie-breaker rule on edges — weight first, then
  // (source, target) — so equal-weight edges render in a stable order
  // and the trim at TOP_K_EDGES is deterministic.
  const edges = rows
    .filter((e) => tagSet.has(e.source) && tagSet.has(e.target))
    .slice()
    .sort(
      (a, b) =>
        b.weight - a.weight ||
        a.source.localeCompare(b.source) ||
        a.target.localeCompare(b.target),
    )
    .slice(0, TOP_K_EDGES);
  // Surface whether we actually trimmed — the caption below mentions
  // the top-15 cap, and that's only honest when the input had >15
  // tags (exactly-15 should NOT read as "trimmed").
  return {
    nodes: topTags,
    edges,
    trimmed: nodeWeights.size > TOP_K_TAGS,
  };
}

// Map weight → [1, 3] stroke width so heavy edges read as bolder
// without any individual line dominating the chart. Gracefully
// handles the degenerate single-edge case (maxWeight === 1).
export function edgeStrokeWidth(weight, maxWeight) {
  if (maxWeight <= 0) return 1;
  const ratio = Math.min(1, weight / maxWeight);
  return 1 + ratio * 2;
}

export default function TagCooccurrence({ data }) {
  const [hovered, setHovered] = useState(null);
  const { nodes, edges, trimmed } = useMemo(() => buildGraph(data), [data]);

  if (nodes.length < MIN_TAGS) {
    return (
      <div className="text-xs text-[var(--text-muted)] italic py-2">
        Tag co-occurrence appears once at least {MIN_TAGS} tags have
        co-occurred across your memories.
      </div>
    );
  }

  // Precompute node positions so hover lookups are O(1) instead of
  // recomputing trig per pointer-enter.
  const positions = nodes.map((n) => ({
    ...n,
    ...polarPosition(n.index, nodes.length),
  }));
  const positionByTag = new Map(positions.map((p) => [p.tag, p]));
  const maxWeight = edges.reduce((m, e) => Math.max(m, e.weight), 0);

  // Edges touching the hovered tag stay bright; everything else dims.
  // Same rule for nodes — the hovered one plus its neighbours keep
  // their colour/opacity, unrelated tags fade.
  const neighbourTags = new Set();
  if (hovered) {
    neighbourTags.add(hovered);
    for (const e of edges) {
      if (e.source === hovered) neighbourTags.add(e.target);
      if (e.target === hovered) neighbourTags.add(e.source);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
        role="img"
        aria-label="Tag co-occurrence network"
        className="w-full h-auto"
        style={{ maxHeight: 300 }}
      >
        <g>
          {edges.map((e) => {
            const a = positionByTag.get(e.source);
            const b = positionByTag.get(e.target);
            const touched =
              !hovered || e.source === hovered || e.target === hovered;
            return (
              <line
                key={`${e.source}--${e.target}`}
                x1={a.cx}
                y1={a.cy}
                x2={b.cx}
                y2={b.cy}
                stroke="var(--accent)"
                strokeOpacity={touched ? 0.55 : 0.08}
                strokeWidth={edgeStrokeWidth(e.weight, maxWeight)}
              >
                <title>
                  {`${e.source} + ${e.target}: ${e.weight} shared memor${e.weight === 1 ? "y" : "ies"}`}
                </title>
              </line>
            );
          })}
        </g>
        <g>
          {positions.map((n) => {
            const active = !hovered || neighbourTags.has(n.tag);
            const fill = SLICE_COLORS[n.index % SLICE_COLORS.length];
            const labelPos = polarPosition(n.index, nodes.length, LABEL_RADIUS);
            // Anchor labels toward the outside of the ring so they
            // don't overlap the nodes. `text-anchor` flips based on
            // which half of the circle the node lives in.
            const anchor = labelPos.cx < VIEWBOX / 2 ? "end" : "start";
            return (
              <g
                key={n.tag}
                onMouseEnter={() => setHovered(n.tag)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(n.tag)}
                onBlur={() => setHovered(null)}
                tabIndex={0}
                role="img"
                aria-label={`${n.tag}: ${n.weight} co-occurrences`}
                data-tag={n.tag}
                style={{ cursor: "pointer" }}
              >
                <circle
                  cx={n.cx}
                  cy={n.cy}
                  r={hovered === n.tag ? NODE_RADIUS + 2 : NODE_RADIUS}
                  fill={fill}
                  fillOpacity={active ? 1 : 0.2}
                  stroke={hovered === n.tag ? "var(--text)" : "none"}
                  strokeWidth={1}
                />
                <text
                  x={labelPos.cx}
                  y={labelPos.cy}
                  textAnchor={anchor}
                  dominantBaseline="central"
                  fontSize="10"
                  fill="var(--text-muted)"
                  fillOpacity={active ? 1 : 0.3}
                >
                  {n.tag}
                </text>
                <title>{`${n.tag}: ${n.weight} co-occurrences`}</title>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="text-[10px] text-[var(--text-muted)] italic">
        Hover a tag to highlight its connections.
        {trimmed && ` Showing the top ${TOP_K_TAGS} tags by co-occurrence.`}
      </div>
    </div>
  );
}

TagCooccurrence.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      source: PropTypes.string.isRequired,
      target: PropTypes.string.isRequired,
      weight: PropTypes.number.isRequired,
    }),
  ),
};
