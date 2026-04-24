// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PageLayout from "./PageLayout.jsx";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

beforeEach(() => {
  // useTheme reads prefers-color-scheme on first render; jsdom doesn't
  // implement matchMedia so we stub a minimal response.
  vi.stubGlobal("matchMedia", (q) => ({
    matches: false,
    media: q,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }));
});

function renderInRouter(ui, path = "/") {
  return render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);
}

describe("PageLayout", () => {
  it("renders children", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><p>test content</p></PageLayout>)
    );
    expect(screen.getByText("test content")).toBeTruthy();
  });

  it("renders nav with logo and wordmark", async () => {
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(container.querySelector('img[alt="Hive"]')).toBeTruthy();
    expect(screen.getAllByText("Hive").length).toBeGreaterThanOrEqual(1);
  });

  it("renders nav links: Pricing, FAQ, Docs", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(screen.getAllByText("Use cases").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Clients").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pricing").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("FAQ").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Docs").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Sign in button", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(screen.getByText("Sign in")).toBeTruthy();
  });

  it("Sign in navigates to /app", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    fireEvent.click(screen.getByText("Sign in"));
    expect(mockNavigate).toHaveBeenCalledWith("/app");
  });

  it("clicking logo navigates to /", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    const logo = screen.getAllByText("Hive")[0].closest("span");
    fireEvent.click(logo);
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("renders footer with copyright", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(screen.getByText(/© 2026 Hive/)).toBeTruthy();
  });

  it("renders footer links: Pricing, FAQ, Docs", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(screen.getAllByText("Pricing").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("FAQ").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Use cases").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Clients").length).toBeGreaterThanOrEqual(1);
  });

  it("renders footer Terms and Privacy links", async () => {
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    const footer = container.querySelector("footer");
    expect(within(footer).getByText("Terms")).toBeTruthy();
    expect(within(footer).getByText("Privacy")).toBeTruthy();
  });

  it("active nav link has orange bottom border for current page", async () => {
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>, "/pricing")
    );
    const header = container.querySelector("header");
    const pricingLink = within(header).getByRole("link", { name: "Pricing" });
    expect(pricingLink.style.borderBottomColor).toBe("rgb(232, 160, 32)");
  });

  it("inactive nav links have transparent bottom border", async () => {
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>, "/pricing")
    );
    const header = container.querySelector("header");
    const faqLink = within(header).getByRole("link", { name: "FAQ" });
    expect(faqLink.style.borderBottomColor).toBe("transparent");
  });

  it("Sign in button uses nav variant with visible border", async () => {
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    const btn = screen.getByRole("button", { name: "Sign in" });
    expect(btn.className).toContain("border-white/60");
    expect(btn.className).toContain("marketing-signin-btn");
  });

  it("mounts the consent banner when no consent has been stored", async () => {
    localStorage.removeItem("hive_ga_consent");
    await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    expect(screen.getByRole("dialog", { name: "Cookie consent" })).toBeTruthy();
  });

  it("renders Cookie preferences footer link", async () => {
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    const footer = container.querySelector("footer");
    expect(within(footer).getByText("Cookie preferences")).toBeTruthy();
  });

  it("renders a mobile hamburger button with correct aria-label", async () => {
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>));
    const btn = screen.getByLabelText("Open menu");
    expect(btn).toBeTruthy();
    expect(btn.getAttribute("aria-expanded")).toBe("false");
  });

  it("hamburger toggles the mobile drawer and flips its aria label", async () => {
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>));
    const btn = screen.getByLabelText("Open menu");
    await act(async () => fireEvent.click(btn));
    const closeBtn = screen.getByLabelText("Close menu");
    expect(closeBtn.getAttribute("aria-expanded")).toBe("true");
    // Drawer renders its own <nav> inside a div with md:hidden wrapper.
    const drawer = closeBtn.closest("header").querySelector(".md\\:hidden nav");
    expect(drawer).toBeTruthy();
    await act(async () => fireEvent.click(closeBtn));
    expect(screen.getByLabelText("Open menu").getAttribute("aria-expanded")).toBe("false");
  });

  it("mobile drawer lists every nav link; Sign in + theme toggle live in the navbar", async () => {
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>));
    await act(async () => fireEvent.click(screen.getByLabelText("Open menu")));
    const drawer = document.querySelector("header .md\\:hidden nav");
    expect(drawer).toBeTruthy();
    for (const label of ["Use cases", "Clients", "Pricing", "FAQ", "Docs"]) {
      expect(within(drawer).getByText(label)).toBeTruthy();
    }
    // Sign in lives in the navbar (visible at every breakpoint), not in the drawer.
    expect(within(drawer).queryByRole("button", { name: "Sign in" })).toBeNull();
  });

  it("navbar Sign in navigates to /app at every breakpoint", async () => {
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>));
    // Sign in is rendered in the navbar row itself (not the drawer).
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign in" })));
    expect(mockNavigate).toHaveBeenCalledWith("/app");
  });

  it("navbar theme toggle flips the theme and updates its aria-label", async () => {
    localStorage.removeItem("hive_theme");
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>));
    const btn = screen.getByLabelText(/Switch to (dark|light) mode/);
    const before = btn.getAttribute("aria-label");
    await act(async () => fireEvent.click(btn));
    const after = screen.getByLabelText(/Switch to (dark|light) mode/).getAttribute("aria-label");
    expect(after).not.toBe(before);
  });

  it("mobile drawer marks the current page with an orange left border", async () => {
    await act(async () => renderInRouter(<PageLayout><span /></PageLayout>, "/faq"));
    await act(async () => fireEvent.click(screen.getByLabelText("Open menu")));
    const drawer = document.querySelector("header .md\\:hidden nav");
    const faqLink = within(drawer).getByText("FAQ");
    expect(faqLink.style.borderLeftColor).toBe("rgb(232, 160, 32)");
    const pricingLink = within(drawer).getByText("Pricing");
    expect(pricingLink.style.borderLeftColor).toBe("transparent");
  });

  it("Cookie preferences click clears stored consent and re-shows the banner", async () => {
    localStorage.setItem("hive_ga_consent", "reject");
    const { container } = await act(async () =>
      renderInRouter(<PageLayout><span /></PageLayout>)
    );
    // Banner hidden while consent is stored.
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
    const footer = container.querySelector("footer");
    const link = within(footer).getByText("Cookie preferences");
    await act(async () => fireEvent.click(link));
    expect(localStorage.getItem("hive_ga_consent")).toBeNull();
    expect(screen.getByRole("dialog", { name: "Cookie consent" })).toBeTruthy();
  });
});
