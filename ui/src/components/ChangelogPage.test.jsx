// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ChangelogPage from "./ChangelogPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

// Mock the raw CHANGELOG import
vi.mock("../../CHANGELOG.md?raw", () => ({
  default: `# Changelog

## v1.2.0 — 2026-01-02

### Added

- New feature one (#1)
- New feature two (#2)

### Fixed

- Bug fix one (#3)

### Deprecated

- Old thing

## v1.1.0 — 2026-01-01

### Added

- Initial feature (#0)

## Earlier releases

See GitHub.
`,
}));

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("ChangelogPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getAllByText("Changelog").length).toBeGreaterThanOrEqual(1);
  });

  it("renders parsed version headings", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getByText("v1.2.0")).toBeTruthy();
    expect(screen.getByText("v1.1.0")).toBeTruthy();
  });

  it("renders release dates", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getByText("2026-01-02")).toBeTruthy();
    expect(screen.getByText("2026-01-01")).toBeTruthy();
  });

  it("renders group headings (Added, Fixed)", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getAllByText("Added").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Fixed")).toBeTruthy();
  });

  it("renders changelog items with PR refs stripped", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getByText("New feature one")).toBeTruthy();
    expect(screen.getByText("Bug fix one")).toBeTruthy();
  });

  it("renders an unknown group heading with fallback style", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getByText("Deprecated")).toBeTruthy();
  });

  it("parseChangelog pushes trailing section when no Earlier-releases terminator", async () => {
    const { parseChangelog } = await import("./ChangelogPage.jsx");
    const result = parseChangelog("## v2.0.0 — 2026-06-01\n\n### Added\n\n- Something\n");
    expect(result.length).toBe(1);
    expect(result[0].version).toBe("v2.0.0");
  });

  it("renders GitHub releases link", async () => {
    await act(async () => renderInRouter(<ChangelogPage />));
    expect(screen.getByText("GitHub releases page")).toBeTruthy();
  });
});
