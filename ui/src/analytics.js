// Copyright (c) 2026 John Carter. All rights reserved.

/**
 * Thin wrapper around gtag. All functions are no-ops when:
 *   - running in local dev (import.meta.env.DEV)
 *   - VITE_GA_MEASUREMENT_ID is not set
 *   - the visitor has not opted in via the consent banner
 */

import { hasAcceptedConsent } from "./lib/consent.js";

const ID = import.meta.env.VITE_GA_MEASUREMENT_ID;

function enabled() {
  return !import.meta.env.DEV && !!ID && hasAcceptedConsent();
}

export function trackPageView(path) {
  if (!enabled()) return;
  globalThis.gtag?.("event", "page_view", {
    page_path: path,
    send_to: ID,
  });
}

export function trackEvent(name, params = {}) {
  if (!enabled()) return;
  globalThis.gtag?.("event", name, { ...params, send_to: ID });
}
