// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ConsentBanner from "./ConsentBanner.jsx";
import { CONSENT_KEY, CONSENT_RESET_EVENT } from "../lib/consent.js";

function renderBanner() {
  return render(
    <MemoryRouter>
      <ConsentBanner />
    </MemoryRouter>,
  );
}

describe("ConsentBanner", () => {
  beforeEach(() => {
    localStorage.clear();
    document.querySelectorAll("script[data-starter-ga]").forEach((s) => s.remove());
    delete globalThis.gtag;
    delete globalThis.dataLayer;
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TESTID");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders on first visit when no choice is stored", async () => {
    await act(async () => renderBanner());
    expect(screen.getByRole("dialog", { name: "Cookie consent" })).toBeTruthy();
    expect(screen.getByText("Accept")).toBeTruthy();
    expect(screen.getByText("Reject")).toBeTruthy();
  });

  it("is hidden when consent was already accepted", async () => {
    localStorage.setItem(CONSENT_KEY, "accept");
    await act(async () => renderBanner());
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
  });

  it("is hidden when consent was already rejected", async () => {
    localStorage.setItem(CONSENT_KEY, "reject");
    await act(async () => renderBanner());
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
  });

  it("Accept stores consent, loads gtag, and hides the banner", async () => {
    await act(async () => renderBanner());
    fireEvent.click(screen.getByText("Accept"));
    expect(localStorage.getItem(CONSENT_KEY)).toBe("accept");
    expect(document.querySelector("script[data-starter-ga]")).not.toBeNull();
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
  });

  it("Reject stores consent, does not load gtag, and hides the banner", async () => {
    await act(async () => renderBanner());
    fireEvent.click(screen.getByText("Reject"));
    expect(localStorage.getItem(CONSENT_KEY)).toBe("reject");
    expect(document.querySelector("script[data-starter-ga]")).toBeNull();
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
  });

  it("re-shows the banner when the reset event fires", async () => {
    localStorage.setItem(CONSENT_KEY, "reject");
    await act(async () => renderBanner());
    expect(screen.queryByRole("dialog", { name: "Cookie consent" })).toBeNull();
    await act(async () => {
      globalThis.dispatchEvent(new CustomEvent(CONSENT_RESET_EVENT));
    });
    expect(screen.getByRole("dialog", { name: "Cookie consent" })).toBeTruthy();
  });

  it("links to the Privacy Policy", async () => {
    await act(async () => renderBanner());
    const link = screen.getByText("Privacy Policy");
    expect(link.getAttribute("href")).toBe("/privacy");
  });
});
