import { defineConfig } from "vitepress";

export default defineConfig({
  base: "/docs/",
  title: "Hive Docs",
  description: "Shared persistent memory for AI agents — documentation",
  cleanUrls: true,
  sitemap: {
    hostname: "https://hive.warlordofmars.net",
    // VitePress drops `base` from the item URL when writing the sitemap,
    // so prepend it here to match the deployed path at /docs/.
    transformItems: (items) =>
      items.map((item) => ({
        ...item,
        url: `docs/${item.url.replace(/^\//, "")}`,
      })),
  },
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: "/docs/favicon.svg" }],
    ["meta", { property: "og:type", content: "website" }],
    ["meta", { property: "og:site_name", content: "Hive" }],
    ["meta", { property: "og:title", content: "Hive Docs — Shared Memory for Claude Agents" }],
    [
      "meta",
      {
        property: "og:description",
        content: "Documentation for Hive, a shared persistent memory service for Claude agents and teams.",
      },
    ],
    ["meta", { property: "og:url", content: "https://hive.warlordofmars.net/docs/" }],
    [
      "meta",
      { property: "og:image", content: "https://hive.warlordofmars.net/social-preview.png" },
    ],
    ["meta", { property: "og:image:width", content: "1200" }],
    ["meta", { property: "og:image:height", content: "630" }],
    ["meta", { property: "og:image:alt", content: "Hive — Shared Memory for Claude Agents" }],
    ["meta", { name: "twitter:card", content: "summary_large_image" }],
    ["meta", { name: "twitter:title", content: "Hive Docs — Shared Memory for Claude Agents" }],
    [
      "meta",
      {
        name: "twitter:description",
        content: "Documentation for Hive, a shared persistent memory service for Claude agents and teams.",
      },
    ],
    [
      "meta",
      { name: "twitter:image", content: "https://hive.warlordofmars.net/social-preview.png" },
    ],
    ["meta", { name: "twitter:image:alt", content: "Hive — Shared Memory for Claude Agents" }],
  ],

  themeConfig: {
    logo: { src: "/logo.svg", alt: "Hive" },
    siteTitle: "Hive",
    // logoLink is used directly (no withBase() applied), so "/" goes to the
    // marketing page root, not /docs/.
    logoLink: "/",
    // Nav links are rendered via the nav-bar-content-after layout slot as plain
    // <a> elements so we control their exact position (right of social/search)
    // and Vue Router never intercepts the Sign in click.
    nav: [],

    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "What is Hive?", link: "/getting-started/what-is-hive" },
          { text: "Quick start", link: "/getting-started/quick-start" },
          { text: "Connect your MCP client", link: "/getting-started/connect-client" },
          { text: "Your first memory", link: "/getting-started/first-memory" },
        ],
      },
      {
        text: "MCP tools reference",
        items: [
          { text: "Overview", link: "/tools/overview" },
          { text: "remember", link: "/tools/remember" },
          { text: "remember_blob", link: "/tools/remember-blob" },
          { text: "recall", link: "/tools/recall" },
          { text: "forget", link: "/tools/forget" },
          { text: "list_memories", link: "/tools/list-memories" },
          { text: "search_memories", link: "/tools/search-memories" },
          { text: "summarize_context", link: "/tools/summarize-context" },
          { text: "pack_context", link: "/tools/pack-context" },
          { text: "Prompts (slash commands)", link: "/tools/prompts" },
        ],
      },
      {
        text: "Management UI",
        items: [
          { text: "Memory Browser", link: "/ui-guide/memory-browser" },
          { text: "OAuth clients", link: "/ui-guide/oauth-clients" },
          { text: "Activity log", link: "/ui-guide/activity-log" },
        ],
      },
      {
        text: "Concepts",
        items: [
          { text: "How memory scoping works", link: "/concepts/memory-scoping" },
          { text: "Tags and organisation", link: "/concepts/tags" },
          { text: "Key naming conventions", link: "/concepts/key-conventions" },
          { text: "Large memory", link: "/concepts/large-memory" },
          { text: "Quotas and rate limits", link: "/concepts/quotas" },
          { text: "MCP Resources", link: "/concepts/resources" },
        ],
      },
      {
        text: "FAQ",
        link: "/faq",
      },
      {
        text: "API reference",
        link: "/api-reference",
      },
    ],

    socialLinks: [],
    // Enable dark-mode toggle so the docs site matches the dark management
    // app + marketing surfaces — and so the Redoc API reference can flip
    // into its dark palette. Default to user's OS preference.
    appearance: true,

    footer: {
      message: "Hive — shared persistent memory for AI agents",
    },

    search: {
      provider: "local",
    },
  },
});
