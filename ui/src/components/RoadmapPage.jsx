// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useMemo, useState } from "react";
import PageLayout from "@/components/PageLayout";

// Public GitHub REST API — unauth, rate-limited per caller (the
// visitor's IP, not our CloudFront edge, because the browser calls
// api.github.com directly). 60 req/hour in the unauth quota is
// plenty for a marketing page; browser HTTP caching + GitHub's
// ETag revalidation further reduce real traffic.
const ISSUES_URL =
  "https://api.github.com/repos/warlordofmars/hive/issues?" +
  "labels=public-roadmap&state=all&per_page=100";

// Columns map to `roadmap:<col>` labels on each issue. We deliberately
// use a dedicated `roadmap:*` namespace rather than reusing the
// existing `status:*` labels (which `label-check.yml` already treats
// as the required backlog-workflow status — `status:ready`,
// `status:blocked`, `status:needs-info`, `status:design-needed`).
// Shipped column is closed-state regardless of label so recently-
// merged work shows up automatically without a manual label flip.
const COLUMNS = [
  { id: "now", title: "Now", blurb: "In progress — landing soon." },
  { id: "next", title: "Next", blurb: "Planned for the next release or two." },
  { id: "later", title: "Later", blurb: "On the backlog — we'll get to it." },
  { id: "shipped", title: "Shipped", blurb: "Already live — recent highlights." },
];

// Known area labels — kept in sync with the taxonomy in CLAUDE.md
// (§Backlog labels and milestones → Area).
const AREA_LABELS = [
  "ui", "ux", "a11y", "api", "mcp", "auth", "infra", "ci", "dx", "sdk",
  "security", "compliance", "docs", "design", "performance",
  "observability", "marketing", "seo", "growth", "ops", "reliability",
];

// GitHub labels can come as either `{name: "foo"}` objects or bare
// strings depending on the payload shape. Normalise here so callers
// can always treat them as strings.
function _labelNames(issue) {
  const raw = issue.labels ?? [];
  return raw.map((l) => (typeof l === "string" ? l : l.name));
}

// Exported for unit testing in isolation. Takes the raw GitHub
// issues payload and returns a `{columnId: [issue, ...]}` map.
export function _bucketByColumn(issues) {
  const buckets = { now: [], next: [], later: [], shipped: [] };
  for (const issue of issues) {
    // GitHub's /issues endpoint returns PRs too (they share an id
    // space) — skip anything with a `pull_request` field so the
    // roadmap doesn't accidentally surface code-review work.
    if (issue.pull_request) continue;
    if (issue.state === "closed") {
      buckets.shipped.push(issue);
      continue;
    }
    const labels = _labelNames(issue);
    if (labels.includes("roadmap:now")) buckets.now.push(issue);
    else if (labels.includes("roadmap:next")) buckets.next.push(issue);
    else if (labels.includes("roadmap:later")) buckets.later.push(issue);
    // Items with `public-roadmap` but no roadmap:* label are
    // intentionally omitted — the roadmap is curated, not a dump
    // of every tagged issue.
  }
  // Shipped column is time-ordered desc (most-recent first), capped
  // to the last 8 so the marketing page doesn't scroll forever.
  buckets.shipped.sort((a, b) =>
    (b.closed_at ?? "").localeCompare(a.closed_at ?? ""),
  );
  buckets.shipped = buckets.shipped.slice(0, 8);
  return buckets;
}

// Area label → short tag rendered on each card. Derived per issue so
// cards group visually at a glance.
function _pickArea(issue) {
  const labels = _labelNames(issue);
  return labels.find((l) => AREA_LABELS.includes(l)) ?? null;
}

function RoadmapCard({ issue }) {
  const area = _pickArea(issue);
  const reactions = issue.reactions?.total_count ?? 0;
  return (
    <li className="border border-[var(--border)] rounded p-3 bg-[var(--surface)] flex flex-col gap-2">
      <a
        href={issue.html_url}
        target="_blank"
        rel="noreferrer"
        className="text-[var(--text)] no-underline hover:text-[var(--accent)]"
      >
        <h3 className="text-[15px] font-semibold leading-snug m-0">
          {issue.title}
        </h3>
      </a>
      <div className="flex items-center justify-between gap-2 text-[12px] text-[var(--text-muted)]">
        {area ? <span>{area}</span> : <span aria-hidden="true" />}
        {reactions > 0 && (
          <span aria-label={`${reactions} upvotes on GitHub`}>
            +{reactions}
          </span>
        )}
      </div>
    </li>
  );
}

export default function RoadmapPage() {
  const [state, setState] = useState({ status: "loading", issues: [] });

  useEffect(() => {
    let cancelled = false;
    fetch(ISSUES_URL, { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((issues) => {
        if (!cancelled) setState({ status: "ok", issues });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error", issues: [] });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const buckets = useMemo(() => _bucketByColumn(state.issues), [state.issues]);

  return (
    <PageLayout>
      <section className="max-w-[1100px] mx-auto px-4 md:px-8 py-12 md:py-16">
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Roadmap</h1>
        <p className="text-[var(--text-muted)] max-w-[640px] mb-10">
          What we&rsquo;re working on, what&rsquo;s next, and what&rsquo;s
          recently shipped. Click any item to read or upvote the GitHub
          issue — reactions on the issue feed directly into prioritisation.
        </p>

        {state.status === "loading" && (
          <p className="text-[var(--text-muted)]" role="status">
            Loading roadmap…
          </p>
        )}

        {state.status === "error" && (
          <p className="text-[var(--danger)]" role="alert">
            Couldn&rsquo;t reach GitHub. You can still view the roadmap
            directly on{" "}
            <a
              href="https://github.com/warlordofmars/hive/issues?q=is%3Aissue%20label%3Apublic-roadmap"
              target="_blank"
              rel="noreferrer"
              className="text-[var(--accent)] underline"
            >
              our GitHub repo
            </a>
            .
          </p>
        )}

        {state.status === "ok" && (
          <div
            data-testid="roadmap-columns"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
          >
            {COLUMNS.map((col) => (
              <div key={col.id} data-testid={`roadmap-col-${col.id}`}>
                <h2 className="text-lg font-bold mb-1">{col.title}</h2>
                <p className="text-[12px] text-[var(--text-muted)] mb-3">
                  {col.blurb}
                </p>
                {buckets[col.id].length === 0 ? (
                  <p className="text-[13px] text-[var(--text-muted)] italic">
                    Nothing here yet.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2 list-none m-0 p-0">
                    {buckets[col.id].map((issue) => (
                      <RoadmapCard key={issue.id} issue={issue} />
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </PageLayout>
  );
}
