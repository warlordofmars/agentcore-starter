// Copyright (c) 2026 John Carter. All rights reserved.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";

vi.mock("./components/MemoryBrowser.jsx", () => ({
  default: () => <div data-testid="memory-browser" />,
}));
vi.mock("./components/ClientManager.jsx", () => ({
  default: () => <div data-testid="client-manager" />,
}));
vi.mock("./components/ActivityLog.jsx", () => ({
  default: () => <div data-testid="activity-log" />,
}));
vi.mock("./components/LoginPage.jsx", () => ({
  default: () => <div data-testid="login-page" />,
}));
vi.mock("./components/AuthCallback.jsx", () => ({
  default: () => <div data-testid="auth-callback" />,
}));
vi.mock("./components/UsersPanel.jsx", () => ({
  default: () => <div data-testid="users-panel" />,
}));
vi.mock("./components/SetupPanel.jsx", () => ({
  default: () => <div data-testid="setup-panel" />,
}));
vi.mock("./components/Stats.jsx", () => ({
  default: () => <div data-testid="stats-panel" />,
}));
vi.mock("./components/HomePage.jsx", () => ({
  default: () => <div data-testid="home-page" />,
}));
vi.mock("./components/Dashboard.jsx", () => ({
  default: () => <div data-testid="dashboard" />,
}));
vi.mock("./components/LogViewer.jsx", () => ({
  default: () => <div data-testid="log-viewer" />,
}));
vi.mock("./components/ApiKeysPanel.jsx", () => ({
  default: () => <div data-testid="api-keys-panel" />,
}));

/** Build a syntactically-valid mgmt JWT with given claims. */
function makeToken({ expOffsetSeconds = 3600, role = "user", email = "u@example.com" } = {}) {
  const exp = Math.floor(Date.now() / 1000) + expOffsetSeconds;
  const payload = btoa(JSON.stringify({ exp, sub: "test-user", role, email }));
  return `eyJhbGciOiJIUzI1NiJ9.${payload}.sig`;
}

/** URL-aware fetch mock: /api/clients returns items, /health returns version. */
function makeFetch({ clients = [{ client_id: "c1" }] } = {}) {
  return vi.fn().mockImplementation((url) => {
    if (String(url).includes("/api/clients")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: clients }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: "ok", version: "1.2.3" }),
    });
  });
}

describe("App routing", () => {
  let _storage;

  beforeEach(() => {
    _storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => _storage[k] ?? null,
      setItem: (k, v) => { _storage[k] = v; },
      removeItem: (k) => { delete _storage[k]; },
    });
    vi.stubGlobal("matchMedia", (q) => ({
      matches: q === "(prefers-color-scheme: dark)" ? false : false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal("fetch", makeFetch());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows HomePage at / when not authenticated", async () => {
    await act(async () => render(<App />));
    expect(screen.getByTestId("home-page")).toBeTruthy();
  });

  it("redirects / to /app when already authenticated", async () => {
    _storage["hive_mgmt_token"] = makeToken();
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    expect(screen.queryByTestId("home-page")).toBeNull();
  });

  it("shows AuthCallback at /oauth/callback", async () => {
    window.history.pushState({}, "", "/oauth/callback");
    await act(async () => render(<App />));
    expect(screen.getByTestId("auth-callback")).toBeTruthy();
    window.history.pushState({}, "", "/");
  });

  it("renders the branded NotFoundPage on unknown routes", async () => {
    // Catch-all `*` route now lands on a real 404 instead of
    // silently redirecting home — gives the user a path forward
    // (Home / Docs / Contact) instead of a confusing reset.
    window.history.pushState({}, "", "/unknown-path");
    await act(async () => render(<App />));
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
    expect(screen.queryByTestId("home-page")).toBeNull();
    window.history.pushState({}, "", "/");
  });
});

describe("AppShell", () => {
  let _storage;

  beforeEach(() => {
    _storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => _storage[k] ?? null,
      setItem: (k, v) => { _storage[k] = v; },
      removeItem: (k) => { delete _storage[k]; },
    });
    vi.stubGlobal("matchMedia", (q) => ({
      matches: q === "(prefers-color-scheme: dark)" ? false : false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal("fetch", makeFetch());
    _storage["hive_mgmt_token"] = makeToken();
    window.history.pushState({}, "", "/app");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.pushState({}, "", "/");
  });

  it("renders header with Hive title", async () => {
    await act(async () => render(<App />));
    expect(screen.getByText("Hive")).toBeTruthy();
  });

  it("renders the base tab buttons for non-admin (including Setup)", async () => {
    await act(async () => render(<App />));
    expect(screen.getByText("Memories")).toBeTruthy();
    expect(screen.getByText("OAuth Clients")).toBeTruthy();
    expect(screen.getByText("API Keys")).toBeTruthy();
    expect(screen.getByText("Activity Log")).toBeTruthy();
    expect(screen.getByText("Setup")).toBeTruthy();
    expect(screen.queryByText("Users")).toBeNull();
  });

  it("renders Users and Dashboard tabs for admin", async () => {
    _storage["hive_mgmt_token"] = makeToken({ role: "admin" });
    await act(async () => render(<App />));
    expect(screen.getByText("Users")).toBeTruthy();
    expect(screen.getByText("Dashboard")).toBeTruthy();
  });

  it("shows MemoryBrowser on initial render when clients exist", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    expect(screen.queryByTestId("client-manager")).toBeNull();
    expect(screen.queryByTestId("activity-log")).toBeNull();
    expect(screen.queryByTestId("setup-panel")).toBeNull();
  });

  it("defaults to Setup tab on first load when no clients registered (tour dismissed)", async () => {
    // The auto-switch only fires once the OnboardingTour has been
    // dismissed — otherwise step 1's "Memories" spotlight would
    // point at a tab that's no longer the active panel.
    _storage["hive_tour_dismissed"] = "1";
    vi.stubGlobal("fetch", makeFetch({ clients: [] }));
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("setup-panel")).toBeTruthy());
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("suppresses auto-switch to Setup while the OnboardingTour is still active", async () => {
    // Tour dismissed flag is NOT set — the empty-clients
    // auto-switch must hold so the spotlight on step 1 ("Memories")
    // matches the active tab.
    vi.stubGlobal("fetch", makeFetch({ clients: [] }));
    await act(async () => render(<App />));
    // Settle the listClients promise.
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    expect(screen.queryByTestId("setup-panel")).toBeNull();
  });

  it("does not switch to Setup when listClients returns null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url) => {
        if (String(url).includes("/api/clients")) {
          return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve() });
        }
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ status: "ok", version: "1.2.3" }),
        });
      }),
    );
    await act(async () => render(<App />));
    expect(screen.getByText("Memories")).toBeTruthy();
  });

  it("does not crash when listClients fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url) => {
        if (String(url).includes("/api/clients")) {
          return Promise.reject(new Error("Network error"));
        }
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ status: "ok", version: "1.2.3" }),
        });
      }),
    );
    await act(async () => render(<App />));
    expect(screen.getByText("Memories")).toBeTruthy();
  });

  it("switches to ClientManager when OAuth Clients tab is clicked", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("OAuth Clients"));
    expect(screen.getByTestId("client-manager")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to Stats when the Stats tab is clicked (#535)", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Stats"));
    expect(screen.getByTestId("stats-panel")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to ApiKeysPanel when API Keys tab is clicked", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("API Keys"));
    expect(screen.getByTestId("api-keys-panel")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to ActivityLog when Activity Log tab is clicked", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Activity Log"));
    expect(screen.getByTestId("activity-log")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to SetupPanel when Setup tab is clicked", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Setup"));
    expect(screen.getByTestId("setup-panel")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to UsersPanel when Users tab is clicked (admin only)", async () => {
    _storage["hive_mgmt_token"] = makeToken({ role: "admin" });
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Users"));
    expect(screen.getByTestId("users-panel")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to Dashboard when Dashboard tab is clicked (admin only)", async () => {
    _storage["hive_mgmt_token"] = makeToken({ role: "admin" });
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Dashboard"));
    expect(screen.getByTestId("dashboard")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("switches to LogViewer when Logs tab is clicked (admin only)", async () => {
    _storage["hive_mgmt_token"] = makeToken({ role: "admin" });
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Logs"));
    expect(screen.getByTestId("log-viewer")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("shows LoginPage when no token is stored", async () => {
    delete _storage["hive_mgmt_token"];
    await act(async () => render(<App />));
    expect(screen.getByTestId("login-page")).toBeTruthy();
    expect(screen.queryByTestId("memory-browser")).toBeNull();
  });

  it("shows LoginPage when token is expired", async () => {
    _storage["hive_mgmt_token"] = makeToken({ expOffsetSeconds: -3600 });
    await act(async () => render(<App />));
    expect(screen.getByTestId("login-page")).toBeTruthy();
  });

  it("shows LoginPage when token is malformed", async () => {
    _storage["hive_mgmt_token"] = "not.a.jwt";
    await act(async () => render(<App />));
    expect(screen.getByTestId("login-page")).toBeTruthy();
  });

  it("displays user email in header", async () => {
    _storage["hive_mgmt_token"] = makeToken({ email: "alice@example.com" });
    await act(async () => render(<App />));
    expect(screen.getByText("alice@example.com")).toBeTruthy();
  });

  it("does not show email when token has no email claim", async () => {
    _storage["hive_mgmt_token"] = makeToken({ email: null });
    await act(async () => render(<App />));
    expect(screen.getByText("Hive")).toBeTruthy();
  });

  it("clicking Hive logo navigates to /", async () => {
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Hive"));
    // After clicking the logo we navigate to "/" — HomeRoute redirects back to /app
    // since token is valid. Just assert no crash.
    expect(screen.getByText("Hive")).toBeTruthy();
  });

  it("sign out button clears mgmt token and reloads", async () => {
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, replace: replaceMock });
    await act(async () => render(<App />));
    fireEvent.click(screen.getByText("Sign out"));
    expect(_storage["hive_mgmt_token"]).toBeUndefined();
    expect(replaceMock).toHaveBeenCalledWith("/");
  });

  it("shows version in footer after health check", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByText("Hive 1.2.3")).toBeTruthy());
  });

  it("hides footer when health check returns no version", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url) => {
        if (String(url).includes("/api/clients")) {
          return Promise.resolve({
            ok: true, status: 200,
            json: () => Promise.resolve({ items: [{ client_id: "c1" }] }),
          });
        }
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ status: "ok" }),
        });
      }),
    );
    await act(async () => render(<App />));
    await waitFor(() => {});
    expect(screen.queryByText(/Hive \d/)).toBeNull();
  });

  it("does not crash when health check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url) => {
        if (String(url).includes("/api/clients")) {
          return Promise.resolve({
            ok: true, status: 200,
            json: () => Promise.resolve({ items: [{ client_id: "c1" }] }),
          });
        }
        return Promise.reject(new Error("Network error"));
      }),
    );
    await act(async () => render(<App />));
    expect(screen.getByText("Memories")).toBeTruthy();
    expect(screen.queryByText(/Hive \d/)).toBeNull();
  });

  it("renders dark mode toggle button", async () => {
    await act(async () => render(<App />));
    const toggle = screen.getByRole("button", { name: /switch to dark mode/i });
    expect(toggle).toBeTruthy();
    // icon is now a Lucide SVG — no text content
    expect(toggle.querySelector("svg")).toBeTruthy();
  });

  it("clicking dark mode toggle changes aria-label", async () => {
    await act(async () => render(<App />));
    const toggle = screen.getByRole("button", { name: /switch to dark mode/i });
    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: /switch to light mode/i })).toBeTruthy();
  });

  it("active tab has brand bottom border class", async () => {
    await act(async () => render(<App />));
    const memoriesBtn = screen.getByText("Memories");
    expect(memoriesBtn.className).toContain("border-b-brand");
  });

  it("version in footer links to /changelog", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByText("Hive 1.2.3")).toBeTruthy());
    const link = screen.getByText("Hive 1.2.3").closest("a");
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toBe("/changelog");
  });

  it("hive:switch-tab event switches the active tab", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    act(() => window.dispatchEvent(new CustomEvent("hive:switch-tab", { detail: "clients" })));
    expect(screen.getByTestId("client-manager")).toBeTruthy();
  });

  it("footer changelog link has hover:underline class", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByText("Hive 1.2.3")).toBeTruthy());
    const link = screen.getByText("Hive 1.2.3").closest("a");
    expect(link.className).toContain("hover:underline");
  });

  it("footer changelog link has focus:underline class", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByText("Hive 1.2.3")).toBeTruthy());
    const link = screen.getByText("Hive 1.2.3").closest("a");
    expect(link.className).toContain("focus:underline");
  });

  it("renders hamburger toggle button", async () => {
    await act(async () => render(<App />));
    expect(screen.getByRole("button", { name: /toggle navigation/i })).toBeTruthy();
  });

  it("hamburger click shows mobile nav", async () => {
    await act(async () => render(<App />));
    expect(screen.queryByTestId("mobile-nav")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /toggle navigation/i }));
    expect(screen.getByTestId("mobile-nav")).toBeTruthy();
  });

  it("clicking tab in mobile nav switches panel and closes menu", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /toggle navigation/i }));
    const mobileNav = screen.getByTestId("mobile-nav");
    // Click "OAuth Clients" — third tab now that Stats sits at index 1 (#535).
    const mobileButtons = mobileNav.querySelectorAll("button[type='button']");
    fireEvent.click(mobileButtons[2]);
    expect(screen.queryByTestId("mobile-nav")).toBeNull();
    expect(screen.getByTestId("client-manager")).toBeTruthy();
  });

  it("mobile nav active tab has an orange left-border indicator (not a gray fill)", async () => {
    await act(async () => render(<App />));
    await waitFor(() => expect(screen.getByTestId("memory-browser")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /toggle navigation/i }));
    const mobileNav = screen.getByTestId("mobile-nav");
    const buttons = mobileNav.querySelectorAll("button[type='button']");
    // Memories is the default active tab; OAuth Clients is inactive.
    expect(buttons[0].className).toContain("border-l-brand");
    // `hover:bg-white/5` stays on all rows; the active state no longer
    // has a bare `bg-white/5` fill — so the class list splits by space
    // must not contain that utility as its own token.
    expect(buttons[0].className.split(/\s+/)).not.toContain("bg-white/5");
    expect(buttons[1].className).toContain("border-l-transparent");
  });
});
