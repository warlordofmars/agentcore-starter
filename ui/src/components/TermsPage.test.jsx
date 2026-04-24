// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import TermsPage from "./TermsPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("TermsPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getAllByText(/Terms of Service/).length).toBeGreaterThan(0);
  });

  it("renders the last-updated note", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getByText(/Last updated: April 2026/)).toBeTruthy();
  });

  it("renders all section headings", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getByText(/Acceptance of Terms/)).toBeTruthy();
    expect(screen.getByText(/Acceptable Use/)).toBeTruthy();
    expect(screen.getByText(/What Hive Stores/)).toBeTruthy();
    expect(screen.getByText(/Data Retention and Deletion/)).toBeTruthy();
    expect(screen.getByText(/Service Availability/)).toBeTruthy();
    expect(screen.getByText(/Limitation of Liability/)).toBeTruthy();
    expect(screen.getByText(/Intellectual Property/)).toBeTruthy();
    expect(screen.getByText(/Changes to These Terms/)).toBeTruthy();
    expect(screen.getByText(/Governing Law/)).toBeTruthy();
    expect(screen.getByText(/^10\. Contact/)).toBeTruthy();
  });

  it("mentions the DELETE /api/account endpoint", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getAllByText(/DELETE \/api\/account/).length).toBeGreaterThan(0);
  });

  it("mentions memories, OAuth tokens, and activity logs", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getAllByText(/Memories/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/OAuth tokens/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Activity logs/).length).toBeGreaterThan(0);
  });

  it("mentions California governing law", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getByText(/California/)).toBeTruthy();
  });

  it("renders the Privacy Policy footer link", async () => {
    await act(async () => renderInRouter(<TermsPage />));
    expect(screen.getAllByText(/Privacy Policy/).length).toBeGreaterThan(0);
  });
});
