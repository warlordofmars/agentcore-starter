// Copyright (c) 2026 John Carter. All rights reserved.
import React from "react";
import changelogRaw from "../../CHANGELOG.md?raw";
import PageLayout from "@/components/PageLayout";

/**
 * Parse the CHANGELOG.md into sections.
 * Each section starts with "## vX.Y.Z — YYYY-MM-DD" and contains ### subsections.
 * Returns an array of { version, date, groups: [{ heading, items }] }
 */
export function parseChangelog(raw) { // NOSONAR — complexity inherent in multi-pass changelog parsing
  const sections = [];
  let current = null;
  let currentGroup = null;

  for (const line of raw.split("\n")) {
    const versionMatch = line.match(/^## (v[\d.]+(?:-[\w.]+)?) — (\d{4}-\d{2}-\d{2})/);
    if (versionMatch) {
      if (current) sections.push(current);
      current = { version: versionMatch[1], date: versionMatch[2], groups: [] };
      currentGroup = null;
      continue;
    }

    if (!current) continue;

    // Stop at "## Earlier releases" or similar non-version headings
    if (line.startsWith("## ")) {
      sections.push(current);
      current = null;
      break;
    }

    const groupMatch = line.match(/^### (.+)/);
    if (groupMatch) {
      currentGroup = { heading: groupMatch[1], items: [] };
      current.groups.push(currentGroup);
      continue;
    }

    const itemMatch = line.match(/^- (.+)/);
    if (itemMatch && currentGroup) {
      // Strip PR refs like (#123, #456) from item text
      currentGroup.items.push(itemMatch[1].replace(/\s*\(#[\d, #]+\)/g, "").trim()); // NOSONAR — input is a static changelog file, not user-supplied
    }
  }

  if (current) sections.push(current);
  return sections;
}

const GROUP_COLORS = {
  Added: "text-green-600 dark:text-green-400",
  Fixed: "text-amber-600 dark:text-amber-400",
  Changed: "text-blue-600 dark:text-blue-400",
  Removed: "text-red-600 dark:text-red-400",
};

function ChangelogSection({ version, date, groups }) {
  return (
    <div className="border-b border-[var(--border)] pb-10 mb-10 last:border-0 last:mb-0 last:pb-0">
      <div className="flex items-baseline gap-4 mb-6">
        <h2 className="text-xl font-bold">{version}</h2>
        <span className="text-sm text-[var(--text-muted)]">{date}</span>
      </div>
      {groups.map((g) => (
        <div key={g.heading} className="mb-4 last:mb-0">
          <h3 className={`text-xs font-semibold uppercase tracking-widest mb-2 ${GROUP_COLORS[g.heading] ?? "text-[var(--text-muted)]"}`}>
            {g.heading}
          </h3>
          <ul className="flex flex-col gap-1.5">
            {g.items.map((item, i) => (
              <li key={`${g.heading}-${i}`} className="text-sm text-[var(--text)] leading-relaxed flex gap-2">
                <span className="text-[var(--text-muted)] shrink-0">—</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default function ChangelogPage() {
  const sections = parseChangelog(changelogRaw);

  return (
    <PageLayout>
      {/* Header */}
      <section className="py-20 px-4 md:px-8 text-center bg-[var(--surface)]">
        <div className="max-w-[1100px] mx-auto">
          <h1 className="text-[2.5rem] font-extrabold mb-4">Changelog</h1>
          <p className="text-[var(--text-muted)] text-lg max-w-[480px] mx-auto leading-relaxed">
            Notable changes in each release of Hive.
          </p>
        </div>
      </section>

      {/* Entries */}
      <section className="py-16 px-4 md:px-8">
        <div className="max-w-[720px] mx-auto">
          {sections.map((s) => (
            <ChangelogSection key={s.version} {...s} />
          ))}
          <p className="text-sm text-[var(--text-muted)] mt-8">
            Older releases are on the{" "}
            <a
              href="https://github.com/warlordofmars/hive/releases"
              className="text-brand no-underline hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              GitHub releases page
            </a>{"."}</p>
        </div>
      </section>
    </PageLayout>
  );
}
