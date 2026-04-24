// Copyright (c) 2026 John Carter. All rights reserved.
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuthCallback from "./AuthCallback.jsx";

describe("AuthCallback", () => {
  let _storage;
  let _session;

  function stubLocation(search = "") {
    vi.stubGlobal("location", {
      ...window.location,
      search,
      origin: "https://hive.example.com",
      replace: vi.fn(),
    });
  }

  beforeEach(() => {
    _storage = {};
    _session = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => _storage[k] ?? null,
      setItem: (k, v) => {
        _storage[k] = v;
      },
      removeItem: (k) => {
        delete _storage[k];
      },
    });
    vi.stubGlobal("sessionStorage", {
      getItem: (k) => _session[k] ?? null,
      setItem: (k, v) => {
        _session[k] = v;
      },
      removeItem: (k) => {
        delete _session[k];
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows completing sign-in spinner initially", async () => {
    stubLocation("?code=abc&state=s1");
    _session["oauth_state"] = "s1";
    _session["pkce_verifier"] = "verifier123";
    _storage["hive_client_id"] = "client-1";
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));

    await act(async () => render(<AuthCallback />));
    expect(screen.getByText(/Completing sign-in/)).toBeTruthy();
  });

  it("stores token and redirects on success", async () => {
    stubLocation("?code=auth-code&state=mystate");
    _session["oauth_state"] = "mystate";
    _session["pkce_verifier"] = "verifier123";
    _storage["hive_client_id"] = "client-1";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ access_token: "jwt-token-abc" }),
      }),
    );

    await act(async () => render(<AuthCallback />));
    await waitFor(() => {
      expect(_storage["hive_token"]).toBe("jwt-token-abc");
      expect(window.location.replace).toHaveBeenCalledWith("/");
      expect(_session["pkce_verifier"]).toBeUndefined();
      expect(_session["oauth_state"]).toBeUndefined();
    });
  });

  it("shows error when error param is present", async () => {
    stubLocation("?error=access_denied");
    await act(async () => render(<AuthCallback />));
    expect(screen.getByText(/Sign-in failed: access_denied/)).toBeTruthy();
  });

  it("shows error when no code param", async () => {
    stubLocation("?state=s");
    await act(async () => render(<AuthCallback />));
    expect(screen.getByText(/No authorization code received/)).toBeTruthy();
  });

  it("shows error on state mismatch", async () => {
    stubLocation("?code=c&state=wrong");
    _session["oauth_state"] = "expected";
    await act(async () => render(<AuthCallback />));
    expect(screen.getByText(/State mismatch/)).toBeTruthy();
  });

  it("shows error when pkce verifier or client_id is missing", async () => {
    stubLocation("?code=c&state=s");
    _session["oauth_state"] = "s";
    // No verifier or client_id stored
    await act(async () => render(<AuthCallback />));
    expect(screen.getByText(/Missing sign-in context/)).toBeTruthy();
  });

  it("shows error when token exchange fails", async () => {
    stubLocation("?code=bad-code&state=s");
    _session["oauth_state"] = "s";
    _session["pkce_verifier"] = "verifier";
    _storage["hive_client_id"] = "client-1";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ detail: "invalid_grant" }),
      }),
    );

    await act(async () => render(<AuthCallback />));
    await waitFor(() => {
      expect(screen.getByText("invalid_grant")).toBeTruthy();
    });
  });

  it("shows return link on error", async () => {
    stubLocation("?error=denied");
    await act(async () => render(<AuthCallback />));
    const link = screen.getByText("Return to login");
    expect(link.getAttribute("href")).toBe("/");
  });

  it("shows generic error message when token response has no detail", async () => {
    stubLocation("?code=bad-code&state=s");
    _session["oauth_state"] = "s";
    _session["pkce_verifier"] = "verifier";
    _storage["hive_client_id"] = "client-1";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({}), // no detail field
      }),
    );

    await act(async () => render(<AuthCallback />));
    await waitFor(() => {
      expect(screen.getByText("Token exchange failed.")).toBeTruthy();
    });
  });
});
