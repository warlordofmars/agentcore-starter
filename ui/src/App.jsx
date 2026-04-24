// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Menu, Moon, Sun, X } from "lucide-react";
import { trackEvent, trackPageView } from "./analytics.js";
import { api } from "./api.js";
import ActivityLog from "./components/ActivityLog.jsx";
import AuthCallback from "./components/AuthCallback.jsx";
import ClientManager from "./components/ClientManager.jsx";
import Dashboard from "./components/Dashboard.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import LogViewer from "./components/LogViewer.jsx";
import ChangelogPage from "./components/ChangelogPage.jsx";
import FaqPage from "./components/FaqPage.jsx";
import HomePage from "./components/HomePage.jsx";
import NotFoundPage from "./components/NotFoundPage.jsx";
import PrivacyPage from "./components/PrivacyPage.jsx";
import SubprocessorsPage from "./components/SubprocessorsPage.jsx";
import TermsPage from "./components/TermsPage.jsx";
import LoginPage from "./components/LoginPage.jsx";
import McpClientsPage from "./components/McpClientsPage.jsx";
import OnboardingTour from "./components/OnboardingTour.jsx";
import PricingPage from "./components/PricingPage.jsx";
import RoadmapPage from "./components/RoadmapPage.jsx";
import StatusPage from "./components/StatusPage.jsx";
import UseCasesPage from "./components/UseCasesPage.jsx";
import ApiKeysPanel from "./components/ApiKeysPanel.jsx";
import MemoryBrowser from "./components/MemoryBrowser.jsx";
import SetupPanel from "./components/SetupPanel.jsx";
import Stats from "./components/Stats.jsx";
import UsersPanel from "./components/UsersPanel.jsx";
import { Button } from "./components/ui/button.jsx";
import { Toaster } from "./components/ui/sonner.jsx";
import { useTheme } from "./hooks/useTheme.js";

const BASE_TABS = [
  { id: "memories", label: "Memories" },
  { id: "stats", label: "Stats" },
  { id: "clients", label: "OAuth Clients" },
  { id: "api-keys", label: "API Keys" },
  { id: "activity", label: "Activity Log" },
  { id: "setup", label: "Setup" },
];
const ADMIN_TABS = [
  ...BASE_TABS,
  { id: "users", label: "Users" },
  { id: "dashboard", label: "Dashboard" },
  { id: "logs", label: "Logs" },
];

function parseToken(token) {
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/")));
  } catch {
    return null;
  }
}

function isTokenValid(token) {
  const payload = parseToken(token);
  return payload ? payload.exp * 1000 > Date.now() : false;
}

function signOut() {
  localStorage.removeItem("hive_mgmt_token");
  globalThis.location.replace("/");
}

function AppShell() {
  const [tab, setTab] = useState("memories");
  const [menuOpen, setMenuOpen] = useState(false);

  function switchTab(id) {
    setTab(id);
    trackEvent("tab_view", { tab_name: id });
  }
  const [version, setVersion] = useState(null);
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();

  const token = localStorage.getItem("hive_mgmt_token") ?? "";
  const authenticated = isTokenValid(token);

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((data) => setVersion(data.version ?? null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    api.listClients()
      .then((data) => {
        // Skip the auto-switch when the OnboardingTour is still
        // active — otherwise step 1 spotlights "Memories" while
        // the underlying content silently jumps to Setup, leaving
        // the spotlight pointing at a tab that's no longer the
        // active panel.
        const tourActive = !localStorage.getItem("hive_tour_dismissed");
        if (data?.items.length === 0 && !tourActive) setTab("setup");
      })
      .catch(() => {});
  }, [authenticated]);

  useEffect(() => {
    function onSwitchTab(e) { switchTab(e.detail); }
    globalThis.addEventListener("hive:switch-tab", onSwitchTab);
    return () => globalThis.removeEventListener("hive:switch-tab", onSwitchTab);
  }, []);

  if (!authenticated) {
    return <LoginPage />;
  }

  const claims = parseToken(token);
  const isAdmin = claims.role === "admin";
  const userEmail = claims.email ?? "";
  const tabs = isAdmin ? ADMIN_TABS : BASE_TABS;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-navy text-white px-4 md:px-6 flex items-center gap-3 md:gap-6 h-14 relative">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 cursor-pointer bg-transparent border-none p-0 text-inherit"
        >
          <img src="/logo.svg" alt="Hive" className="w-7 h-7" />
          <span className="font-bold text-xl tracking-wide">Hive</span>
        </button>

        {/* Desktop tab nav — hidden on mobile. Each button carries
            data-tab-id so the OnboardingTour can spotlight it
            without prop-drilling refs through. */}
        <nav className="hidden md:flex gap-1 flex-1">
          {tabs.map((t) => (
            <Button
              key={t.id}
              data-tab-id={t.id}
              variant="ghost"
              size="sm"
              onClick={() => switchTab(t.id)}
              className={`text-sm border-b-2 rounded-none pb-0 ${
                tab === t.id ? "border-b-brand" : "border-b-transparent"
              }`}
            >
              {t.label}
            </Button>
          ))}
        </nav>

        {/* Spacer on mobile so right-side items stay right */}
        <div className="flex-1 md:hidden" />

        <a
          href="/docs/"
          className="hidden md:block text-[13px] text-white/60 no-underline hover:text-white/90"
        >
          Docs
        </a>

        {userEmail && (
          <span className="hidden md:inline text-[13px] text-white/70">{userEmail}</span>
        )}

        <Button variant="outline" size="sm" onClick={signOut}>
          Sign out
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </Button>

        {/* Hamburger — mobile only */}
        <Button
          variant="ghost"
          size="sm"
          className="md:hidden text-white hover:bg-white/10"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle navigation"
          aria-expanded={menuOpen}
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </Button>

        {/* Mobile nav dropdown */}
        {menuOpen && (
          <nav
            data-testid="mobile-nav"
            className="absolute top-14 left-0 right-0 bg-navy border-t border-white/10 z-50"
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                data-tab-id={t.id}
                type="button"
                className={`w-full text-left px-6 py-3 text-sm text-white bg-transparent cursor-pointer font-[inherit] min-h-[44px] hover:bg-white/5 border-l-2 ${
                  tab === t.id
                    ? "font-semibold border-l-brand"
                    : "border-l-transparent"
                }`}
                onClick={() => { switchTab(t.id); setMenuOpen(false); }}
              >
                {t.label}
              </button>
            ))}
          </nav>
        )}
      </header>

      <main className="flex-1 p-4 md:p-6 max-w-[1100px] mx-auto w-full">
        {tab === "memories" && <MemoryBrowser />}
        {tab === "stats" && <Stats />}
        {tab === "clients" && <ClientManager />}
        {tab === "api-keys" && <ApiKeysPanel />}
        {tab === "activity" && <ActivityLog />}
        {tab === "users" && isAdmin && <UsersPanel />}
        {tab === "setup" && <SetupPanel />}
        {tab === "dashboard" && isAdmin && <Dashboard />}
        {tab === "logs" && isAdmin && <LogViewer />}
      </main>

      {version && (
        <footer className="text-center py-2 text-xs text-[var(--text-muted)] border-t border-[var(--border)]">
          <a
            href="/changelog"
            className="text-inherit no-underline hover:underline focus:underline"
          >
            Hive {version}
          </a>
        </footer>
      )}

      <Toaster />
      <OnboardingTour isAdmin={isAdmin} />
    </div>
  );
}

function HomeRoute() {
  const token = localStorage.getItem("hive_mgmt_token") ?? "";
  if (isTokenValid(token)) {
    return <Navigate to="/app" replace />;
  }
  return <HomePage />;
}

function RouteTracker() {
  const location = useLocation();
  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);
  return null;
}

export default function App() {
  useTheme(); // apply data-theme to <html> for all routes
  // ErrorBoundary wraps the entire route tree so a thrown render
  // exception in any page lands on the friendly fallback instead of
  // a blank tab. Catch-all `*` route renders the branded 404 page —
  // CloudFront already serves index.html for unknown paths (with a
  // 200 so the SPA can route), so hitting `*` is the React Router
  // signal that no route matched.
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <RouteTracker />
        <Routes>
          <Route path="/" element={<HomeRoute />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/faq" element={<FaqPage />} />
          <Route path="/use-cases" element={<UseCasesPage />} />
          <Route path="/clients" element={<McpClientsPage />} />
          <Route path="/changelog" element={<ChangelogPage />} />
          <Route path="/roadmap" element={<RoadmapPage />} />
          <Route path="/status" element={<StatusPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/subprocessors" element={<SubprocessorsPage />} />
          <Route path="/app" element={<AppShell />} />
          <Route path="/oauth/callback" element={<AuthCallback />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
