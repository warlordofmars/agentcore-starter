---
title: API reference
outline: deep
pageClass: api-reference-page
---

<script setup>
import { onMounted, onBeforeUnmount } from "vue";

const SCRIPT_ID = "swagger-ui-bundle";
const CSS_LIGHT_ID = "swagger-ui-css-light";
const CSS_DARK_ID = "swagger-ui-css-dark";
const CONTAINER_ID = "swagger-ui-container";

const SWAGGER_JS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js";
const SWAGGER_CSS_LIGHT = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css";
// Amoenus/SwaggerDark is a community dark theme designed as a drop-in
// replacement for the standard Swagger UI CSS. Loading it (and disabling
// the light one) when html.dark is set flips the whole reference without
// re-initialising SwaggerUIBundle — much cleaner than Redoc's theme object.
const SWAGGER_CSS_DARK = "https://cdn.jsdelivr.net/gh/Amoenus/SwaggerDark@v1.0.0/SwaggerDark.css";

function isDark() {
  return document.documentElement.classList.contains("dark");
}

function ensureCss(id, href) {
  let link = document.getElementById(id);
  if (!link) {
    link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  }
  return link;
}

function applyTheme() {
  // Keep the base (light) stylesheet loaded always — SwaggerDark is a set
  // of layered overrides, not a complete replacement. Disabling the base
  // left Swagger UI totally unstyled in dark mode. Ordering matters: the
  // dark link is appended after the light one, so its rules win in the
  // cascade whenever it's enabled.
  ensureCss(CSS_LIGHT_ID, SWAGGER_CSS_LIGHT);
  const dark = ensureCss(CSS_DARK_ID, SWAGGER_CSS_DARK);
  dark.disabled = !isDark();
}

function mountSwagger() {
  if (!window.SwaggerUIBundle || !document.getElementById(CONTAINER_ID)) return;
  window.SwaggerUIBundle({
    url: "/docs/openapi.json",
    dom_id: "#" + CONTAINER_ID,
    deepLinking: true,
    presets: [window.SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
  });
}

let observer = null;

onMounted(() => {
  applyTheme();

  function start() {
    mountSwagger();
    observer = new MutationObserver(applyTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  if (window.SwaggerUIBundle) {
    start();
    return;
  }
  const existing = document.getElementById(SCRIPT_ID);
  if (existing) {
    existing.addEventListener("load", start, { once: true });
    return;
  }
  const script = document.createElement("script");
  script.id = SCRIPT_ID;
  script.src = SWAGGER_JS;
  script.addEventListener("load", start, { once: true });
  document.body.appendChild(script);
});

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
});
</script>

<style>
/*
  Layout: widen the API reference page so Swagger UI gets the full available
  canvas (minus the VP left sidebar). VitePress's default doc layout caps
  .container width and reserves room for an aside TOC that Swagger UI
  doesn't need since the reference has its own in-page navigation.
*/
.api-reference-page .VPDoc {
  padding: 0 !important;
}

.api-reference-page .VPDoc .container,
.api-reference-page .VPDoc .content,
.api-reference-page .VPDoc .content-container {
  max-width: none !important;
  padding: 0 !important;
  margin: 0 !important;
}

.api-reference-page .VPDocAsideOutline,
.api-reference-page .aside {
  display: none !important;
}

/* Intro H1 + paragraph: VitePress wraps them in .vp-doc > div > … so a
   direct-child selector off .vp-doc misses. Descendant selector it is —
   there's only one H1 and the intro <p> on this page, so no collateral. */
.api-reference-page .vp-doc h1,
.api-reference-page .vp-doc div > p {
  padding: 0 24px;
  margin: 24px 0 0;
}

.api-reference-page .vp-doc div > p {
  margin-bottom: 24px;
}

.api-reference-page #swagger-ui-container {
  width: 100%;
  margin-top: 24px;
}
</style>

# API reference

Every endpoint the Hive management API exposes, auto-generated from the deployed FastAPI app. Use it alongside the [MCP tools reference](/tools/overview) if you're building SDKs or bots against the REST surface.

<div id="swagger-ui-container"></div>
