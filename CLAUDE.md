# AgentCore Starter

A starter template for AWS-native AI agent backend services.
Built with FastAPI (Python), DynamoDB, AWS CDK, and a React management UI.

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
│       └── api/
│           ├── main.py        # FastAPI app + routes
│           ├── admin.py       # Admin-only endpoints
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
- MCP server on port 8000, management API on port 8001, UI on port 5173
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

- **Workspaces are the tenancy root** (#482) — any multi-tenancy feature
  consumes the workspace model. Don't invent a second tenancy axis
  (per-user, per-client-group, etc.) without explicit design review.
- **Billing deferred** — ship features free. Do not design tier
  abstractions, per-seat accounting, or billing gates until billing is
  an active constraint. Keep the concept out of data models for as long
  as possible.
- **Client-side LLM preferred** — features needing an LLM (extraction,
  classification, synthesis) use MCP Sampling (#448). Don't add
  Bedrock / OpenAI dependencies when the MCP client can provide the model.
- **Shared-infra features ship full scope** — when two capabilities share
  ~80% of the infrastructure (e.g. text-large + binary memory in #451,
  webhook + SSE + MCP notification in #392), ship them together in one
  release. Splitting a shared-infra pair doubles release cost for
  marginal benefit.
- **Agents swap tokens to switch context** — don't design tool APIs that
  take a `workspace_id` / `namespace` param on every call. Scope comes
  from the token claim (`workspace_id`, `conversation_id` where
  applicable); agents register a new DCR client per context and swap
  tokens to switch.

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
- **`vi.useFakeTimers()`** — activate only *after* the initial async render
  completes (`await waitFor(...)`) otherwise fake timers block promise
  resolution

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

## Design-review workflow

Governs how to process `status:design-needed` issues. Distinct from the
autonomous issue workflow below — design review is **interactive**
(requires user decisions), not unattended.

### Pre-flight triage

Before starting a design review, apply scope triage:

1. **Redundant?** If another open issue or recently-landed feature
   already covers the same use case with a broader surface, close as
   redundant (see §Closing as redundant) rather than reviewing.
2. **`priority:p3` + `size:xl`?** Park — keep the `status:design-needed`
   label, skip the review. These rarely pay off soon and design effort
   decays.
3. **Everything else** — proceed to the 3-phase review.

### Phase 1 — decisions comment

Post a structured comment on the issue with this skeleton:

```markdown
## Design decisions

### Resolved

1. **<question>** — <answer> — <one-line rationale>
2. ...

### Derived decisions

- <consequence that follows from the resolved answers>
- ...

### Breakdown (only if size:xl)

This issue is `size:xl` and will be delivered via the sub-issues linked
below. This issue stays open as the epic tracker.
```

Every open design question from the issue body must be addressed —
either **resolved** (a decision is made and recorded) or **flagged**
(marked as needing user input, which pauses the review).

### Phase 2 — label flip

Apply the correct status label based on the outcome:

| Outcome | Label |
|---|---|
| Fully specified, no external blockers | `status:ready` |
| Depends on another open issue in this repo | `status:blocked` (body must include `Blocked by #N`) |
| Waiting on off-platform info (billing, account, external service) | `status:needs-info` |

For `size:xl` issues that have been design-approved, also add the `epic`
label so the autonomous loop never picks up the tracker itself.

### Phase 3 — sub-issue breakdown (only if size:xl)

For epics:

1. Create one sub-issue per deliverable unit (typically 5–8 sub-issues)
2. Each sub-issue body starts with `Part of #<epic>` and lists any
   `Blocked by #N` cross-sub-issue dependencies
3. Link each sub-issue to the epic via `mcp__github__sub_issue_write`
   (GitHub's first-class sub-issue API), not just via the text reference
4. Sub-issues get normal labels: `status:ready` or `status:blocked`,
   plus priority / size / area. Never `epic`.

### Closing as redundant

When closing an issue rather than design-reviewing it:

- **`state_reason: not_planned`** — for redundant issues (a broader
  feature subsumes the narrower one). Post an explanatory comment
  referencing the broader issue and explaining why the narrower one no
  longer adds capability.
- **`state_reason: duplicate`** + `duplicate_of: <#N>` — for true
  duplicates (same underlying mechanism, different framing).

Never close an issue as redundant without an explanatory comment — the
audit trail matters.

### Asking for user input

Use the `AskUserQuestion` tool for binding decisions. Rules:

- Only include options when you genuinely don't know the right call
- Lead with the recommended option labelled `(Recommended)`
- Describe the trade-off in each option's `description` field, not the
  question body
- Batch 2–4 logically related questions in one call — don't ask one at
  a time when they're all on the table

---

## Autonomous issue workflow

This section governs how Claude Code operates when given a batch of issues
to work through unattended.

### Core principle

Work autonomously. Do not ask for confirmation unless the situation is
explicitly listed under **Stop and ask** below. Make reasonable judgment
calls and document them in the PR description.

### Issue cycle

When given one or more GitHub issue numbers, process them **sequentially**.
Complete the full cycle for each issue before starting the next.

When given no specific issue number, use the selection algorithm in §0 to
pick the next one from the queue.

When processing a batch of issues, after completing each issue cycle
successfully, append the issue number to `.autonomous-progress` in the
repo root. This allows an interrupted batch to be resumed by checking
which issues are already recorded there.

#### 0. Pick the next issue (if none was given)

Every open issue should carry three metadata labels:

- **Status** — `status:ready`, `status:blocked`, `status:design-needed`,
  or `status:needs-info`
- **Priority** — `priority:p0` (ship this week) through `priority:p3`
  (someday-maybe)
- **Size** — `size:xs` (<1h), `size:s` (half-day), `size:m` (1–2 days),
  `size:l` (3–5 days), `size:xl` (epic; break down before picking up)

Pick the next issue using this deterministic queue:

1. **Filter** to issues matching ALL of:
   - `state:open`
   - `status:ready` (exclude `status:blocked`, `status:design-needed`,
     `status:needs-info`)
   - no assignee (not already being worked on)
   - not labelled `epic` (those are tracking issues, not implementation work)

2. **Sort** by priority descending: `p0` > `p1` > `p2` > `p3`.
   Missing priority label → treat as `p3`.

3. **Break priority ties by milestone preference**: within the same
   priority, prefer the current release milestone first (the lowest
   open `vX.Y`), then a themed hardening bucket (`MVP-hardening` or
   similar), then `Backlog`, then unmilestoned. This keeps the agent
   focused on the active release commitment without ignoring
   higher-priority work elsewhere — a `priority:p1` in `Backlog`
   still out-ranks a `priority:p2` in the current release.

4. **Break remaining ties** by size ascending (smallest first):
   `xs` > `s` > `m` > `l` > `xl`. Missing size label → treat as `m`.

5. **Break final ties** by issue number ascending (oldest first).

Saved GitHub queries (run in order — exhaust the first before moving to
the next):

```
# Current release — drain this first at each priority level
is:issue is:open no:assignee label:status:ready -label:epic milestone:"v0.22"

# Hardening bucket — drain after current release
is:issue is:open no:assignee label:status:ready -label:epic milestone:"MVP-hardening"

# Backlog — drain last
is:issue is:open no:assignee label:status:ready -label:epic milestone:"Backlog"
```

Substitute the actual current release milestone name (e.g. `v0.22`,
`v0.23`) when running these.

Sort each result set by label priority manually (GitHub search doesn't
sort by label precedence), then by size ascending, then by issue
number ascending.

**Never pick** issues labelled `status:design-needed` or `status:needs-info`.
If you believe one of those issues is actually ready, state the case in a
comment and ask for the label to be changed — do not proceed unilaterally.

**Never pick** `size:xl` issues. Ask the user to break them into smaller
issues first.

**Never pick** issues from the "Stop and ask" list below, even if labelled
`status:ready`.

#### 1. Understand the issue

```bash
gh issue view <number>
```

Read the issue fully. Before doing anything else, check it is still open
and has no existing PR:

```bash
gh issue view <number> --json state -q .state          # must be OPEN
gh pr list --search "issue-<number>" --state open      # must be empty
```

If the issue is closed or already has an open PR, skip it and move to the
next. If the issue is ambiguous, make a reasonable interpretation, document
it in the PR description, and proceed.

#### 2. Branch

Always branch off `origin/development`, never off another feature branch.
Name the branch to match the issue type:

```bash
git fetch origin

# bug fix
git checkout -b fix/issue-<number>-<short-slug> origin/development
# feature / enhancement
git checkout -b feat/issue-<number>-<short-slug> origin/development
# chore / docs / refactor
git checkout -b chore/issue-<number>-<short-slug> origin/development
```

#### 3. Implement

Make the necessary changes. Follow all conventions in this file.

**Coverage:** 100% is required — CI fails below this.
- Every new Python module needs tests in `tests/unit/` or `tests/integration/`.
- Every new UI component needs a co-located `*.test.jsx` file.

**Copyright, UI conventions, dependency management:** follow the rules
defined in the sections above.

#### 4. Run pre-push gate

```bash
uv run inv pre-push
```

If infra files changed, also run:

```bash
uv run inv synth
```

Fix all failures before proceeding. Do not open a PR with a failing
pre-push gate.

#### 5. Run local e2e if warranted

Apply the "when to run local e2e tests" rules above to decide whether to
run e2e before opening the PR.

**Important:** `inv dev` is a long-lived blocking process. Do not attempt
to start it in the background during an autonomous session. Instead:

- If the local stack is already running (started externally), run:

  ```bash
  uv run inv e2e-local
  # or for a specific test file:
  uv run inv e2e-local --tests tests/e2e/<relevant_file>.py
  ```

- If the local stack is **not** running, skip local e2e and note in the PR
  description: *"Local e2e not run — CI will cover this on the development
  branch deploy."* The `development` pipeline deploys and runs the full e2e
  suite, which is an adequate safety net for most changes.

Fix any failures before proceeding.

**Decision rules for "use judgement" cases:**

- Any change to a UI component → run `tests/e2e/test_ui_e2e.py`
- Any change to `api/` endpoints → run `tests/e2e/test_mcp_e2e.py` and/or
  `tests/e2e/test_auth_e2e.py` depending on what's affected

#### 6. Create PR

Rebase and verify clean history:

```bash
git fetch origin
git rebase origin/development
git log --oneline origin/development..HEAD   # must show ONLY your commits
```

Push — use `-u` for a brand-new branch, `--force-with-lease` after a rebase
on an already-pushed branch:

```bash
# first push of this branch
git push -u origin <branch>

# after a rebase on a branch already pushed
git push --force-with-lease
```

Create the PR. **Do not enable auto-merge yet if the linked issue is
labelled `agent-safe`** — step 7.5 owns that for the Copilot-review
flow. Arming auto-merge at PR-create time means CI finishes, the PR
squashes, and the Copilot step never runs (observed on #599).

```bash
gh pr create --base development \
  --title "<concise title>" \
  --body "Closes #<number>

## Summary
<what was changed and why>

## Approach
<any non-obvious decisions or interpretations of the issue>"

# Only for PRs whose linked issue is NOT labelled `agent-safe`:
gh pr merge --auto --squash --delete-branch
```

#### 7. Monitor PR CI

Get the run ID and watch until all checks pass or a failure requires a fix:

```bash
gh run list --branch <branch> --limit 1   # get the run ID
gh run watch <run-id>
```

If any check fails:
1. Read the failure: `gh run view <run-id> --log-failed`
2. Fix on the same branch
3. `git push`
4. Get the new run ID: `gh run list --branch <branch> --limit 1`
5. Return to watching

Repeat until all checks pass. Auto-merge fires automatically once they
do — except on `agent-safe` PRs, where step 7.5 arms auto-merge only
after the Copilot loop completes.

If the same check fails 3 times without a clear fix, stop and ask.

#### 7.5 Request Copilot review

Runs on **every** agent-created PR — `agent-safe` or not. The label
no longer gates whether the review runs; it only gates whether the
agent *merges* autonomously after the review completes. Every PR
gets a second opinion.

For non-`agent-safe` PRs, running Copilot review still benefits the
human who will merge — they inherit a cleaner PR where small
correctness / clarity findings have already been addressed.

Auto-merge is **not** armed yet at this point — step 6 deliberately
skipped it so this review can run without racing the merge. For
`agent-safe` PRs, auto-merge is armed at the end of this step. For
non-`agent-safe` PRs, the human merges once they're satisfied.

1. After CI is green, request a Copilot review on the PR via
   `mcp__github__request_copilot_review`.
2. Wait for the Copilot **`Agent` check-run** to move to
   `completed` (`get_check_runs`, typically 2–5 min), **then wait an
   additional ~90s** before the first `get_review_comments` call —
   the Agent check closes before Copilot finishes writing individual
   line-level comments to the PR, so polling immediately on
   completion returns an empty thread list even when findings are
   incoming (observed on #606: Agent completed at 12:41:52, comments
   posted at 12:43:03). **Do not rely on `get_reviews` alone** —
   subsequent Copilot iterations can post line-level comments without
   creating a new top-level review object, so `get_reviews` will
   look empty even when new findings exist. The authoritative
   signal is: Agent check completed + ≥90s elapsed + a fresh
   `get_review_comments` call shows threads from
   `copilot-pull-request-reviewer` whose `created_at` is after the
   last fix commit's timestamp.
3. Call `get_review_comments` and triage
   each unresolved thread. **Every thread gets a reply before it's
   resolved** — never silently close a thread. Use
   `mcp__github__add_reply_to_pull_request_comment`, then
   `mcp__github__resolve_review_thread`.
   - **Correctness / security / clarity finding** — write the fix on
     the same branch, run `uv run inv pre-push` locally (the post-fix
     safety gate — if it breaks, revert the fix and reply `This would
     introduce a regression; declining.`), push, reply on the thread
     with `Fixed in <SHA> — <one-line summary>`, resolve the thread,
     then re-request Copilot review.
   - **Pure style nit** (Tailwind class order, const-vs-let, naming
     preference, import sort) — reply with a short canned decline
     citing project conventions, then resolve the thread.
   - **Ambiguous, architecturally significant, or would meaningfully
     change scope** — emit
     `HUMAN_INPUT_REQUIRED: Copilot flagged X on #NNN — unclear call`
     and stop. Do **not** resolve the thread — leave it open so the
     human reviewer sees exactly what was flagged.
4. **Hard iteration cap: 5, with early-exit on convergence.** Stop
   the review loop when either:
   - 5 round-trips have completed, OR
   - Two consecutive iterations produce no new actionable findings
     (style-only comments don't count as actionable).

   If unresolved findings remain at the stop point, emit
   `HUMAN_INPUT_REQUIRED: Copilot loop ended with open findings on
   #NNN` and stop. Leave those threads unresolved so the human sees
   them. Otherwise continue to step 5.
5. **Agent-safe PRs**: arm auto-merge via
   `mcp__github__enable_pr_auto_merge` (squash). It fires when CI
   is green.

   **Non-agent-safe PRs**: emit
   `HUMAN_INPUT_REQUIRED: PR #NNN ready for human review + merge`
   and stop. Do not arm auto-merge and do not move to the next
   issue until the human merges.

Apply fixes to real findings even if they're small — Copilot's value
is catching the subtle correctness issues the test suite won't.
Default to disagreeing on style-only comments; default to agreeing on
security / correctness / clarity.

#### 8. Monitor development branch CI/CD post-merge

After the PR merges, the `development` branch pipeline triggers. Record the
merge time and poll until a matching run appears, then watch it:

```bash
# Record merge time, then poll until an active run created after merge appears
MERGE_TIME=$(date -u +%s)
while true; do
  RUN_ID=$(gh run list --branch development --limit 5 \
    --json databaseId,status,createdAt | \
    jq -r --argjson since "$MERGE_TIME" \
    '.[] | select(
        (.status == "in_progress" or .status == "queued") and
        (.createdAt | fromdateiso8601) > $since
      ) | .databaseId' | head -1)
  [ -n "$RUN_ID" ] && break
  sleep 15
done
gh run watch "$RUN_ID"
```

This uses `jq`'s built-in `fromdateiso8601` for portable timestamp parsing —
avoids the `date -r` vs `date -d` incompatibility between macOS and Linux,
and ensures we only latch onto a run triggered by this merge rather than a
pre-existing in-flight run from a concurrent PR.

If the pipeline fails:
1. Read the failure: `gh run view <run-id> --log-failed`
2. Create a new fix branch off the updated `origin/development`
3. Fix, run `inv pre-push`, run local e2e if warranted
4. PR and repeat from step 6

Only move to the next issue when the `development` pipeline is green.

#### 9. Check if the milestone is drained

After the development pipeline is green, check whether the closed issue's
milestone still has any open, non-epic issues:

```bash
# Resolve the milestone number from the issue just closed (via gh)
MILESTONE=$(gh issue view <number> --json milestone --jq '.milestone.title')

# If the milestone exists and matches a release-milestone pattern (vX.Y),
# count the open non-epic issues remaining in it
if [[ -n "$MILESTONE" && "$MILESTONE" =~ ^v[0-9]+\.[0-9]+$ ]]; then
  REMAINING=$(gh issue list \
    --milestone "$MILESTONE" \
    --state open \
    --json labels \
    --jq '[.[] | select(.labels | map(.name) | contains(["epic"]) | not)] | length')

  if [ "$REMAINING" -eq 0 ]; then
    echo "HUMAN_INPUT_REQUIRED: Milestone $MILESTONE has no open issues — ready to cut release?"
    exit 0   # stop; do not pick up the next issue
  fi
fi
```

If the release milestone is drained, stop and surface the sentinel so the
operator can decide whether to cut the release first or continue draining
from `Backlog`. Do **not** unilaterally create a release branch — releases
are a human decision per §Releasing to production.

If the milestone is non-release (e.g. `Backlog`, `MVP-hardening`), or the
issue has no milestone, or there are still open non-epic items: skip this
step and pick up the next issue normally.

### Keeping CLAUDE.md current

If you discover that CLAUDE.md is missing information needed to work
effectively — a new inv task, an undocumented gotcha, a test convention —
update it in the same PR as the change that surfaced it.

**Permitted without asking:**
- Adding or correcting inv task names, commands, or flags
- Documenting a newly discovered gotcha or test convention
- Updating the file structure map when new files are added

**Requires human review (open a separate PR, do not auto-merge):**
- Any change to the "Autonomous issue workflow" section
- Any change to the "Stop and ask" list
- Any change that expands what Claude is permitted to do unattended

### Stop and ask

When stopping, always emit a sentinel as the first line of your message:

```
HUMAN_INPUT_REQUIRED: <brief reason>
```

This allows automated monitoring to detect the stop and alert the operator.

Halt and wait for human input **only** in these situations:

- The PR is not auto-merging after CI passes and the reason is unclear
- The `development` pipeline failure is in infrastructure (CDK / Lambda /
  DynamoDB) and the root cause is not apparent from logs
- A change requires modifying `infra/stacks/starter_stack.py` in a way that
  could affect production resources
- The same CI check has failed 3 times without a clear fix
- A release milestone (pattern `vX.Y`) drains to zero open non-epic issues —
  stop after step 9 and surface so the user can decide whether to cut the
  release before continuing

In all other cases, make a judgment call and proceed.

### What you must never do

- Push directly to `development` or `main`
- Merge a PR manually — auto-merge handles this
- Run `gh release create` — CI owns releases
- Hardcode credentials, secrets, or AWS account IDs
- Use `pip` or `requirements.txt` — always use `uv`
- Skip `inv pre-push` before creating a PR
- Pin GitHub Actions to mutable version tags — use full commit SHAs

## Backlog labels and milestones

The selection algorithm in §Autonomous issue workflow §0 assumes every
open implementation issue carries status + priority + size + area labels.
This section defines the taxonomy and the creation rules that keep the
queue trustworthy.

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

### Public roadmap labels

Orthogonal to the backlog-workflow `status:*` labels — an issue can
carry one of each without conflict. These control what surfaces on
the public-facing `/roadmap` page (rendered by `RoadmapPage.jsx`,
fetching from GitHub's public REST API at render time):

- `public-roadmap` — gate label. Without it, the issue never appears
  on the roadmap regardless of other labels.
- `roadmap:now` — **Now** column — in-progress, landing soon
- `roadmap:next` — **Next** column — planned for the next release or two
- `roadmap:later` — **Later** column — accepted, no committed date

Issues with `public-roadmap` but no `roadmap:*` label are
intentionally omitted — the roadmap is curated, not a dump.

The **Shipped** column auto-populates from closed `public-roadmap`
issues (time-ordered, capped to the 8 most-recent) — no label flip
needed when work lands.

Deliberately a separate namespace from `status:*` because
`label-check.yml` already treats `status:*` as the required
backlog-workflow status (`status:ready` / `blocked` /
`design-needed` / `needs-info`). Using `roadmap:*` avoids cross-purpose
confusion.

Principle: the roadmap communicates to users what we've chosen to
tell them — not every tagged issue. Prefer fewer, clearer cards over
exhaustive coverage. Skip bugs, infra/CI chores, internal security
fixes, design spikes that don't read as user-visible capability, and
anything that would confuse or worry users (e.g. cross-tenant leak
investigations).

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