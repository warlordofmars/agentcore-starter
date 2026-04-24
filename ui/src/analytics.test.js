// Copyright (c) 2026 John Carter. All rights reserved.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We need to re-import the module with different env conditions, so we use
// vi.doMock / vi.importActual patterns with module resetting.

describe("analytics (GA disabled — DEV mode or no ID)", () => {
  beforeEach(() => {
    vi.resetModules();
    window.gtag = vi.fn();
  });

  afterEach(() => {
    delete window.gtag;
  });

  it("trackPageView is a no-op when DEV=true", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const { trackPageView } = await import("./analytics.js");
    trackPageView("/test");
    expect(window.gtag).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });

  it("trackEvent is a no-op when DEV=true", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const { trackEvent } = await import("./analytics.js");
    trackEvent("cta_click", { cta_location: "hero" });
    expect(window.gtag).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });

  it("trackPageView is a no-op when no measurement ID", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "");
    const { trackPageView } = await import("./analytics.js");
    trackPageView("/test");
    expect(window.gtag).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });

  it("trackEvent is a no-op when no measurement ID", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "");
    const { trackEvent } = await import("./analytics.js");
    trackEvent("tab_view", { tab_name: "memories" });
    expect(window.gtag).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });
});

describe("analytics (GA enabled — production with ID)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    localStorage.setItem("hive_ga_consent", "accept");
    window.gtag = vi.fn();
  });

  afterEach(() => {
    delete window.gtag;
    localStorage.clear();
    vi.unstubAllEnvs();
  });

  it("trackPageView calls gtag with page_view event", async () => {
    const { trackPageView } = await import("./analytics.js");
    trackPageView("/pricing");
    expect(window.gtag).toHaveBeenCalledWith("event", "page_view", {
      page_path: "/pricing",
      send_to: "G-TEST123",
    });
  });

  it("trackEvent calls gtag with the given event name and params", async () => {
    const { trackEvent } = await import("./analytics.js");
    trackEvent("cta_click", { cta_location: "hero" });
    expect(window.gtag).toHaveBeenCalledWith("event", "cta_click", {
      cta_location: "hero",
      send_to: "G-TEST123",
    });
  });

  it("trackEvent works with no params", async () => {
    const { trackEvent } = await import("./analytics.js");
    trackEvent("tab_view");
    expect(window.gtag).toHaveBeenCalledWith("event", "tab_view", {
      send_to: "G-TEST123",
    });
  });

  it("trackPageView is a no-op when window.gtag is not defined", async () => {
    delete window.gtag;
    const { trackPageView } = await import("./analytics.js");
    expect(() => trackPageView("/test")).not.toThrow();
  });

  it("trackEvent is a no-op when window.gtag is not defined", async () => {
    delete window.gtag;
    const { trackEvent } = await import("./analytics.js");
    expect(() => trackEvent("cta_click")).not.toThrow();
  });
});

describe("analytics (GA gated on consent)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    localStorage.clear();
    window.gtag = vi.fn();
  });

  afterEach(() => {
    delete window.gtag;
    localStorage.clear();
    vi.unstubAllEnvs();
  });

  it("trackPageView is a no-op when no consent is stored", async () => {
    const { trackPageView } = await import("./analytics.js");
    trackPageView("/pricing");
    expect(window.gtag).not.toHaveBeenCalled();
  });

  it("trackPageView is a no-op when consent is rejected", async () => {
    localStorage.setItem("hive_ga_consent", "reject");
    const { trackPageView } = await import("./analytics.js");
    trackPageView("/pricing");
    expect(window.gtag).not.toHaveBeenCalled();
  });

  it("trackEvent is a no-op when consent is rejected", async () => {
    localStorage.setItem("hive_ga_consent", "reject");
    const { trackEvent } = await import("./analytics.js");
    trackEvent("cta_click");
    expect(window.gtag).not.toHaveBeenCalled();
  });
});
