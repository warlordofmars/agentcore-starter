// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import PrivacyPage from "./PrivacyPage.jsx";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderInRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("PrivacyPage", () => {
  it("renders the heading", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/Privacy Policy/).length).toBeGreaterThan(0);
  });

  it("renders the last-updated note", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getByText(/Last updated: April 2026/)).toBeTruthy();
  });

  it("renders all section headings", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getByText(/Who We Are/)).toBeTruthy();
    expect(screen.getByText(/Data We Collect/)).toBeTruthy();
    expect(screen.getByText(/How We Use Your Data/)).toBeTruthy();
    expect(screen.getByText(/Where Data Is Stored/)).toBeTruthy();
    expect(screen.getByText(/Cookies and Local Storage/)).toBeTruthy();
    expect(screen.getAllByText(/Google Analytics 4/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Google OAuth/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Your Rights/)).toBeTruthy();
    expect(screen.getByText(/Data Retention/)).toBeTruthy();
    expect(screen.getByText(/Changes to This Policy/)).toBeTruthy();
    expect(screen.getByText(/^11\. Contact/)).toBeTruthy();
  });

  it("discloses Google Analytics 4 usage", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/Google Analytics 4/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/GA4/).length).toBeGreaterThan(0);
  });

  it("discloses localStorage token usage", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/hive_mgmt_token/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/localStorage/).length).toBeGreaterThan(0);
  });

  it("mentions DynamoDB and AWS storage", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/DynamoDB/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AWS/).length).toBeGreaterThan(0);
  });

  it("mentions the DELETE /api/account endpoint", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/DELETE \/api\/account/).length).toBeGreaterThan(0);
  });

  it("does not sell data to third parties", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getByText(/do not sell/)).toBeTruthy();
  });

  it("renders the Terms of Service footer link", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/Terms of Service/).length).toBeGreaterThan(0);
  });

  it("renders the privacy contact email", async () => {
    await act(async () => renderInRouter(<PrivacyPage />));
    expect(screen.getAllByText(/privacy@warlordofmars\.net/).length).toBeGreaterThan(0);
  });
});
