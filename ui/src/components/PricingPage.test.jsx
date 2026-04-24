// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PricingPage from "./PricingPage.jsx";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("PricingPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getByText(/Simple, honest pricing/)).toBeTruthy();
  });

  it("renders the Free badge", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getByText("Free")).toBeTruthy();
  });

  it("renders $0 price", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getByText("$0")).toBeTruthy();
  });

  it("renders all included features", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getByText(/Up to 500 memories/)).toBeTruthy();
    expect(screen.getByText(/Semantic search/)).toBeTruthy();
    expect(screen.getAllByText(/No credit card required/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders Get started free CTA", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getAllByText(/Get started free/).length).toBeGreaterThanOrEqual(1);
  });

  it("CTA navigates to /app", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    fireEvent.click(screen.getByText(/Get started free →/));
    expect(mockNavigate).toHaveBeenCalledWith("/app");
  });

  it("renders FAQ link", async () => {
    await act(async () => renderInRouter(<PricingPage />));
    expect(screen.getByText(/See the FAQ/)).toBeTruthy();
  });
});
