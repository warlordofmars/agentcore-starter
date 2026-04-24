// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  CONSENT_RESET_EVENT,
  getConsent,
  loadGtag,
  setConsent,
} from "@/lib/consent";

export default function ConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(function subscribeToResetEvent() {
    if (getConsent() === null) setVisible(true);
    function onReset() {
      setVisible(true);
    }
    globalThis.addEventListener(CONSENT_RESET_EVENT, onReset);
    return function cleanup() {
      globalThis.removeEventListener(CONSENT_RESET_EVENT, onReset);
    };
  }, []);

  function handleAccept() {
    setConsent("accept");
    loadGtag(import.meta.env.VITE_GA_MEASUREMENT_ID);
    setVisible(false);
  }

  function handleReject() {
    setConsent("reject");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 sm:max-w-[420px] bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius)] shadow-lg p-4 z-50"
    >
      <p className="text-sm text-[var(--text)] mb-3">
        We use Google Analytics to understand how visitors use the marketing
        site. No tracking happens until you choose. See the{" "}
        <a
          href="/privacy"
          className="text-[var(--accent)] underline"
        >
          Privacy Policy
        </a>{" "}
        for details.
      </p>
      <div className="flex gap-2">
        <Button variant="brand" size="sm" onClick={handleAccept}>
          Accept
        </Button>
        <Button variant="secondary" size="sm" onClick={handleReject}>
          Reject
        </Button>
      </div>
    </div>
  );
}
