// Copyright (c) 2026 John Carter. All rights reserved.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CONSENT_KEY,
  CONSENT_RESET_EVENT,
  clearConsent,
  getConsent,
  hasAcceptedConsent,
  loadGtag,
  setConsent,
} from "./consent.js";

describe("consent utilities", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getConsent returns null when unset", () => {
    expect(getConsent()).toBeNull();
  });

  it("setConsent/getConsent round-trip", () => {
    setConsent("accept");
    expect(getConsent()).toBe("accept");
  });

  it("clearConsent removes the stored value", () => {
    setConsent("reject");
    clearConsent();
    expect(getConsent()).toBeNull();
  });

  it("hasAcceptedConsent is true only for 'accept'", () => {
    expect(hasAcceptedConsent()).toBe(false);
    setConsent("reject");
    expect(hasAcceptedConsent()).toBe(false);
    setConsent("accept");
    expect(hasAcceptedConsent()).toBe(true);
  });

  it("swallows localStorage errors from get", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
    });
    expect(getConsent()).toBeNull();
  });

  it("swallows localStorage errors from set", () => {
    vi.stubGlobal("localStorage", {
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => setConsent("accept")).not.toThrow();
  });

  it("swallows localStorage errors from remove", () => {
    vi.stubGlobal("localStorage", {
      removeItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => clearConsent()).not.toThrow();
  });

  it("CONSENT_KEY and CONSENT_RESET_EVENT are stable strings", () => {
    expect(CONSENT_KEY).toBe("starter_ga_consent");
    expect(CONSENT_RESET_EVENT).toBe("starter:consent-reset");
  });

  describe("loadGtag", () => {
    beforeEach(() => {
      document
        .querySelectorAll("script[data-starter-ga]")
        .forEach((s) => s.remove());
      delete globalThis.gtag;
      delete globalThis.dataLayer;
    });

    it("is a no-op when no measurement id is given", () => {
      loadGtag("");
      expect(document.querySelector("script[data-starter-ga]")).toBeNull();
    });

    it("injects the gtag script and initialises gtag()", () => {
      loadGtag("G-TESTID");
      const s = document.querySelector("script[data-starter-ga]");
      expect(s).not.toBeNull();
      expect(s.src).toContain("googletagmanager.com/gtag/js?id=G-TESTID");
      expect(typeof globalThis.gtag).toBe("function");
      expect(Array.isArray(globalThis.dataLayer)).toBe(true);
    });

    it("does not inject the script twice", () => {
      loadGtag("G-TESTID");
      loadGtag("G-TESTID");
      expect(document.querySelectorAll("script[data-starter-ga]")).toHaveLength(1);
    });

    it("is a no-op when document is missing", () => {
      vi.stubGlobal("document", undefined);
      expect(() => loadGtag("G-TESTID")).not.toThrow();
    });
  });
});
