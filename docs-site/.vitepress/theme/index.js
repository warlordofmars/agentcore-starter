import { h } from "vue";
import DefaultTheme from "vitepress/theme";
import "./style.css";

export default {
  ...DefaultTheme,

  // Inject nav links as plain <a> elements via nav-bar-content-after so
  // they render at the far right of the navbar, matching the marketing site:
  // Use cases · Clients · Pricing · FAQ · Docs | Sign in
  //
  // VitePress .content-body flex order:
  //   [nav-bar-content-before] Search Menu Appearance Social [nav-bar-content-after]
  //
  // Sign in sits in the navbar at every breakpoint so it parallels the
  // management app's layout (follow-up to #543). The mobile drawer holds
  // nav links only.
  Layout() {
    return h(DefaultTheme.Layout, null, {
      "nav-bar-content-after": () =>
        h("div", { class: "docs-nav-group" }, [
          h("a", { href: "/use-cases", class: "docs-nav-link" }, "Use cases"),
          h("a", { href: "/clients", class: "docs-nav-link" }, "Clients"),
          h("a", { href: "/pricing", class: "docs-nav-link" }, "Pricing"),
          h("a", { href: "/faq", class: "docs-nav-link" }, "FAQ"),
          h(
            "a",
            { href: "/docs/getting-started/what-is-hive", class: "docs-nav-link docs-nav-link--active" },
            "Docs",
          ),
          h("a", { href: "/app", class: "docs-signin-btn docs-signin-btn--always" }, "Sign in"),
        ]),
      // Mobile expanded menu — nav links only (Sign in is always in navbar).
      // The Docs link carries --active on this site so it gets an orange
      // left-border indicator matching the marketing site's current-page
      // affordance (instead of VitePress's default gray background fill).
      "nav-screen-content-after": () =>
        h("div", { class: "docs-screen-group" }, [
          h("a", { href: "/use-cases", class: "docs-screen-nav-link" }, "Use cases"),
          h("a", { href: "/clients", class: "docs-screen-nav-link" }, "Clients"),
          h("a", { href: "/pricing", class: "docs-screen-nav-link" }, "Pricing"),
          h("a", { href: "/faq", class: "docs-screen-nav-link" }, "FAQ"),
          h(
            "a",
            {
              href: "/docs/getting-started/what-is-hive",
              class: "docs-screen-nav-link docs-screen-nav-link--active",
            },
            "Docs",
          ),
        ]),
    });
  },

  enhanceApp() {
    // Vue Router 4 intercepts ALL same-origin anchor clicks, even hrefs outside
    // its /docs/ base. Intercept in capture phase and force window.location.href
    // for links that must cause a real full-page navigation.
    if (typeof window !== "undefined") {
      document.addEventListener(
        "click",
        (e) => {
          // Logo → marketing page root
          const title = e.target.closest(".VPNavBarTitle .title");
          if (title && title.getAttribute("href") === "/") {
            e.preventDefault();
            e.stopImmediatePropagation();
            window.location.href = "/";
            return;
          }
          // Marketing site links (outside /docs/) → full-page navigation
          const navLink = e.target.closest(".docs-nav-link, .docs-screen-nav-link");
          if (navLink) {
            const href = navLink.getAttribute("href");
            if (href && !href.startsWith("/docs/")) {
              e.preventDefault();
              e.stopImmediatePropagation();
              window.location.href = href;
              return;
            }
          }
          // Sign in → /app
          const signin = e.target.closest(".docs-signin-btn, .docs-signin-screen-btn");
          if (signin) {
            e.preventDefault();
            e.stopImmediatePropagation();
            window.location.href = "/app";
          }
        },
        true,
      );
    }
  },
};
