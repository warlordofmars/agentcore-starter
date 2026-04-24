// Copyright (c) 2026 John Carter. All rights reserved.
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Menu, Moon, Sun, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import ConsentBanner from "@/components/ConsentBanner";
import { useTheme } from "@/hooks/useTheme";
import { CONSENT_RESET_EVENT, clearConsent } from "@/lib/consent";

const NAV_LINK_BASE = "text-sm no-underline hover:text-white transition-colors";

const NAV_LINKS = [
  { href: "/use-cases", label: "Use cases" },
  { href: "/clients", label: "Clients" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/docs/", label: "Docs" },
];

function handleReopenConsent(e) {
  e.preventDefault();
  clearConsent();
  globalThis.dispatchEvent(new CustomEvent(CONSENT_RESET_EVENT));
}

export default function PageLayout({ children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { theme, toggle } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close the mobile menu whenever the route changes so a link click doesn't
  // leave the drawer open over the new page.
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function navLinkStyle(href) {
    const active = pathname === href;
    return {
      borderBottom: active ? "2px solid #e8a020" : "2px solid transparent",
      paddingBottom: 2,
    };
  }

  return (
    <div className="font-[system-ui,sans-serif] text-[var(--text)] flex flex-col min-h-screen">
      {/* Nav — mirrors the management app's navbar (#543 follow-up):
          logo · spacer · Sign in · theme toggle · hamburger (mobile only).
          Desktop adds the inline nav links before Sign in. */}
      <header className="bg-navy text-white">
        <div className="max-w-[1100px] mx-auto px-4 md:px-8 h-14 flex items-center gap-3">
          <button
            className="flex items-center gap-2 cursor-pointer bg-transparent border-none p-0 text-inherit"
            onClick={() => navigate("/")}
          >
            <img src="/logo.svg" alt="Hive" className="h-7 w-auto" />
            <span className="font-bold text-xl tracking-[1px]">Hive</span>
          </button>

          {/* Desktop inline nav links — hidden below md */}
          <nav className="hidden md:flex items-center gap-6 flex-1 ml-4">
            {NAV_LINKS.map(({ href, label }) => (
              <a
                key={href}
                href={href}
                className={`text-white/75 ${NAV_LINK_BASE}`}
                style={
                  label === "Docs"
                    ? { borderBottom: "2px solid transparent", paddingBottom: 2 }
                    : navLinkStyle(href)
                }
              >
                {label}
              </a>
            ))}
          </nav>

          {/* Spacer keeps right-side controls right-aligned on mobile */}
          <div className="flex-1 md:hidden" />

          {/* Always-visible right-side controls: Sign in + theme toggle */}
          <Button
            variant="nav"
            size="sm"
            className="marketing-signin-btn"
            onClick={() => navigate("/app")}
          >
            Sign in
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </Button>

          {/* Hamburger — mobile only; drawer holds nav links only */}
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden text-white hover:bg-white/10"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </Button>
        </div>

        {/* Mobile drawer (<768px): nav links only. Sign in and theme toggle
            live in the navbar on every breakpoint for visual parity with the
            management app. */}
        {menuOpen && (
          <div className="md:hidden bg-navy border-t border-white/10">
            <nav className="px-4 py-4 flex flex-col gap-1">
              {NAV_LINKS.map(({ href, label }) => {
                const active = pathname === href;
                return (
                  <a
                    key={href}
                    href={href}
                    className="block px-3 py-3 text-white/85 text-base no-underline hover:text-white hover:bg-white/5 rounded"
                    style={{ borderLeft: active ? "2px solid #e8a020" : "2px solid transparent" }}
                  >
                    {label}
                  </a>
                );
              })}
            </nav>
          </div>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border)]">
        <div className="max-w-[1100px] mx-auto px-4 md:px-8 py-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:justify-between sm:items-start">
            <div className="flex items-center gap-2">
              <img src="/logo.svg" alt="Hive" className="h-5 w-auto opacity-60" />
              <span className="font-bold text-sm tracking-[1px] text-[var(--text-muted)]">Hive</span>
            </div>
            <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-[var(--text-muted)]">
              <a href="/use-cases" className="no-underline hover:text-[var(--text)] transition-colors">Use cases</a>
              <a href="/clients" className="no-underline hover:text-[var(--text)] transition-colors">Clients</a>
              <a href="/pricing" className="no-underline hover:text-[var(--text)] transition-colors">Pricing</a>
              <a href="/faq" className="no-underline hover:text-[var(--text)] transition-colors">FAQ</a>
              <a href="/docs/" className="no-underline hover:text-[var(--text)] transition-colors">Docs</a>
              <a href="/roadmap" className="no-underline hover:text-[var(--text)] transition-colors">Roadmap</a>
              <a href="/changelog" className="no-underline hover:text-[var(--text)] transition-colors">Changelog</a>
              <a href="/status" className="no-underline hover:text-[var(--text)] transition-colors">Status</a>
              <a href="/terms" className="no-underline hover:text-[var(--text)] transition-colors">Terms</a>
              <a href="/privacy" className="no-underline hover:text-[var(--text)] transition-colors">Privacy</a>
              <a href="/subprocessors" className="no-underline hover:text-[var(--text)] transition-colors">Subprocessors</a>
              <a
                href="#cookie-preferences"
                onClick={handleReopenConsent}
                className="no-underline hover:text-[var(--text)] transition-colors"
              >
                Cookie preferences
              </a>
            </div>
          </div>
          <p className="mt-6 text-[13px] text-[var(--text-muted)]">© 2026 Hive. Free to use.</p>
        </div>
      </footer>
      <ConsentBanner />
    </div>
  );
}
