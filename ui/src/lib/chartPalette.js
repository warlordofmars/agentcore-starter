// Copyright (c) 2026 John Carter. All rights reserved.

// Shared colour palette for categorical charts on the Stats tab
// (tag distribution, client contribution, and future force graphs).
// Brand orange leads so the largest / most-active slice always reads
// as "primary". The next four slots track Dashboard.jsx's TOOL_COLORS
// so the two tabs feel cohesive; the last three are distinct non-TOOL
// hues that stay readable against both light + dark backgrounds.
export const SLICE_COLORS = [
  "#e8a020", // brand orange (TOOL_COLORS.remember)
  "#1a73e8", // blue          (TOOL_COLORS.recall)
  "#00897b", // teal          (TOOL_COLORS.list_memories)
  "#9334e8", // purple        (TOOL_COLORS.summarize_context)
  "#34a853", // green         (TOOL_COLORS.search_memories)
  "#fb923c", // orange-500 (extra)
  "#d93025", // red        (TOOL_COLORS.forget)
  "#64748b", // slate      (extra)
];
