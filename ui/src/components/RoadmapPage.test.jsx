// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import RoadmapPage, { _bucketByColumn } from "./RoadmapPage.jsx";

function mockFetchOk(payload) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    }),
  );
}

function issue(partial) {
  return {
    id: partial.id ?? Math.random(),
    number: partial.number ?? 1,
    title: partial.title ?? "Untitled",
    state: partial.state ?? "open",
    html_url: partial.html_url ?? "https://github.com/warlordofmars/hive/issues/1",
    labels: (partial.labels ?? []).map((name) => ({ name })),
    reactions: partial.reactions ?? { total_count: 0 },
    closed_at: partial.closed_at ?? null,
  };
}

function renderInRouter() {
  return render(
    <MemoryRouter>
      <RoadmapPage />
    </MemoryRouter>,
  );
}

describe("RoadmapPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the heading and intro copy", async () => {
    mockFetchOk([]);
    await act(async () => renderInRouter());
    expect(screen.getByRole("heading", { name: "Roadmap" })).toBeTruthy();
    expect(screen.getByText(/reactions on the issue feed directly/i)).toBeTruthy();
  });

  it("shows a loading indicator while the fetch is in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    renderInRouter();
    expect(screen.getByRole("status")).toBeTruthy();
    expect(screen.getByText("Loading roadmap…")).toBeTruthy();
  });

  it("shows an error message with a GitHub fallback link when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    const link = screen.getByRole("link", { name: /our GitHub repo/i });
    expect(link.getAttribute("href")).toContain("label%3Apublic-roadmap");
  });

  it("falls back to the error branch when fetch itself rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });

  it("renders Now / Next / Later / Shipped columns with their issues", async () => {
    mockFetchOk([
      issue({ id: 1, title: "Alpha now", labels: ["public-roadmap", "roadmap:now"] }),
      issue({ id: 2, title: "Beta next", labels: ["public-roadmap", "roadmap:next"] }),
      issue({ id: 3, title: "Gamma later", labels: ["public-roadmap", "roadmap:later"] }),
      issue({
        id: 4,
        title: "Delta shipped",
        state: "closed",
        labels: ["public-roadmap"],
        closed_at: "2026-04-20T00:00:00Z",
      }),
    ]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());

    const now = within(screen.getByTestId("roadmap-col-now"));
    expect(now.getByText("Alpha now")).toBeTruthy();
    const next = within(screen.getByTestId("roadmap-col-next"));
    expect(next.getByText("Beta next")).toBeTruthy();
    const later = within(screen.getByTestId("roadmap-col-later"));
    expect(later.getByText("Gamma later")).toBeTruthy();
    const shipped = within(screen.getByTestId("roadmap-col-shipped"));
    expect(shipped.getByText("Delta shipped")).toBeTruthy();
  });

  it("renders empty columns with a 'Nothing here yet' placeholder", async () => {
    mockFetchOk([]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    const placeholders = screen.getAllByText("Nothing here yet.");
    expect(placeholders).toHaveLength(4);
  });

  it("card links open the GitHub issue in a new tab", async () => {
    mockFetchOk([
      issue({
        id: 1,
        title: "Item with link",
        labels: ["public-roadmap", "roadmap:now"],
        html_url: "https://github.com/warlordofmars/hive/issues/42",
      }),
    ]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    const link = screen.getByRole("link", { name: "Item with link" });
    expect(link.getAttribute("href")).toBe("https://github.com/warlordofmars/hive/issues/42");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noreferrer");
  });

  it("handles a missing reactions field on the card", async () => {
    // Covers the `issue.reactions?.total_count ?? 0` fallback when
    // GitHub omits the reactions object entirely (older API
    // responses, cached CDN payload, etc.). The +N badge must not
    // render and the card must not crash.
    mockFetchOk([
      {
        ...issue({
          id: 1,
          title: "Reactionless item",
          labels: ["public-roadmap", "roadmap:now"],
        }),
        reactions: undefined,
      },
    ]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    expect(screen.getByText("Reactionless item")).toBeTruthy();
  });

  it("shows reaction count on cards that have upvotes", async () => {
    mockFetchOk([
      issue({
        id: 1,
        title: "Popular item",
        labels: ["public-roadmap", "roadmap:now"],
        reactions: { total_count: 17 },
      }),
      issue({
        id: 2,
        title: "Lonely item",
        labels: ["public-roadmap", "roadmap:now"],
        reactions: { total_count: 0 },
      }),
    ]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    expect(screen.getByText("+17")).toBeTruthy();
    // Zero-reaction item shouldn't render a +0 badge.
    expect(screen.queryByText("+0")).toBeNull();
  });

  it("shows the area tag when an issue has a known area label", async () => {
    mockFetchOk([
      issue({
        id: 1,
        title: "UI item",
        labels: ["public-roadmap", "roadmap:now", "ui"],
      }),
      issue({
        id: 2,
        title: "Obscure area item",
        labels: ["public-roadmap", "roadmap:now", "random-label"],
      }),
    ]);
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    expect(screen.getByText("ui")).toBeTruthy();
    // Unknown area labels don't render.
    expect(screen.queryByText("random-label")).toBeNull();
  });

  describe("_bucketByColumn", () => {
    it("drops open issues without a status label", () => {
      const buckets = _bucketByColumn([issue({ labels: ["public-roadmap"] })]);
      expect(buckets.now).toHaveLength(0);
      expect(buckets.next).toHaveLength(0);
      expect(buckets.later).toHaveLength(0);
      expect(buckets.shipped).toHaveLength(0);
    });

    it("caps the shipped column at 8 items, most-recent first", () => {
      const twelve = Array.from({ length: 12 }, (_, i) =>
        issue({
          id: 100 + i,
          state: "closed",
          closed_at: `2026-04-${String(i + 1).padStart(2, "0")}T00:00:00Z`,
          labels: ["public-roadmap"],
        }),
      );
      const { shipped } = _bucketByColumn(twelve);
      expect(shipped).toHaveLength(8);
      // Most recent is the item closed 2026-04-12 (index 11).
      expect(shipped[0].id).toBe(111);
    });

    it("handles labels provided as plain strings (not {name} objects)", () => {
      const buckets = _bucketByColumn([
        {
          id: 1,
          state: "open",
          labels: ["public-roadmap", "roadmap:now"],
        },
      ]);
      expect(buckets.now).toHaveLength(1);
    });

    it("handles missing labels array defensively", () => {
      const buckets = _bucketByColumn([
        { id: 1, state: "open" },
        { id: 2, state: "closed", closed_at: "2026-04-01T00:00:00Z" },
      ]);
      expect(buckets.now).toHaveLength(0);
      // Closed issues flow into Shipped regardless of labels.
      expect(buckets.shipped).toHaveLength(1);
    });

    it("tolerates a missing closed_at on the shipped sort key", () => {
      // Defensive — GitHub sometimes returns closed issues without
      // a closed_at timestamp (edge case). Cover both sides of the
      // `?? ""` fallback: a pair where only one side is dated, and
      // a pair where neither side is dated.
      const partial = _bucketByColumn([
        { id: 1, state: "closed", closed_at: "2026-04-20T00:00:00Z", labels: [] },
        { id: 2, state: "closed", labels: [] }, // no closed_at
      ]);
      expect(partial.shipped).toHaveLength(2);
      // The dated one sorts before the undated one (empty-string
      // comparator puts undated last).
      expect(partial.shipped[0].id).toBe(1);

      // Both-undated: the sort still runs but doesn't reorder.
      const both = _bucketByColumn([
        { id: 10, state: "closed", labels: [] },
        { id: 11, state: "closed", labels: [] },
      ]);
      expect(both.shipped).toHaveLength(2);
    });

    it("filters out pull requests from the /issues payload", () => {
      // GitHub's /issues endpoint returns PRs too (shared id space).
      // Anything with a `pull_request` field is a PR and must be
      // dropped regardless of state or labels so code-review work
      // never leaks onto the public marketing roadmap.
      const buckets = _bucketByColumn([
        issue({
          id: 1,
          title: "Real issue",
          state: "closed",
          closed_at: "2026-04-21T00:00:00Z",
          labels: ["public-roadmap"],
        }),
        {
          ...issue({
            id: 2,
            title: "PR in disguise",
            state: "closed",
            closed_at: "2026-04-21T01:00:00Z",
            labels: ["public-roadmap", "roadmap:now"],
          }),
          pull_request: { url: "https://api.github.com/..." },
        },
      ]);
      expect(buckets.shipped).toHaveLength(1);
      expect(buckets.shipped[0].title).toBe("Real issue");
      expect(buckets.now).toHaveLength(0);
    });
  });

  it("renders an area tag for every known area in the taxonomy", async () => {
    // Regression for the Copilot-flagged drift between the roadmap
    // allowlist and CLAUDE.md's taxonomy. Render one issue per
    // known area label and verify each tag surfaces — catches the
    // case where someone adds a new area to CLAUDE.md but forgets
    // to update the component constant.
    const ALL_AREAS = [
      "ui", "ux", "a11y", "api", "mcp", "auth", "infra", "ci", "dx", "sdk",
      "security", "compliance", "docs", "design", "performance",
      "observability", "marketing", "seo", "growth", "ops", "reliability",
    ];
    mockFetchOk(
      ALL_AREAS.map((area, i) =>
        issue({
          id: i + 1,
          title: `Issue-${area}`,
          labels: ["public-roadmap", "roadmap:now", area],
        }),
      ),
    );
    await act(async () => renderInRouter());
    await waitFor(() => expect(screen.getByTestId("roadmap-columns")).toBeTruthy());
    for (const area of ALL_AREAS) {
      expect(screen.getByText(area)).toBeTruthy();
    }
  });
});
