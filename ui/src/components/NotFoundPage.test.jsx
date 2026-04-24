// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import NotFoundPage from "./NotFoundPage.jsx";

function renderInRouter() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>,
  );
}

describe("NotFoundPage", () => {
  it("renders the 404 banner and 'Page not found' heading", async () => {
    await act(async () => renderInRouter());
    expect(screen.getByText("404")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });

  it("offers Home / Docs / Contact support links so the user has a path forward", async () => {
    await act(async () => renderInRouter());
    // Scope to the body section so we don't pick up the navbar/footer
    // Docs links from PageLayout (PageLayout adds three Docs links of
    // its own — nav, mobile-drawer-not-rendered, footer).
    const heading = screen.getByRole("heading", { name: "Page not found" });
    const section = heading.closest("section");
    const links = section.querySelectorAll("a");
    const byLabel = {};
    for (const link of links) byLabel[link.textContent.trim()] = link;

    expect(byLabel["Home"].getAttribute("href")).toBe("/");
    // Marketing-site Docs link points at the VitePress mount, not a
    // React Router route, so it stays a plain `<a href>` (consistent
    // with the navbar / footer link).
    expect(byLabel["Docs"].getAttribute("href")).toBe("/docs/");
    expect(byLabel["Contact support"].getAttribute("href")).toContain(
      "mailto:hello@warlordofmars.net",
    );
  });

  it("hides the literal '404' text from screen readers (decorative only)", async () => {
    await act(async () => renderInRouter());
    // The "404" badge above the heading is purely decorative — the
    // heading itself carries the semantic meaning. Asserting the
    // aria-hidden so an SR doesn't read out "four oh four — Page not
    // found".
    const badge = screen.getByText("404");
    expect(badge.getAttribute("aria-hidden")).toBe("true");
  });
});
