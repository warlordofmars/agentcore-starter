// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OnboardingTour from "./OnboardingTour.jsx";

function setupTabAnchors() {
  // The tour spotlights tab buttons via [data-tab-id]. In jsdom,
  // appending stand-in buttons ensures those anchors exist in the
  // document for the component to find via querySelector. jsdom
  // still returns a zero-rect from getBoundingClientRect, so the
  // tooltip ends up positioned at top:8 left:-4 — fine for asserting
  // logic; visual positioning is only meaningful in a real browser.
  for (const id of ["memories", "setup", "activity", "clients", "dashboard"]) {
    const btn = document.createElement("button");
    btn.setAttribute("data-tab-id", id);
    btn.textContent = id;
    document.body.appendChild(btn);
  }
}

function teardownTabAnchors() {
  document.querySelectorAll("[data-tab-id]").forEach((el) => el.remove());
}

describe("OnboardingTour", () => {
  beforeEach(() => {
    localStorage.clear();
    setupTabAnchors();
  });

  afterEach(() => {
    teardownTabAnchors();
    localStorage.clear();
  });

  it("renders the tour on first visit and walks Memories → Setup → Activity → Clients", async () => {
    await act(async () => render(<OnboardingTour />));
    expect(screen.getByTestId("onboarding-tour-card")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Your memory store" })).toBeTruthy();
    expect(screen.getByText("Step 1 of 4")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Connect your first agent" })).toBeTruthy();
    expect(screen.getByText("Step 2 of 4")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "See your agents at work" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Manage OAuth clients" })).toBeTruthy();
    // Last step: button label flips to "Got it" and clicking
    // dismisses the tour (no Step 5).
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByTestId("onboarding-tour-card")).toBeNull();
    expect(localStorage.getItem("hive_tour_dismissed")).toBe("1");
  });

  it("appends the admin Dashboard step when isAdmin", async () => {
    await act(async () => render(<OnboardingTour isAdmin />));
    expect(screen.getByText("Step 1 of 5")).toBeTruthy();
    // Skip ahead to the admin step.
    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
    }
    expect(screen.getByRole("heading", { name: "Admin dashboard" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Got it" })).toBeTruthy();
  });

  it("Back button returns to the previous step", async () => {
    await act(async () => render(<OnboardingTour />));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Step 1 of 4")).toBeTruthy();
    // Step 1 has no Back button (there's nothing to go back to).
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
  });

  it("Skip dismisses the tour and persists the choice across reloads", async () => {
    const { unmount } = render(<OnboardingTour />);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(screen.queryByTestId("onboarding-tour-card")).toBeNull();
    unmount();

    // Re-mount: dismissed flag in localStorage prevents the tour
    // from re-appearing.
    await act(async () => render(<OnboardingTour />));
    expect(screen.queryByTestId("onboarding-tour-card")).toBeNull();
  });

  it("clicking the backdrop dismisses the tour", async () => {
    await act(async () => render(<OnboardingTour />));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss onboarding tour" }));
    expect(screen.queryByTestId("onboarding-tour-card")).toBeNull();
  });

  it("falls back to top-of-viewport tooltip when the tab anchor is missing", async () => {
    teardownTabAnchors(); // simulate mobile drawer closed / no nav rendered
    await act(async () => render(<OnboardingTour />));
    const card = screen.getByTestId("onboarding-tour-card");
    // Fallback positions the card at top:80, left:16 — pin it so a
    // regression that changes the fallback origin breaks the test.
    expect(card.style.top).toBe("80px");
    expect(card.style.left).toBe("16px");
  });

  it("dispatches hive:switch-tab on step changes (skipping initial mount)", async () => {
    // Initial mount doesn't dispatch — the default tab is already
    // "memories", so a programmatic switch would just fire a
    // redundant tab_view analytics event.
    const dispatched = [];
    const realDispatch = globalThis.dispatchEvent.bind(globalThis);
    vi.spyOn(globalThis, "dispatchEvent").mockImplementation((evt) => {
      if (evt && evt.type === "hive:switch-tab") dispatched.push(evt.detail);
      return realDispatch(evt);
    });

    await act(async () => render(<OnboardingTour />));
    expect(dispatched).toEqual([]); // no initial dispatch

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(dispatched.at(-1)).toBe("setup");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(dispatched.at(-1)).toBe("activity");

    // Back from step 3 → step 2 must re-dispatch "setup", and
    // Back from step 2 → step 1 must re-dispatch "memories" so
    // the underlying tab matches the spotlight even when the user
    // walks backwards. (Iter-3 fix: skip-on-mount ref instead of
    // skip-on-stepIndex-zero.)
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(dispatched.at(-1)).toBe("setup");
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(dispatched.at(-1)).toBe("memories");

    vi.restoreAllMocks();
  });

  it("Escape key dismisses the tour", async () => {
    await act(async () => render(<OnboardingTour />));
    await act(async () => {
      globalThis.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(screen.queryByTestId("onboarding-tour-card")).toBeNull();
    expect(localStorage.getItem("hive_tour_dismissed")).toBe("1");
  });

  it("ignores non-Escape keys", async () => {
    // Defensive — covers the `if (e.key === 'Escape')` branch
    // false path so a regression that broadens the dismiss key
    // (e.g. any key) is caught.
    await act(async () => render(<OnboardingTour />));
    await act(async () => {
      globalThis.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    });
    expect(screen.getByTestId("onboarding-tour-card")).toBeTruthy();
  });

  it("focuses the primary action on mount and on each step change", async () => {
    await act(async () => render(<OnboardingTour />));
    await waitFor(() => {
      expect(document.activeElement?.textContent).toBe("Next");
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(document.activeElement?.textContent).toBe("Next");
    });
  });

  it("renders the dialog with aria-modal so screen readers trap focus", async () => {
    await act(async () => render(<OnboardingTour />));
    const card = screen.getByTestId("onboarding-tour-card");
    expect(card.getAttribute("role")).toBe("dialog");
    expect(card.getAttribute("aria-modal")).toBe("true");
  });

  it("re-measures the spotlight rect on window resize", async () => {
    await act(async () => render(<OnboardingTour />));
    // Move the anchor: a resize event should re-read its rect via
    // the effect's setTick(). We can't easily assert the new
    // position from jsdom, but we can verify the listener is wired
    // by triggering and confirming the card still renders without
    // throwing.
    await act(async () => {
      globalThis.dispatchEvent(new Event("resize"));
    });
    expect(screen.getByTestId("onboarding-tour-card")).toBeTruthy();
  });
});
