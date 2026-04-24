// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";

const ILLUSTRATIONS = {
  memories: (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <rect x="12" y="20" width="56" height="44" rx="6" stroke="currentColor" strokeWidth="2.5" />
      <rect x="20" y="30" width="24" height="3" rx="1.5" fill="currentColor" opacity=".4" />
      <rect x="20" y="37" width="40" height="3" rx="1.5" fill="currentColor" opacity=".25" />
      <rect x="20" y="44" width="32" height="3" rx="1.5" fill="currentColor" opacity=".25" />
      <circle cx="58" cy="22" r="10" fill="var(--accent)" opacity=".15" />
      <path d="M54 22h8M58 18v8" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  clients: (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <rect x="10" y="28" width="36" height="28" rx="5" stroke="currentColor" strokeWidth="2.5" />
      <rect x="18" y="36" width="20" height="3" rx="1.5" fill="currentColor" opacity=".4" />
      <rect x="18" y="43" width="14" height="3" rx="1.5" fill="currentColor" opacity=".25" />
      <path d="M46 42h8M54 42l-4-4M54 42l-4 4" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="54" y="28" width="16" height="28" rx="5" stroke="var(--accent)" strokeWidth="2" opacity=".5" />
      <rect x="57" y="36" width="10" height="2.5" rx="1.25" fill="var(--accent)" opacity=".5" />
      <rect x="57" y="42" width="7" height="2.5" rx="1.25" fill="var(--accent)" opacity=".35" />
    </svg>
  ),
  activity: (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <circle cx="40" cy="40" r="22" stroke="currentColor" strokeWidth="2.5" />
      <path d="M40 28v13l8 5" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="40" cy="40" r="2" fill="currentColor" opacity=".3" />
    </svg>
  ),
  users: (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
      <circle cx="35" cy="30" r="10" stroke="currentColor" strokeWidth="2.5" />
      <path d="M15 62c0-11 9-18 20-18s20 7 20 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="57" cy="32" r="7" stroke="var(--accent)" strokeWidth="2" opacity=".6" />
      <path d="M44 58c0-7 6-12 13-12" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" opacity=".6" />
    </svg>
  ),
};

export default function EmptyState({ variant, title, description, action }) {
  return (
    <div className="flex flex-col items-center text-center py-12 px-6 text-[var(--text-muted)]">
      <div className="mb-4 opacity-60">
        {ILLUSTRATIONS[variant] ?? ILLUSTRATIONS.memories}
      </div>
      <p className="font-semibold text-[15px] text-[var(--text)] mb-1.5">
        {title}
      </p>
      {description && (
        <p className="text-[13px] max-w-xs leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
