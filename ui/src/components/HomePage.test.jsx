// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { BrainCircuit, Plug, ShieldCheck, Users } from "lucide-react";
import HomePage from "./HomePage.jsx";

// Wrap in MemoryRouter so useNavigate works in tests
function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("HomePage", () => {
  let navigated;

  beforeEach(() => {
    navigated = null;
    // Spy on useNavigate — react-router MemoryRouter records pushes via navigate()
    // We check DOM changes instead since MemoryRouter handles navigation internally.
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the hero heading", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getAllByText(/Persistent memory/).length).toBeGreaterThan(0);
  });

  it("renders the tagline", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getAllByText(/Model Context Protocol/).length).toBeGreaterThan(0);
  });

  it("renders all feature cards", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getByText(/Persistent memory across sessions/)).toBeTruthy();
    expect(screen.getByText(/Works with any MCP client/)).toBeTruthy();
    expect(screen.getByText(/Share memory across your team/)).toBeTruthy();
    expect(screen.getByText(/Your data, scoped to you/)).toBeTruthy();
  });

  it("renders all how-it-works steps", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getByText(/Sign in with Google/)).toBeTruthy();
    expect(screen.getByText(/Connect your MCP client/)).toBeTruthy();
    expect(screen.getByText(/Start remembering/)).toBeTruthy();
  });

  it("renders the logo and wordmark in the nav header", async () => {
    const { container } = await act(async () => renderInRouter(<HomePage />));
    const logo = container.querySelector('img[alt="Hive"]');
    expect(logo).toBeTruthy();
    expect(logo.getAttribute("src")).toBe("/logo.svg");
    // "Hive" wordmark text appears alongside logo
    expect(screen.getAllByText("Hive").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the nav Sign in button", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getByText("Sign in")).toBeTruthy();
  });

  it("renders multiple Get started free CTA buttons", async () => {
    await act(async () => renderInRouter(<HomePage />));
    const ctaButtons = screen.getAllByText(/Get started free/);
    expect(ctaButtons.length).toBeGreaterThanOrEqual(2);
  });

  it("renders the footer", async () => {
    await act(async () => renderInRouter(<HomePage />));
    expect(screen.getByText(/© 2026 Hive/)).toBeTruthy();
  });

  it("CTA buttons and Sign in button are clickable", async () => {
    await act(async () => renderInRouter(<HomePage />));
    // Buttons are present and clickable — they call navigate("/app") internally
    expect(screen.getByText("Sign in")).toBeTruthy();
    fireEvent.click(screen.getByText("Sign in"));
    const ctaButtons = screen.getAllByText(/Get started free/);
    expect(ctaButtons.length).toBeGreaterThan(0);
    ctaButtons.forEach((btn) => fireEvent.click(btn));
  });

  it("renders Lucide icons for feature cards", async () => {
    const { container } = await act(async () => renderInRouter(<HomePage />));
    // lucide-react renders SVGs with data-testid based on icon name
    expect(container.querySelector("svg")).toBeTruthy();
    const svgs = container.querySelectorAll("svg");
    // 4 feature icons
    expect(svgs.length).toBeGreaterThanOrEqual(4);
  });
});
