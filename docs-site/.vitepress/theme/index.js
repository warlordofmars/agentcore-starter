import { h } from "vue";
import DefaultTheme from "vitepress/theme";
import "./style.css";

export default {
  ...DefaultTheme,

  // Inject nav links via nav-bar-content-after so they render at the far
  // right of the VitePress navbar.
  Layout() {
    return h(DefaultTheme.Layout, null, {
      "nav-bar-content-after": () =>
        h("div", { class: "docs-nav-group" }, [
          h(
            "a",
            { href: "/docs/", class: "docs-nav-link docs-nav-link--active" },
            "Docs",
          ),
          h("a", { href: "/app", class: "docs-signin-btn docs-signin-btn--always" }, "Sign in"),
        ]),
      "nav-screen-content-after": () =>
        h("div", { class: "docs-screen-group" }, [
          h(
            "a",
            {
              href: "/docs/",
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
