// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import { diffWords } from "diff";

// Inline word-level diff. We use word granularity (rather than chars
// or lines) because memory values are typically short prose — word
// diffs read clearly and still surface small edits. For very long
// multi-line memories the same renderer works acceptably.
//
// Colour is driven by CSS variables so dark-mode and light-mode
// both look clean without extra branching.
export default function MemoryDiff({ before, after }) {
  const parts = diffWords(before ?? "", after ?? "");
  return (
    <pre
      data-testid="memory-diff"
      className="m-0 p-2 rounded bg-[var(--surface)] border border-[var(--border)] text-[13px] whitespace-pre-wrap font-[inherit] leading-relaxed"
    >
      {parts.map((part, i) => {
        if (part.added) {
          return (
            <ins
              key={i}
              className="no-underline bg-[var(--success-surface,rgba(16,185,129,0.15))]"
              style={{ color: "var(--success)" }}
            >
              {part.value}
            </ins>
          );
        }
        if (part.removed) {
          return (
            <del
              key={i}
              className="bg-[var(--danger-surface,rgba(239,68,68,0.15))]"
              style={{ color: "var(--danger)" }}
            >
              {part.value}
            </del>
          );
        }
        return (
          <span key={i} className="text-[var(--text-muted)]">
            {part.value}
          </span>
        );
      })}
    </pre>
  );
}
