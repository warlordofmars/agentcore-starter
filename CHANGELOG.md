# Changelog

All notable changes to Hive are documented here. Releases correspond to GitHub tags and follow [semantic versioning](https://semver.org/).

See the [GitHub releases page](https://github.com/warlordofmars/hive/releases) for full release notes generated from merged PRs.

## [Unreleased]

_Changes accumulated on `development` since v0.26.0. Will be rolled into the next release._

## v0.26.0 — 2026-04-24

Large-memory milestone (#451) — Hive now stores documents, images, and
binary blobs alongside plain-text memories. Text over 100 KB routes
transparently to S3, `remember_blob` accepts up to 10 MB of any MIME
type, and the management UI renders each content type appropriately.
A second storage-bytes dimension joins the existing memory-count
quota, with admin override UI for both.

### Added

#### Large memory

- **Foundation — data model, S3 bucket, storage routing.** `Memory` grows `value_type` (`text` / `text-large` / `image` / `blob`), `s3_uri`, `content_type`, and `size_bytes`. A new `hive-memory-blobs` S3 bucket (SSE-S3, block-public, enforce-ssl) is provisioned per environment with scoped IAM for both Lambda roles. Writes over 100 KB promote inline text to `text-large` and upload to S3; existing sub-threshold memories stay in DynamoDB untouched. (#497)
- **Transparent large-text recall + full-text vector embedding.** `remember(key, value)` accepts any size — above the 100 KB threshold the value moves to S3 and `recall` transparently fetches it. `search_memories` embeds the full text (not just the first N bytes), so semantic search works on multi-hundred-KB documents. (#498)
- **`remember_blob` tool + binary MCP content types.** New tool stores up to 10 MB of binary data (images, documents, archives) via MCP; `recall` returns `ImageContent` / `BlobContent` based on the MIME type. Oversized uploads fail with a clear error; list / search skip binary from semantic search and surface a type badge so agents know the memories exist. (#499)
- **MemoryBrowser renders text-large, images, and blobs.** List view shows a type badge plus size; `text-large` shows the first ~500 chars with a "Show full content" affordance; images preview inline; blobs surface filename / MIME / size with a download button. (#501)

#### Storage quota

- **Two-dimension quota — memory count + storage bytes, admin override UI.** Quota accounting adds a `size_bytes` dimension summed across every `value_type`. Per-user override UI in the admin Users panel (`GET` / `PUT /api/users/{id}/limits`) lets admins bump individual users above the system default. `QuotaGauge` shows both dimensions side-by-side; the storage bar exposes `role="progressbar"` + `aria-valuenow/min/max` so screen readers report usage. Quota checks run delta-based on update paths (`remember`, `remember_if_absent`, `remember_blob`, and both API update endpoints), so growing an existing memory past the budget is rejected just like a new write. (#500, #636)

#### Operations

- **Blob cleanup.** `forget(key)` deletes the associated S3 object for non-text memories; a CDK S3 lifecycle rule sweeps orphaned objects after 30 days as a safety net. Every delete emits a structured log event so cleanup is auditable. (#502)

#### Documentation

- New docs pages: `concepts/large-memory.md` explains the text-large vs binary split and size limits; `tools/remember_blob.md` is a full tool reference; existing `tools/remember.md` and `ui-guide/memory-browser.md` note the transparent routing and new rendering. (#503)

### Fixed

#### Security

- **`list_memories` and `summarize_context` now scope to the requesting user.** Both tools previously returned memories belonging to other users when called by a non-admin. Fixed plus fail-closed behaviour added across `remember`, `remember_if_absent`, `list_memories`, and `summarize_context` so missing or unscoped client records reject the call instead of silently widening scope. (#631)

#### Reliability

- **DCR clients created during OAuth bypass are associated with the test user.** Local e2e flows that mint new clients via the bypass no longer leave them orphaned. (#635)

### Meta

- Regenerated OpenAPI spec so `UpdateUserLimitsRequest.memory_limit` / `storage_bytes_limit` advertise their `minimum: 1` constraint to generated clients (`Field(ge=1)` replaces the prior `field_validator`). (#636)

## v0.25.0 — 2026-04-21

UI/UX polish release — every tab the user touches on first visit
now has a clear path forward, quota exhaustion is diagnosed rather
than just reported, and there's a public roadmap for the first time.

### Added

#### Onboarding

- First-visit **tour overlay** walks new users through Memories → Setup → Activity Log → OAuth Clients (admin users also see a Dashboard step). Each step spotlights the relevant tab, dispatches a tab switch so the page content matches the narration, and dismisses via Skip / backdrop-click / Escape / Got-it. Dismissal persists in `localStorage`. `aria-modal="true"` + focus management + Escape-to-dismiss match the accessibility expectations of a shadcn-style dialog without pulling in Radix. (#429, #619)
- **MemoryBrowser empty state** previously said "use the remember tool in your MCP client"; now offers a two-action call-to-action (+ New Memory button plus an Open Setup link that deep-links into the Setup tab via the existing `hive:switch-tab` event). (#429, #619)
- **First-memory celebration** — Sonner toast fires once per user when the first create succeeds. Gated on a per-browser `hive_first_memory` localStorage flag **and** a server-side check that the unfiltered workspace has exactly one memory, so existing users who just happen to be on a fresh browser don't get a misleading "first memory" toast. The probe caches its negative result in `hive_first_memory_skipped` so existing-workspace users don't re-query on every subsequent create. (#429, #619)

#### Error surfaces

- **Branded 404** (`NotFoundPage.jsx`) replaces the silent redirect-to-home that any unknown SPA path used to get. Offers Home / Docs / Contact-support links so users have a path forward. CloudFront-level error routing for 403/404 → `/index.html` was already in place; this PR wires React Router's catch-all to the new page instead of `<Navigate to="/">`. (#417, #618)
- **Root-level `ErrorBoundary`** wraps the entire route tree. A thrown render exception in any page now lands on a friendly "Something went wrong" fallback with Reload + Contact-support instead of a blank tab; `componentDidCatch` logs the error via `console.error` for developer inspection, with room to wire a backend ingest endpoint later. (#417, #618)
- **Docs-site 404** (`docs-site/404.md`) overrides VitePress's generic default with on-brand copy linking to docs home, quick start, tools reference, and the marketing home. (#417, #618)

#### Quota / rate-limit UX

- SetupPanel's Usage section renders a **`QuotaCallout`** below the existing QuotaBar rows when utilisation hits ≥ 80% (amber) or 100% (red). Severity is driven by the worst-case bucket (one resource at 100% is enough to block writes) and copy is tailored per bucket — memory-only, client-only, or combined — so "New memories cannot be saved" doesn't show up when it's actually the client quota that's full. Links to `mailto:hello@warlordofmars.net` for capacity requests. `_quotaSeverity` / `_quotaRatio` / `QuotaBar` all treat limits ≤ 0 as "unconfigured" rather than "infinitely full", and the whole Usage section hides when no limits are configured. (#359, #616)
- **MemoryBrowser surfaces 429 responses** from `createMemory` with a richer banner instead of the bare server detail string. Banner body is quota-vs-rate-limit agnostic ("Try again later, or open Setup to review your current usage"), and an **Open Setup** button dispatches `hive:switch-tab` then scrolls to the `#usage` anchor. `api.js` now attaches the HTTP status to thrown errors so callers can branch on 429 without scraping the message. (#359, #616)

#### Roadmap visibility

- Public **`/roadmap`** page fetches `public-roadmap`-labelled issues from GitHub's REST API at render time and buckets them into **Now / Next / Later / Shipped** columns via a dedicated `roadmap:*` label namespace (kept separate from the existing backlog `status:*` taxonomy that `label-check.yml` enforces). Shipped column is closed-state regardless of label, sorted most-recent-first and capped to 8. PRs are filtered out of the `/issues` endpoint. Each card links to its issue so upvote reactions feed prioritisation directly. Footer link in PageLayout. (#430, #620, #623)

#### Memory browser

- **Version history now shows a word-level diff** against the current live value — each row in the History panel has a Show diff / Hide diff toggle that expands an inline `<ins>`/`<del>` rendering via the `diff` npm package. Restore stays in place. Diff colours are driven by `var(--success)` / `var(--danger)` so both themes stay clean. (#383, #621)
- **Semantic search playground** — the search input already surfaced a `{N}% match` badge on every result, but there was no way to tune `top_k`. A range slider (1–100, default 50) appears only in search mode and re-runs the query on change after the existing 400ms debounce. `aria-label` + `aria-live` on the count span. (#384, #622)

### Fixed

- **E2e tab-click timeouts** — the OnboardingTour's viewport-covering backdrop was intercepting every nav-tab click in Playwright tests that had no way to dismiss it. `browser_page` / `admin_browser_page` fixtures now use `browser.new_context()` + `context.add_init_script()` to pre-set `hive_tour_dismissed=1` before any page load, so e2e tests proceed against the real UI. (#624)

### Meta

- CLAUDE.md: documented the **public-roadmap label convention** — `public-roadmap` as the gate label, `roadmap:now / :next / :later` for column placement, Shipped auto-populating from closed issues — and why `roadmap:*` is orthogonal to `status:*`. (#623)

## v0.24.0 — 2026-04-20

### Added

#### Stats tab — six new analytics views

- New **Stats** tab in the management UI, fed by a single `/api/account/stats` endpoint (#572). Each view rolls up the caller's memories without touching cross-tenant data, and gracefully degrades when the workspace is empty. Six views landed across the milestone:
  - Top-recalled memories, tag distribution, memory-growth trend, and a quota gauge — the at-a-glance dashboard surfaces the most-used and least-used corners of the workspace (#581).
  - 12-month activity heatmap (calendar grid keyed off `recall_count` / `created_at`) so usage patterns and dormant periods are visible at a glance (#579).
  - Memory freshness scatter — plots `last_accessed_at` vs `created_at` so stale items are visually obvious (#600, post-merge cleanup in #603).
  - Client contribution breakdown — per-client write counts, recall counts, and quota share (#604).
  - Tag co-occurrence network — graph view of which tags appear together, useful for spotting taxonomy drift (#605).

#### MCP surface

- New `pack_context(topic, budget_tokens=2000, ordering="relevance+recency")` tool — token-budget-aware retrieval that returns as many relevant memories as fit in the caller's remaining context window, formatted as a markdown block. Same hybrid retrieval backbone as `search_memories`; greedy packer skips (rather than truncates) over-budget memories so a half-quoted decision can't slip through; redacted memories always excluded. Uses a 4-chars-per-token heuristic instead of `tiktoken` to keep the Lambda bundle slim. (#608, docs polish in #613)
- Memories are now exposed as **MCP Resources** alongside tools, URI-addressable via `memory://_index` (the static index) and `memory://{key}` (templated). Resource handlers enforce `memories:read` scope and the same rate-limit / tenant-isolation as tools; redacted and expired items are filtered. The reserved `_index` namespace avoids collision with a memory whose key happens to be `index`. (#609)
- New **MCP Prompts** — slash commands for common Hive workflows (`recall`, `summarize`, etc.), discoverable via `prompts/list` in supporting clients. (#606)

#### Observability & ops

- `RateLimitedRequests` CloudWatch metric (EMF) emitted on every 429 from the rate-limiter + a Dashboard card showing the rolling count, so quota exhaustion shows up before a customer reports it. (#571)

#### Dev experience & CI

- Autonomous Copilot review loop integrated into the §7.5 PR workflow — every agent-safe PR gets a Copilot review, with auto-merge deferred until the loop resolves; up to 5 fix-iterations before stopping for human review. Multiple iterations of process-tightening landed across the milestone after observed gaps: re-arm auto-merge after each Copilot-driven fix push, fix the `get_reviews` blind spot in the polling loop, require a reply on every thread before resolving, wait ~90s after the Agent check completes before polling for line-level comments, bump the iteration cap from 3 to 5. (#580, #582, #601, #603, #607, #612)

### Fixed

#### Security

- **OAuth auth-code redemption is now atomic** — closes RFC 6749 §10.5 TOCTOU. Two concurrent `POST /oauth/token` requests with the same code used to both pass the `auth_code.used` pre-check before either could write back, both successfully exchanging for token pairs. `mark_auth_code_used` now uses a conditional `UpdateItem` guarded by `attribute_exists(PK) AND used = false`; the loser of the race gets a `ConditionalCheckFailedException`, translated to a new `AuthCodeAlreadyUsed` exception that the token endpoint maps to the same `400 "Invalid or already-used code"` response as the pre-check. The `attribute_exists(PK)` guard also closes a forged-code path: callers can no longer mint tokens by passing arbitrary strings. (#611)

#### Reliability

- Audit-log endpoint missed events that landed near midnight UTC — the date-range query was off-by-one in the hour-sharded `AUDIT#{date}#{hour}` partition lookup. Now the boundary hours are queried correctly so compliance trails stay complete. (#599)

### Meta

- CLAUDE.md §7.5 hardened across the milestone: every Copilot review thread now gets a reply before resolution; the loop polls for line-level comments after the Agent check completes (with a ~90s buffer) instead of relying on top-level reviews; iteration cap raised from 3 to 5; auto-merge re-armed after each Copilot-driven fix push so a downstream finding doesn't leave the PR un-merged. (#582, #607, #612)

## v0.23.0 — 2026-04-19

### Added

#### Documentation

- Auto-generated REST API reference at `/docs/api-reference`, rendered from the deployed FastAPI app's OpenAPI spec. Starts in light mode, follows the docs-site appearance toggle into dark mode, and is kept in sync with a CI drift check against a committed `openapi.json` snapshot. After landing on Scalar and then Redoc (neither of which survived light-mode scrutiny on our navy chrome), settled on Swagger UI with a community dark stylesheet overlay. (#421, #551, #552, #554, #558)

#### Admin dashboard

- Alarm row now scales with signal instead of drowning the view in green pills. During normal operation a single `✓ N alarms OK` summary badge replaces the per-alarm row; as soon as anything is firing, the `ALARM` / `INSUFFICIENT_DATA` badges appear individually with a muted `+N OK` pill trailing them. (#369, #553)

### Changed

#### Cross-surface mobile UX

- Swept the marketing site, docs site, and management app for mobile parity. Unified navbar across all three: always-visible Sign in/out, always-visible theme toggle, hamburger drawer identical in layout. Drawer items left-aligned with an orange left-border active indicator (replacing the gray-fill highlight). Dashboard, Activity Log, and Logs viewer no longer overflow horizontally on narrow viewports — header / stat-card / filter rows now wrap, and individual log rows restack into three lines on mobile (header / log-group / 2-line-clamped summary with tap-to-expand). (#533, #541, #543, #544, #545, #547, #549, #550, #562, #563, #564, #566)

### Fixed

#### CI reliability

- Raised the httpx timeout on all e2e HTTP clients from the default 5s to 30s, absorbing Lambda cold-start on the first DCR call in a test run. (#565)
- Doubled the tag-filter GSI-propagation retry window in `test_create_and_see_memory` from 60s to 120s while #568 investigates the underlying propagation lag. The raised budget keeps the dev pipeline green; the lag itself is treated as a product bug, not a test flake. (#546)

### Meta

- Removed the `release-milestone-watcher` workflow — the CLAUDE.md autonomous loop already detects milestone drain in-session, making the separate workflow redundant. (#531, #532)

## v0.22.0 — 2026-04-18

### Added

#### MCP surface

- Every MCP tool response carries the caller's quota and rate-limit state under a top-level `_meta.hive` block (`memory_quota.{used,limit,remaining}` + `rate_limit.{per_minute_limit,per_day_limit}`) so well-behaved agents can self-throttle before hitting a hard limit. New docs page `/docs/concepts/quotas` documents the schema. `memory_history` now returns `{versions, count}` instead of a bare list for a consistent structured-content envelope. (#453)
- Long-running tools (`search_memories`, `summarize_context`) emit MCP `notifications/progress` events at major stages; supporting clients render progress indicators. Best-effort — falls through on clients that don't support it. (#449)
- `remember(key, value, …, version=)` accepts an optimistic-lock token from a prior `recall`/`list_memories` response; concurrent-write conflicts raise a `ToolError` with the current state JSON-encoded so agents can compare-and-retry. (#391)
- `search_memories` now hybrid-retrieves: weighted blend of semantic similarity, term-frequency keyword match, and half-life recency decay against `last_accessed_at`/`updated_at`. Three optional `w_semantic/w_keyword/w_recency` params re-normalise to 1.0. Per-signal sub-scores exposed for debugging + agent-side re-ranking. (#481)
- `summarize_context` synthesises memories via MCP Sampling — the client's own model produces the briefing, with a deterministic concat fallback for clients that don't support sampling. (#448)
- New `redact_memory(key, reason=None)` tool tombstones a value while preserving the record: sets `Memory.redacted_at`, replaces value with `__redacted__`, writes the pre-redaction value to the audit log. `recall` on a redacted memory returns a sentinel; `list_memories` + `search_memories` skip redacted items by default (opt-in via `include_redacted`). (#400)
- `Memory.recall_count` + `last_accessed_at` — bumped atomically on every successful `recall`; surfaced on list/search results for ranking, dashboards, and memory-decay scoring. (#394)

#### Compliance & observability

- `log_audit_event` is now called from every memory-touching tool, producing an immutable `AUDIT#` trail separate from the user-visible activity log. Audit items carry a DynamoDB TTL (`HIVE_AUDIT_RETENTION_DAYS`, default 365) and a new `GET /api/admin/audit-log` endpoint exposes them with `client_id` / `event_type` / date-range filters. (#395)
- `POST /api/csp-report` receives browser CSP violation reports (both legacy `application/csp-report` and modern `application/reports+json`), logs them structured to CloudWatch, and emits a `CSPViolations` EMF metric (aggregate + per-directive drill-down). Unauthenticated by design; per-IP rate-limited. Admin dashboard gets a "Security" section showing the count. (#488)

#### Dev experience & CI

- Release Drafter keeps a draft GitHub release current as PRs merge into `development`, grouped by category label — no more hand-maintained `[Unreleased]`. Label-check workflow now requires a category label on every linked issue. (#420)
- `release-milestone-watcher` workflow opens a "Release: cut vX.Y" tracking issue when any `vX.Y` milestone drains to zero open non-epic issues. Pairs with the in-session stop condition. (#484, #512)

### Meta

- CLAUDE.md: design-review workflow + product-decision section. (#506)
- CLAUDE.md: milestone preference added to the issue selection algorithm. (#514)

## v0.21.0 — 2026-04-18

## v0.21.0 — 2026-04-18

### Added

#### MCP surface

- New `ping` tool for connectivity and auth health checks (#411)
- New `list_tags` tool for tag-space discovery (#415)
- New `relate_memories(key, top_k)` tool — semantic traversal from a memory to its nearest neighbours (#465)
- New `remember_if_absent(key, value, tags?, ttl_seconds?)` — conditional write only when the key doesn't already exist (#466)
- `search_memories` gained `min_score` (score threshold) and `filter_tags` (tag-intersection filter) parameters (#412, #444)
- `remember` enforces a UTF-8 byte-size cap on `value` (default 10 KB, configurable via `HIVE_MAX_VALUE_BYTES`) (#403)
- Every tool now advertises title + `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` so capable clients can auto-approve read-only calls and confirm destructive ones (#469)
- `list_memories` and `search_memories` responses now include `owner_client_id`; the memory browser renders a "by {client name}" attribution badge on every card (#463)

#### Compliance & privacy

- GDPR Article 20 / CCPA §1798.100 data export: `GET /api/account/export` streams a JSON bundle with the user's profile, memories, OAuth clients, and the last 90 days of activity; rate-limited to one export per 5 min (#468)
- Opt-in GA4 cookie consent banner — no tracking script loads until the visitor clicks Accept; choice persisted in `localStorage`, revocable via a footer "Cookie preferences" link (#467)
- New `/subprocessors` page listing AWS, Google OAuth, and Google Analytics with purpose, data categories, and location; cross-linked from Privacy §4 and the FAQ (#470)

#### Infrastructure, security, & observability

- CloudFront response-headers policy: HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and a `Content-Security-Policy-Report-Only` draft; enforcing CSP tracked separately (#473)
- New CloudWatch alarms: Lambda throttles (MCP + API), DynamoDB user errors, and Bearer-token auth failures; every prod alarm now pages both on firing and on recovery (OK actions); first-deploy runbook documents the SNS subscription flow (#474)
- Backup / restore runbook for prod DynamoDB PITR recovery — when-to, pre-flight, restore, swap, validation, cleanup, post-mortem template, and annual drill guidance (#478)
- SEO: `robots.txt` + `sitemap.xml` for marketing SPA + VitePress-generated docs sitemap (#443)
- Open Graph + Twitter Card metadata across marketing and docs pages so shared links render proper preview cards (#455)

#### Dev experience & CI

- Key-naming conventions docs page with the recommended `{domain}:{entity-type}/{entity-id}:{attribute}` pattern and examples (#408)
- `main`-branch guard: PRs to `main` from anything other than `development` or `release/*` fail a required status check, preventing another v0.20.0-style release-bypass (#477)
- Dependabot now runs daily for pip and npm (github-actions stays weekly) and passing Dependabot PRs auto-merge (#432, #445)
- ChatGPT joins the supported-clients list everywhere; Claude Desktop setup now leads with the Custom Connector URL flow (mcp-remote JSON kept as a legacy fallback) (#485)

### Fixed

- Pricing page claimed "unlimited memories" while the free-tier quota is 500 (#404)
- Privacy Policy / Terms referenced `privacy@hive.so` and `hello@hive.so` on a domain we don't own; switched to `@warlordofmars.net` (#431)
- Marketing home page's "3-step setup" described a flow that doesn't exist ("register a client", "one-line snippet"); rewritten to match `SetupPanel` and the docs, including the browser-OAuth step (#471)

### Meta

- CLAUDE.md: deterministic selection algorithm for the autonomous issue queue (#461)
- CLAUDE.md: label taxonomy (status / priority / size / area) and milestone policy; enforced at PR merge via `label-check.yml` (#462, #464)
- CLAUDE.md: autonomous agent halts and surfaces `HUMAN_INPUT_REQUIRED` when the active release milestone drains (#483)
- CHANGELOG: retroactive v0.20.0 entry documenting what actually shipped there (#476)

## v0.20.0 — 2026-04-17

> **Note**: v0.20.0 was cut from a single PR that bypassed the normal release-branch workflow. The intended scope of this milestone (compliance work, accuracy audit, MCP annotations, etc.) was merged to `development` after the tag was already pushed and will ship in v0.21.0. This entry documents what actually shipped in v0.20.0. See #475 for the branch-protection follow-up to prevent this recurring.

### Added

- Terms of Service and Privacy Policy marketing pages (#401)

## v0.19.1 — 2026-04-13

### Fixed

- Omit `client_secret` from DCR response for public clients — `mcp-remote` Zod schema rejected `null` value, breaking Claude Desktop connections (#373)
- MCP auth: `Meta.get()` error and missing HTTP 401 for OAuth clients (#371, #372)
- E2e tests: accept HTTP 401 as valid auth rejection (#375)

## v0.19.0 — 2026-04-12

### Added

- Python and JavaScript client SDKs (#349)
- API key authentication (`hive_sk_` tokens) for programmatic access without OAuth (#339)
- Memory versioning — previous values preserved on overwrite (#342)
- Per-memory TTL at creation time (#341)
- Bulk memory operations: `forget_all`, `export`, `import` (#340)
- Per-user usage quotas for free tier (#333)
- Per-client rate limiting with 429 + Retry-After (#331)
- GDPR account deletion via `DELETE /api/account` (#330)
- OpenAPI/Swagger UI on management API (#329)
- Responsive mobile layout for management UI (#337)
- Improved UsersPanel: pagination, search, and user detail (#338)
- Migrated UI to shadcn/ui component library (#334)
- SLO error budget burn rate alarms and CloudWatch dashboard (#346)
- WAF enabled on dev environment (#344)
- Lambda provisioned concurrency for MCP function in prod (#351)
- Slack notifications for CI/CD pipeline events (#350)
- Weekly DynamoDB PITR backup restore test (#348)
- E2e tests for cost data in admin dashboard (#345)
- Hardened repo against malicious contributions (#343)

### Fixed

- Sign in button border not visible in marketing site navbar (#327, #332)
- Orange active indicator missing from Docs nav link on docs site (#326)
- Dashboard chart x-axis labels cut off (#328)
- E2e race conditions in memory creation and tag filter tests (#335, #336)
- Dashboard e2e cost section assertions (#345, #347, #352, #353)

### Chore

- CLAUDE.md autonomous issue workflow guidelines (#324, #325)

## v0.18.0 — 2026-04-11

### Added

- Live CloudWatch log viewer in admin UI: group/window/filter controls, level badge toggles, expandable rows, 10 s polling with pause/resume (#291, #295, #296, #297, #298)
- Tag picker with autocomplete suggestions for memory filter in MemoryBrowser (#292)
- Relative timestamps on Dashboard last-refreshed indicator (#294)
- Keyboard navigation for memory card list (Arrow keys, Enter, Escape) (#294)

### Fixed

- Docs site visual design unified with marketing site navbar (#289)
- Accessibility and JS quality improvements across admin UI (#288)
- Conditional hooks and chart legend overlap in AppShell/Dashboard (#285)
- Empty state guard for unauthenticated AppShell renders (#286)

## v0.17.1 — 2026-04-10

### Fixed

- Pass `VITE_GA_MEASUREMENT_ID` to `inv deploy` steps so GA4 tag is correctly substituted in deployed `index.html` (#243)

## v0.17.0 — 2026-04-09

### Added

- Google Analytics 4 integration: `page_view` on route changes, `tab_view` on app tab switches, `cta_click` on "Get started" buttons (#240)
- GA4 is disabled in local dev and when `VITE_GA_MEASUREMENT_ID` is unset — no tracking in development

## v0.16.1 — 2026-04-08

### Fixed

- Upgrade `cryptography` 46.0.6 → 46.0.7 to address CVE-2026-39892 (#237)

## v0.16.0 — 2026-04-08

### Added

- Marketing site expanded with Pricing, FAQ, Use Cases, MCP Client Compatibility, Changelog, and Status pages (#231, #232, #234)
- Shared `PageLayout` component with consistent header/footer nav across all marketing pages (#231)
- `ChangelogPage` parses `CHANGELOG.md` at build time and renders versioned sections with color-coded change groups (#234)
- `StatusPage` performs a live health check against `GET /health` with refresh and checked-at time display (#234)
- shadcn/ui component foundation with Tailwind v4 design tokens matching VitePress docs site branding (#228)

### Fixed

- Tailwind utility classes (`mx-auto`) overridden by unlayered CSS reset — moved reset into `@layer base` (#229)
- Flash of light background on dark-mode page load — synchronous inline theme script applied before first paint (#230)
- E2e mobile menu toggle test replaced fixed 300ms wait with condition-based `wait_for` (#235)

## v0.15.0 — 2026-04-07

### Added

- VitePress user-facing documentation site hosted at `/docs` (#201)
- CloudFront routing for `/docs/*` with clean URL rewriting — VitePress `cleanUrls` output served correctly without trailing-slash issues (#201, #204, #205)
- Docs site themed to match marketing site: dark navy navbar, orange accent, Hive logo/favicon (#203, #207, #220)
- Docs navbar with Docs and Sign in links rendered as plain `<a>` elements (bypasses Vue Router so navigation works correctly across site boundaries) (#209, #210, #213, #214, #221, #222)
- `/docs` and `/docs/` redirect to `what-is-hive` first doc page (#215)
- Playwright e2e test suite for docs site: routing, navbar appearance, nav link clicks, logo/Sign in navigation, mobile hamburger (#204, #209, #210, #211, #213, #214, #221, #222)

### Fixed

- Dark mode toggle and GitHub icon removed from docs navbar (#223, #224)
- Logo navigates to marketing page root (Vue Router SPA interception bypassed) (#213)
- Sign in button positioned at far right of navbar next to Docs link (#222)

## v0.14.0 — 2026-04-06

### Added

- Semantic memory search via Amazon S3 Vectors + Bedrock Titan Embeddings V2 — new `search_memories` MCP tool and `GET /api/memories?search=` API endpoint return memories ranked by cosine similarity (#193, #194)
- Debounced semantic search input in Memory Browser UI with match score badges (#193, #194)

### Fixed

- SetupPanel tab and JSON panel colors were hardcoded light-mode values and did not render correctly in dark mode (#196)

## v0.13.1 — 2026-04-06

### Fixed

- LoginPage tagline still referenced "Claude agents" after #184 — updated to "AI agents" (#188)

## v0.13.0 — 2026-04-06

### Added

- Scheduled synthetic traffic workflow generating real CloudWatch metrics every 15 minutes (#154)
- E2E tests for CloudWatch metrics dashboard, including admin API and UI validation (#157)
- Dark mode support with OS preference detection and manual toggle; CSS design tokens via Tailwind v4 (#175)
- Visual identity — logo, favicon, and social preview image (#173)
- Make Google auth bypass conditional on `test_email` param for safer e2e testing (#170, #171)

### Fixed

- MCP client setup instructions for Claude Desktop and Claude Code (#169)
- Marketing page layout: logo, wordmark, 2×2 feature grid, consistent 1100px content width (#178–#181)
- Dark mode applied to all routes (LoginPage, HomePage) via `useTheme` at App root (#182, #183)

### Changed

- Broadened messaging from Claude-specific to MCP-compatible; added Cursor and Continue setup docs and onboarding snippets (#184)

## Earlier releases

See [GitHub releases](https://github.com/warlordofmars/hive/releases) for the full history.
