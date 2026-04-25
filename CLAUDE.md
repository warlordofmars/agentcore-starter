# AgentCore Starter

A starter template for AWS-native AI agent backend services.
Built with FastAPI (Python), DynamoDB, AWS CDK, and a React management UI.

> **Naming disambiguation**: this template is named after a product family,
> not the AWS Bedrock AgentCore service. The inline-agent wrapper lives at
> `agents/inline_agent.py`; AgentCore Runtime, Memory, and Gateway are not
> currently integrated. See issue #17 for the feasibility spike on
> integrating them.

## Stack

- FastAPI (Python) — OAuth 2.1 authorization server + management REST API
- React (Vite) + shadcn/ui — management UI SPA
- DynamoDB — persistent storage (single table design)
- AWS Lambda + Function URL — hosting
- AWS CDK (Python) — IaC
- IAM roles — Lambda <-> DynamoDB auth
- Google OAuth — identity provider for management UI login
- uv — dependency management (pyproject.toml + uv.lock)

## Structure

```text
agentcore-starter/
├── src/
│   └── starter/
│       ├── storage.py         # DynamoDB read/write logic
│       ├── models.py          # Data models
│       ├── logging_config.py  # Structured JSON logging setup
│       ├── metrics.py         # CloudWatch EMF metrics helpers
│       ├── auth/
│       │   ├── oauth.py       # OAuth 2.1 authorization server
│       │   ├── dcr.py         # Dynamic Client Registration (RFC 7591)
│       │   ├── tokens.py      # Token issuance + validation
│       │   ├── google.py      # Google OAuth integration
│       │   └── mgmt_auth.py   # Management API authentication
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── bedrock.py     # Converse + converse_stream (raw Bedrock)
│       │   └── inline_agent.py # invoke + invoke_stream (Bedrock inline agent)
│       └── api/
│           ├── main.py        # FastAPI app + routes
│           ├── admin.py       # Admin-only endpoints
│           ├── agents.py      # Agent scaffold endpoints
│           └── users.py       # User management endpoints
├── ui/
│   ├── src/
│   │   ├── App.jsx            # Router, AppShell, tab nav
│   │   ├── api.js             # API client (fetch wrappers)
│   │   ├── analytics.js       # GA4 trackPageView + trackEvent helpers
│   │   ├── hooks/
│   │   │   └── useTheme.js    # Dark/light theme hook
│   │   ├── lib/
│   │   │   └── utils.js       # Shared utility functions (cn, etc.)
│   │   └── components/
│   │       ├── ui/
│   │       │   └── button.jsx # shadcn/ui Button primitive
│   │       ├── Dashboard.jsx  # Admin: CloudWatch metrics + cost data
│   │       ├── UsersPanel.jsx # Admin: user list + management
│   │       ├── EmptyState.jsx # Shared empty-state illustrations
│   │       ├── PageLayout.jsx # Shared page layout + navbar
│   │       ├── AuthCallback.jsx
│   │       └── LoginPage.jsx
│   └── package.json
├── docs-site/                 # VitePress documentation site
│   ├── .vitepress/
│   │   ├── config.mjs         # base: "/docs/", nav, sidebar
│   │   └── theme/
│   │       ├── index.js       # Custom Layout (nav-bar-content-after slot)
│   │       └── style.css      # Dark navy navbar, brand colours
│   └── getting-started/       # Introduction and quick-start
├── infra/
│   ├── app.py                 # CDK app entry point
│   └── stacks/
│       └── starter_stack.py   # Lambda + DynamoDB + CloudFront + IAM
├── tests/
│   ├── unit/                  # Pure logic, no AWS deps
│   ├── integration/           # Tests against DynamoDB Local
│   └── e2e/                   # Playwright tests against deployed env
│       ├── test_auth_e2e.py
│       └── test_ui_e2e.py     # Admin UI (Playwright)
├── scripts/
│   └── check_copyright.py     # Copyright header linter
├── .github/
│   └── workflows/
│       ├── ci.yml             # CI on PRs + deploy on push to dev/main
│       ├── deploy-dev.yml     # Manual dev deploy (workflow_dispatch)
│       └── security.yml       # Scheduled security scans
├── tasks.py                   # Invoke task definitions (lint, test, deploy)
├── pyproject.toml
└── README.md
```

## Auth

- OAuth 2.1 authorization server built into AgentCore Starter (self-contained)
- Dynamic Client Registration per RFC 7591 (required by MCP spec)
- PKCE required on all authorization code flows
- Tokens stored in DynamoDB with TTL
- All API endpoints require a valid Bearer token
- Management UI login via Google OAuth (`/auth/login`)

## DynamoDB single table design

- OAuth client items: `PK=CLIENT#{client_id}`, `SK=META`
- Token items: `PK=TOKEN#{jti}`, `SK=META` (TTL enabled)
- Activity log items: `PK=LOG#{date}#{hour}`, `SK={timestamp}#{event_id}`
  (hour-sharded to avoid hot partitions)
- Audit log items: `PK=AUDIT#{date}#{hour}`, `SK={timestamp}#{event_id}`
  (immutable compliance trail, TTL via `STARTER_AUDIT_RETENTION_DAYS`,
  default 365 days)
- User items: `PK=USER#{user_id}`, `SK=META`
- Mgmt state items: `PK=MGMT_STATE#{state}`, `SK=META`
  (TTL enabled, used for OAuth state parameter)
- GSIs:
  - `ClientIdIndex` — `GSI3PK=CLIENT#{client_id}` (for client lookups)
  - `UserEmailIndex` — `PK=EMAIL#{email}` (for user lookups by email)

## Management UI

- React SPA (Vite), runs on port 5173 in dev
- Communicates with FastAPI management API on port 8001
- Features:
  - Admin only: user management (`UsersPanel`), metrics dashboard (`Dashboard`)
- Auth: Google OAuth via `/auth/login`;
  token stored in localStorage as `starter_mgmt_token`
- Tab set: Users, Dashboard (admin only)

## Docs site

- VitePress with `base: "/docs/"` — served at `<domain>/docs/`
- CloudFront Function rewrites clean URLs (no extension → `.html`)
- Nav links injected via `nav-bar-content-after` layout slot as plain `<a>`
  elements (not Vue Router links) so Vue Router never intercepts
  marketing-site clicks
- Deployed to S3 prefix `docs/` alongside the React SPA in the same bucket
- `DeployUi` CDK construct uses `prune=False` — never delete docs assets
- `DeployDocs` depends on `DeployUi` so docs always win on final write order

## Testing

- pytest for all Python tests (unit, integration, e2e)
- DynamoDB Local (Docker) for integration tests
- Playwright for UI e2e tests
- Unit tests: no AWS deps, fully mocked
- Integration tests: run against DynamoDB Local
- E2e tests: run against deployed AWS dev environment
- **100% coverage required** — both Python (pytest-cov) and JS (vitest v8);
  CI fails below 100%
- Every new UI component needs a co-located `*.test.jsx` file

### E2e test conventions

- Use a unique tag per test run (e.g. `e2e-{timestamp}`) when creating test
  data, then filter by that tag to assert — avoids pagination issues from
  accumulated test data
- When selecting one element among many sharing a class, use Playwright
  `has_text=` (e.g. `page.locator(".docs-nav-link", has_text="Docs")`)
  to avoid strict-mode violations

## CI/CD (GitHub Actions)

`ci.yml` runs on every PR and push to `development` or `main`:

- Lint (ruff) + type check (mypy) + copyright headers
- Unit tests + integration tests (DynamoDB Local) + combined coverage report
- Frontend tests (vitest) + build; coverage uploaded to Codecov
- Docs site build
- Infra synth + Trivy IaC scan (CloudFormation SARIF → GitHub Security tab)
- Trivy dependency audit (SARIF → GitHub Security tab)
- SonarCloud scan
- On push to `development`: deploy to dev + run all e2e tests
- On push to `main`: release + deploy to prod + back-merge to development

Other workflows:

- `deploy-dev.yml` — manual dev deploy via `workflow_dispatch`
- `security.yml` — scheduled security scans
- `synthetic-traffic.yml` — scheduled synthetic load against dev environment

Deploy order: React SPA → docs site (docs depend on SPA deployment completing
first).

## Conventions

- Use uv for all dependency management — never pip or requirements.txt
- Management API on port 8001, UI on port 5173
- All infra in CDK (Python) under `infra/`
- All config via environment variables
- Never hardcode credentials or secrets
- AWS credentials in GitHub Actions via OIDC (no long-lived access keys)
- Pin third-party GitHub Actions to full commit SHAs, not mutable version tags
  (e.g. `uses: actions/checkout@<sha> # v4`); use
  `gh api repos/{owner}/{repo}/git/ref/tags/{tag}` to resolve SHAs

## Product decisions

Durable architectural choices that constrain future designs. Don't
re-derive these during design review — cite them.

- **Workspaces are the tenancy root** — any multi-tenancy feature
  consumes the workspace model. Don't invent a second tenancy axis
  (per-user, per-client-group, etc.) without explicit design review.
- **Billing deferred** — ship features free. Do not design tier
  abstractions, per-seat accounting, or billing gates until billing is
  an active constraint. Keep the concept out of data models for as long
  as possible.
- **Client-side LLM preferred** — features needing an LLM (extraction,
  classification, synthesis) use MCP Sampling. Don't add
  Bedrock / OpenAI dependencies when the MCP client can provide the model.
- **Shared-infra features ship full scope** — when two capabilities share
  ~80% of the infrastructure, ship them together in one release.
  Splitting a shared-infra pair doubles release cost for marginal benefit.
- **Agents swap tokens to switch context** — don't design tool APIs that
  take a `workspace_id` / `namespace` param on every call. Scope comes
  from the token claim; agents register a new DCR client per context and
  swap tokens to switch.
- **Agent session IDs are user-namespaced** — the `inline_agent.py` wrapper
  computes the Bedrock `sessionId` as `f"{jwt_sub}:{caller_session_id}"`.
  Callers supply their own opaque `session_id`; the wrapper adds the user
  prefix so sessions never bleed across users. The namespaced form is
  internal — only the caller's `session_id` is echoed back in responses.

## UI conventions

- **CSS variables only** — never hardcode colours; use `var(--text-muted)`,
  `var(--border)`, `var(--accent)`, `var(--danger)`, `var(--success)`, etc.
  for dark-mode compatibility
- **Lucide icons** — use `lucide-react` for all icons; never use emojis as
  UI elements
- **shadcn/ui primitives** — prefer shadcn components (Button, etc.) over
  custom HTML; add new primitives to `ui/src/components/ui/` as needed
- **jsdom colour normalisation** — in vitest, jsdom converts hex to
  `rgb(r, g, b)`; assert `"rgb(232, 160, 32)"` not `"#e8a020"`
- **Anonymous inline functions** — vitest v8 counts uncovered anonymous
  functions; extract or name handlers that must be tested (e.g. event
  listeners in `useEffect`)
- **`vi.useFakeTimers()`** — activate **before** `render(...)` when the
  timer is scheduled in the component's mount `useEffect` (the common
  case — see `ui/src/components/Dashboard.test.jsx:363-370`); activating
  after mount leaves the timer pinned to the real clock. Activate
  *after* the initial render only when the render itself awaits a
  fake-able timer (rare). vitest 1.x's default `toFake` set excludes
  microtasks, so promise resolution is unaffected. Always pair with
  `vi.useRealTimers()` in a matching cleanup. See
  `.claude/skills/react-component/SKILL.md` §5.2 for the full pattern.

## Copyright headers

All source files must carry a copyright header. Current year is 2026.

New Python files:

```python
# Copyright (c) 2026 John Carter. All rights reserved.
```

New JS/JSX files:

```js
// Copyright (c) 2026 John Carter. All rights reserved.
```

When editing a file in a new year, append that year to the existing line
(e.g. editing in 2027 → `# Copyright (c) 2026, 2027 John Carter.
All rights reserved.`).

## PR workflow

### Opening a PR

1. Always branch off `origin/development`, never off another feature branch:

   ```bash
   git fetch origin
   git checkout -b fix/my-fix origin/development
   ```

2. Before `gh pr create`, rebase and verify clean history:

   ```bash
   git fetch origin
   git rebase origin/development
   git push --force-with-lease
   git log --oneline origin/development..HEAD  # must show ONLY your commits
   ```

3. Every PR body must include `Closes #NNN` linking to the GitHub issue.

4. Validate locally before pushing (same gate as CI):

   ```bash
   uv run inv pre-push        # lint + typecheck + unit tests + frontend tests
   uv run inv deploy --env jc # deploy to personal AWS env
   uv run inv e2e --env jc    # e2e tests against that env
   ```

5. After pushing, watch CI (`gh run watch`) and fix any failures immediately.

### Merge strategy

`gh pr create` doesn't support a merge-strategy flag — but immediately
enabling auto-merge after creating the PR pre-configures the strategy so
it fires automatically once CI passes:

```bash
# feature/fix → development  (squash)
gh pr create --base development ...
gh pr merge --auto --squash --delete-branch

# development → main  (merge commit)
gh pr create --base main ...
gh pr merge --auto --merge
```

| PR direction | Strategy | Why |
| --- | --- | --- |
| feature/fix → `development` | **Squash** | One clean commit per feature |
| `development` → `main` | **Merge commit** | Preserves squashed history |
| `main` → `development` (back-merge) | **Merge commit** | Handled by CI automatically |

### Releasing to production

1. **Create a release branch off `development`:**

   ```bash
   git fetch origin
   git checkout -b release/vX.Y.Z origin/development
   ```

2. **Pick the version number from the drained milestone, not from
   Release Drafter.** The milestone title (`vX.Y`) is the commitment;
   Release Drafter's draft often auto-labels the next patch (e.g.
   `v0.22.1`) because it bumps from the last published tag regardless
   of scope. If the milestone says `v0.23`, the release is `v0.23.0`.

3. **Update `CHANGELOG.md`** — move items from `[Unreleased]` into a
   new `## vX.Y.Z — YYYY-MM-DD` section **curated into
   `Added / Changed / Fixed / Meta` subsections** matching the prior
   releases in the file. The **draft release auto-maintained by
   Release Drafter** (see the releases page in this repo) is the
   what-landed source of truth — don't re-derive from PR history —
   but the Drafter body is a flat bulleted list of PR titles; do
   **not** paste it verbatim. Group related PRs, write 1–2
   descriptive sentences per bullet explaining *what changed and
   why*, and cite the PRs in parentheses. Do **not** add a
   `**Full Changelog:** https://github.com/…/compare/…` link at the
   bottom — CHANGELOG.md is a local artefact, not a GitHub release
   note; the prior sections don't carry compare links either. Compare
   the prior versioned section (`v0.22.0`) for the exact tone and
   subsection structure. Commit the change:

   ```bash
   git add CHANGELOG.md
   git commit -m "chore: prepare release vX.Y.Z"
   git push -u origin release/vX.Y.Z
   ```

4. **Open a PR** from `release/vX.Y.Z` → `main`:

   ```bash
   gh pr create --base main --title "release: vX.Y.Z" \
     --body "Release vX.Y.Z. See CHANGELOG for details."
   ```

5. **Merge with `--merge`** (not squash) once CI passes:

   ```bash
   gh pr merge NNN --merge --delete-branch
   ```

6. **CI takes over** — on merge to `main`, the pipeline automatically:
   - Creates the GitHub release + tag
   - Deploys to prod
   - Back-merges `main` → `development`

   **Never run `gh release create` manually** — the pipeline owns this.

## Running the full stack locally

```bash
# 1. Start all services (DynamoDB Local, API, Vite dev server)
#    Add --seed to also seed demo data automatically once the API is ready
uv run inv dev [--seed]
```

`inv dev` sets automatically:

- `CORS_ORIGINS` — `localhost:5173` through `localhost:5179` (handles port
  collisions if 5173 is already taken by another project)
- `STARTER_BYPASS_GOOGLE_AUTH=1` — enables the `?test_email=` auth shortcut
  (only activates when that query param is present; normal browser flows
  are unaffected)

```bash
# 2. Seed DynamoDB with demo data (also creates the table) — if not using --seed
uv run inv seed
```

Must be re-run after every `inv dev` restart (DynamoDB Local is ephemeral).

### Running UI e2e tests locally

```bash
# Auto-detects the Vite port — no env vars to set manually
uv run inv e2e-local

# Run a specific test file
uv run inv e2e-local --tests tests/e2e/test_ui_e2e.py

# Repeat N times to check for flakiness
uv run inv e2e-local --n 5
```

`inv e2e-local` probes ports 5173–5179 for the AgentCore Starter Vite dev server (via
`/auth/login?test_email=probe`) and passes the detected URL as `STARTER_UI_URL`.

Key local e2e gotchas:

- The Vite proxy handles `/auth`, `/api`, `/oauth`, `/mcp` — tests must use
  the Vite URL (not the API URL directly) so the auth bypass sets
  `localStorage` at the correct origin.
- If Vite lands on a port other than 5173, `CORS_ORIGINS` must include that
  port. `inv dev` covers 5173–5179; if you're outside that range, pass
  `CORS_ORIGINS=http://localhost:<port>` when starting the stack.
- `inv seed` (or `inv dev --seed`) must succeed before running e2e tests —
  if auth bypass returns 500, the table is likely missing.
- `test_docs_e2e.py` is excluded automatically — those tests require a
  deployed VitePress build; run them against the deployed stack with `inv e2e`.

### When to run local e2e tests

Not required on every PR — `uv run inv pre-push` (unit + frontend tests) is
the standard gate. Run `inv e2e-local` before opening a PR when the change
touches any of the following:

**Always required:**

- Fixing a failing e2e test — the fix must pass locally before the PR opens
- Auth flows (`auth/`, `AuthCallback.jsx`, `LoginPage.jsx`, OAuth endpoints)
- Management API endpoints (`api/`) that the UI tests exercise

**Use judgement (run the relevant `--tests` file at minimum):**

- UI component changes that affect user-visible flows
- Vite proxy config or API base URL changes

**Not needed:**

- Pure unit test fixes, documentation, infra/CDK changes, style/CSS tweaks,
  or any change fully covered by unit + frontend tests

## Pre-PR checklist (required before every push)

Run `uv run inv pre-push` — this runs the same gate as CI:

1. `inv lint-backend` — ruff lint + format check
2. `inv typecheck` — mypy
3. `inv test-unit` — pytest unit tests
4. `inv test-frontend` — vitest

This is enforced automatically if you install the git hook:
`uv run inv install-hooks`

If infra files changed, also run: `uv run inv synth`

---

## Agent workflows

Three agents handle the structured issue workflows. They live in `.claude/agents/` and load automatically.

- **`orchestrator`** — sequences in-flight work across specialist agents: reads live repo state, resolves directives (`status`, `work next <filter>`, `delegate <#N> to <agent>`, `check #N`, `brief #N`, `epic #N`), delegates, and halts on unresolved blockers or tracked template-bootstrap gaps. Design rationale: `docs/adr/0005-orchestrator-agent.md`.
- **`issue-worker`** — autonomous issue cycle: pick → implement → PR → CI → Copilot review → post-merge pipeline watch. Invoke by asking Claude to work through issues, or with `@"issue-worker (agent)"`.
- **`design-review`** — processes `status:design-needed` issues interactively: triage, decisions comment, label flip, sub-issue breakdown for epics.

---

## Autonomous issue workflow

Full protocol lives in `.claude/agents/issue-worker.md`. Summary of invariants that apply even outside the agent:

- Never push directly to `development` or `main`
- Never merge a PR manually — auto-merge handles this
- Never run `gh release create` — CI owns releases
- Never hardcode credentials, secrets, or AWS account IDs
- Never use `pip` or `requirements.txt` — always use `uv`
- Never skip `inv pre-push` before creating a PR
- Never pin GitHub Actions to mutable version tags — use full commit SHAs

## Backlog labels and milestones

Every open implementation issue must carry status + priority + size + area labels.
This section defines the taxonomy.

### Status (one, required)

- `status:ready` — fully scoped, no blockers, queue-eligible
- `status:blocked` — depends on another **open issue in this repo**;
  body must name the blocker with `Blocked by #N`. Not queue-eligible.
- `status:needs-info` — waiting on **off-platform info** (billing,
  account state, external service verification, legal review). Distinct
  from `blocked` — the resolution isn't in this repo. Not queue-eligible.
- `status:design-needed` — not yet reviewed; needs a design pass per
  §Design-review workflow. Not queue-eligible.

### Priority (one, required)

- `priority:p0` — compliance, security, or outage-adjacent; ship this week
- `priority:p1` — ship this quarter
- `priority:p2` — ship eventually; useful but not urgent
- `priority:p3` — someday-maybe

### Size (one, required)

- `size:xs` — less than 1 hour
- `size:s` — half a day
- `size:m` — 1–2 days
- `size:l` — 3–5 days
- `size:xl` — a week or more; must be broken down before the agent picks
  it up

### Area (one or more, required)

`ui`, `ux`, `a11y`, `api`, `mcp`, `auth`, `infra`, `ci`, `dx`, `sdk`,
`security`, `compliance`, `docs`, `design`, `performance`, `observability`,
`marketing`, `seo`, `growth`, `ops`, `reliability`.

### Special labels

- `epic` — tracking issue with sub-issue checklist; never queue-eligible
- `bug` / `enhancement` / `chore` — issue type
- `agent-safe` — PR from this issue can be merged **autonomously by
  the agent** after the §7.5 Copilot review + CI pass. Apply when the
  work is low-risk enough that an LLM reviewer's feedback is
  sufficient without a human final look: `priority:p2` / `p3`,
  `size:xs` / `s` / `m`, and not touching `infra/stacks/starter_stack.py`,
  `.github/workflows/`, or any auth / token-issuance path. Without
  this label, the agent still runs Copilot review (everyone benefits
  from a second opinion) but then stops for human merge.

### Issue creation rules

When filing a new issue:

1. Use the GitHub issue template (defaults to `status:ready`)
2. Add a `priority:*` label and a `size:*` label before leaving the page
3. Add at least one area label
4. If the issue is part of an existing epic, add `Part of #NNN` to the
   body so the epic's checklist stays linked
5. If the issue depends on another, add `Blocked by #NNN` to the body and
   apply `status:blocked`

The `label-check.yml` workflow enforces status + priority + size at PR
merge time for any PR that contains `Closes #NNN`.

### Milestones

Keep **three** active milestones at any time — no more:

1. **Current release** (e.g. `v0.20`) — what ships next
2. **Themed hardening bucket** (e.g. `MVP-hardening`) — ship-blocking work
   that's too large for the current release
3. **`Backlog`** — accepted but unscheduled p2/p3 work

Epics are **not** milestoned — they span multiple releases.

Do not create future release milestones in advance; they become stockpiles
and degrade the "what's next" signal. When the current release closes,
create the next one and promote items from the hardening bucket.

### Triage cadence (human, not agent)

- **Weekly** — glance at issues created in the last 7 days; fix any
  missing priority / size / area labels
- **Monthly** — review the hardening bucket and promote shippable items
  into the current release
- **Quarterly** — review `priority:p3` and `status:design-needed` issues;
  promote, rescope, or close. Don't let them rot