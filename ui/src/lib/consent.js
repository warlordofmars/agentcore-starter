// Copyright (c) 2026 John Carter. All rights reserved.

/**
 * GA4 consent utilities. The marketing site must not load Google Analytics
 * before the visitor has explicitly opted in (GDPR/CCPA). Both this module
 * and the inline bootstrap in index.html gate on the `starter_ga_consent`
 * localStorage key.
 */

export const CONSENT_KEY = "starter_ga_consent";
export const CONSENT_RESET_EVENT = "starter:consent-reset";

export function getConsent() {
  try {
    return globalThis.localStorage?.getItem(CONSENT_KEY) ?? null;
  } catch {
    return null;
  }
}

export function setConsent(value) {
  try {
    globalThis.localStorage?.setItem(CONSENT_KEY, value);
  } catch {
    /* private browsing / SSR — silently ignore */
  }
}

export function clearConsent() {
  try {
    globalThis.localStorage?.removeItem(CONSENT_KEY);
  } catch {
    /* private browsing / SSR — silently ignore */
  }
}

export function hasAcceptedConsent() {
  return getConsent() === "accept";
}

export function loadGtag(measurementId) {
  if (!measurementId) return;
  const doc = globalThis.document;
  if (!doc) return;
  if (doc.querySelector("script[data-starter-ga]")) return;
  const s = doc.createElement("script");
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + measurementId;
  s.async = true;
  s.dataset.starterGa = "1";
  doc.head.appendChild(s);
  globalThis.dataLayer = globalThis.dataLayer || [];
  function gtag() {
    globalThis.dataLayer.push(arguments);
  }
  globalThis.gtag = gtag;
  gtag("js", new Date());
  gtag("config", measurementId, { send_page_view: false });
}
