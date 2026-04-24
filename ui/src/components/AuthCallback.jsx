// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useState } from "react";

export default function AuthCallback() {
  const [error, setError] = useState(null);

  useEffect(() => {
    async function handleCallback() {
      const params = new URLSearchParams(globalThis.location.search);
      const code = params.get("code");
      const state = params.get("state");
      const errorParam = params.get("error");

      if (errorParam) {
        setError(`Sign-in failed: ${errorParam}`);
        return;
      }
      if (!code) {
        setError("No authorization code received.");
        return;
      }

      const storedState = sessionStorage.getItem("oauth_state");
      if (storedState && state !== storedState) {
        setError("State mismatch — please try signing in again.");
        return;
      }

      const verifier = sessionStorage.getItem("pkce_verifier");
      const clientId = localStorage.getItem("hive_client_id");
      const redirectUri = `${globalThis.location.origin}/oauth/callback`;

      if (!verifier || !clientId) {
        setError("Missing sign-in context — please try again.");
        return;
      }

      const res = await fetch("/oauth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "authorization_code",
          code,
          redirect_uri: redirectUri,
          client_id: clientId,
          code_verifier: verifier,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail ?? "Token exchange failed.");
        return;
      }

      const data = await res.json();
      localStorage.setItem("hive_token", data.access_token);
      sessionStorage.removeItem("pkce_verifier");
      sessionStorage.removeItem("oauth_state");
      globalThis.location.replace("/");
    }

    handleCallback();
  }, []);

  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <p style={{ color: "#d00", fontSize: 16 }}>{error}</p>
        <a href="/" style={{ color: "#1a1a2e" }}>
          Return to login
        </a>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <p style={{ color: "#666" }}>Completing sign-in…</p>
    </div>
  );
}
