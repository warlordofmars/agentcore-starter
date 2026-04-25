import { defineConfig } from "vitepress";

export default defineConfig({
  base: "/docs/",
  title: "AgentCore Starter Docs",
  description: "Documentation for AgentCore Starter",
  cleanUrls: true,
  sitemap: {
    hostname: "https://example.com",
    transformItems: (items) =>
      items.map((item) => ({
        ...item,
        url: `docs/${item.url.replace(/^\//, "")}`,
      })),
  },
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: "/docs/favicon.svg" }],
    ["meta", { property: "og:type", content: "website" }],
    ["meta", { property: "og:site_name", content: "AgentCore Starter" }],
    ["meta", { property: "og:title", content: "AgentCore Starter Docs" }],
    [
      "meta",
      {
        property: "og:description",
        content: "Documentation for AgentCore Starter.",
      },
    ],
  ],

  themeConfig: {
    logo: { src: "/logo.svg", alt: "AgentCore Starter" },
    siteTitle: "AgentCore Starter",
    // logoLink goes to the marketing page root, not /docs/.
    logoLink: "/",
    // Nav links are rendered via nav-bar-content-after as plain <a> elements.
    nav: [],

    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "Introduction", link: "/getting-started/introduction" },
          { text: "Quick start", link: "/getting-started/quick-start" },
        ],
      },
    ],

    socialLinks: [],
    appearance: true,

    footer: {
      message: "AgentCore Starter",
    },

    search: {
      provider: "local",
    },
  },
});
