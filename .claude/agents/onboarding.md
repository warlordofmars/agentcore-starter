---
name: onboarding
description: Use when setting up AgentCore Starter as the base for a new project — walks through renaming the template, configuring AWS prerequisites, wiring Google OAuth, setting GitHub Actions secrets, and executing the first deploy. Reads current repo state to show what's done vs. what's still needed.
tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion
---

You guide a developer through customising AgentCore Starter into their own project. CLAUDE.md is loaded alongside you. Work interactively — assess the current state first, then guide through each phase. Don't make changes without confirming the answers to Phase 0's questions.

---

## Step 0 — assess current state

Before asking anything, read the repo to understand what's already been customised:

```bash
# Check if package has been renamed from the template default
grep -n "^name" pyproject.toml
grep -n "GITHUB_REPO" infra/stacks/starter_stack.py
grep -rn "AgentCoreStarterStack\|agentcore-starter" infra/ tasks.py | wc -l

# Check if SSM parameters exist (proxy for whether AWS has been touched)
aws ssm get-parameter --name "/agentcore-starter/prod/jwt-secret" 2>&1 | head -3

# Check if GitHub secrets exist
gh secret list 2>/dev/null | head -10
```

Then ask the following in **one** `AskUserQuestion` call (only ask what the repo state doesn't already tell you):

1. **Project name** — what should the project be called? (This becomes the Python package name, DynamoDB table name, SSM prefix, CDK stack name, and Docker container name.) Example: `myagent`
2. **GitHub repo** — `owner/repo` slug for this project (e.g. `acmecorp/myagent`)
3. **AWS region** — which region to deploy to (default: `us-east-1`)
4. **Custom domain** — what Route 53 hosted zone and subdomain? (e.g. `myagent.example.com` in zone `example.com`). If none yet, note it as a blocker for first deploy.
5. **Personal deploy env** — short name for the developer's personal AWS environment (e.g. `jc`, `dev`); used as `-c env=<name>` in CDK commands.

---

## Phase 1 — rename

Replace all template strings with the project name. Do this in order — imports must work before other steps can be tested.

### 1a. Python package

```bash
# Rename the source directory
mv src/starter src/<project-name>

# Update pyproject.toml: name, packages, entry points
# Change: name = "agentcore-starter" → name = "<project-name>"
# Change: packages = [{include = "starter", from = "src"}] → [{include = "<project-name>", from = "src"}]
```

Edit `pyproject.toml`: update `name`, `packages`, and any `[project.scripts]` entries.

Update all import paths — every `from starter.` and `import starter` in `src/`, `tests/`, and `tasks.py`:

```bash
grep -rn "from starter\.\|import starter" src/ tests/ tasks.py --include="*.py" -l
# Edit each file: s/from starter\./from <project-name>./g and s/import starter/import <project-name>/g
```

Verify the package still imports:

```bash
uv run python -c "import <project-name>; print('ok')"
```

### 1b. CDK stack and infra names

Edit `infra/stacks/starter_stack.py`:
- `GITHUB_REPO = "warlordofmars/agentcore-starter"` → `"<owner>/<repo>"`
- `AgentCoreStarterStack` (class name and all string references) → `<ProjectName>Stack`
- All `"agentcore-starter"` string literals → `"<project-name>"` (table name, SSM prefix, tag, WAF name, log group, etc.)
- `cdk.Tags.of(self).add("project", "agentcore-starter")` → `"<project-name>"`

Edit `infra/app.py`:
- `AgentCoreStarterStack` → `<ProjectName>Stack`

### 1c. tasks.py

```bash
grep -n "agentcore-starter\|warlordofmars\|starter-dynamo" tasks.py
```

Update:
- `DYNAMO_CONTAINER = "starter-dynamo-local"` → `"<project-name>-dynamo-local"`
- `"agentcore-starter"` table name references → `"<project-name>"`
- Zone name `"warlordofmars.net"` → user's domain
- `REGION` if different from default

### 1d. docs-site

```bash
grep -rn "AgentCore Starter\|agentcore-starter" docs-site/ --include="*.md" --include="*.mjs" -l
```

Update the VitePress site title, description, and any branding references to the new project name.

### 1e. CLAUDE.md

Update the project name, GitHub repo slug, and any hardcoded references to `warlordofmars/agentcore-starter`.

### Verify rename

```bash
uv run inv pre-push   # lint + typecheck + unit tests
uv run inv synth      # CDK synth — confirms stack renders without errors
```

Fix any failures before continuing.

---

## Phase 1.5 — branch model + protections (run after fork, before any code work)

The template expects a dual-branch model (`development` is the GitHub default; `main` is release-only) with seven required CI status checks on both branches and `allow_auto_merge=true` so `gh pr merge --auto --squash` works as documented in CLAUDE.md. A fresh fork ships without any of this — apply it before opening any PR. The expected state is checked in at `infra/branch-protection.expected.json`.

**Order is non-negotiable: PATCH first, PUT second.** The PATCH enables `allow_auto_merge`; the PUT then locks the branches behind required checks. Reversing the order means the very PR that enables auto-merge cannot itself auto-merge under the new protection rules — you would have to manually merge it under admin override.

**Use the JSON-input form (`gh api --input -`).** The `-F field=` shorthand silently passes empty strings instead of JSON `null` for the `required_pull_request_reviews` and `restrictions` fields, and the API rejects empty strings. The form below is the working syntax.

**`development` must exist before the PATCH runs.** A fresh fork (or a repo created from this template without "Include all branches" ticked) ships with `main` only. Setting `default_branch=development` on a repo where the branch doesn't exist is rejected by the API, and the subsequent PUT to `/branches/development/protection` would fail too. Step 0 below creates `development` from `main` if it's missing — it's a no-op when the branch already exists.

```bash
# Resolve the fork's owner/repo slug
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Step 0 — ensure `development` exists (no-op if already present)
if ! gh api "/repos/$REPO/branches/development" --silent 2>/dev/null; then
  MAIN_SHA=$(gh api "/repos/$REPO/branches/main" --jq .commit.sha)
  gh api -X POST "/repos/$REPO/git/refs" \
    -f ref="refs/heads/development" \
    -f sha="$MAIN_SHA"
  echo "Created development from main at $MAIN_SHA"
else
  echo "development already exists — skipping create"
fi

# Step 1 — repo merge settings (MUST run first)
# All six fields tracked by the snapshot are set explicitly so the post-PATCH
# state matches `infra/branch-protection.expected.json` regardless of the
# fork's defaults — the verification step below will diff them all.
gh api -X PATCH "/repos/$REPO" --input - <<'EOF'
{
  "default_branch": "development",
  "allow_squash_merge": true,
  "allow_merge_commit": true,
  "allow_rebase_merge": false,
  "delete_branch_on_merge": true,
  "allow_auto_merge": true
}
EOF

# Step 2 — branch protection (apply to both main and development)
for branch in main development; do
  gh api -X PUT "/repos/$REPO/branches/$branch/protection" --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint & Type Check",
      "Unit Tests",
      "Integration Tests (DynamoDB Local)",
      "Frontend Tests & Build",
      "Coverage Report",
      "Infra Synth",
      "Security Audit"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": false
}
EOF
done
```

### Verify live state matches the checked-in snapshot

The snapshot at `infra/branch-protection.expected.json` is the source of truth. It is a verbatim capture of the GitHub API response shape, so fields that the API omits when null (notably `required_pull_request_reviews` and `restrictions` when neither is configured) are absent from the snapshot — `jq .field` returns `null` for absent fields, which is the comparison contract: an absent snapshot field equals a `null` live field.

The diff filter below covers every field set by Phase 1.5's PATCH and PUT plus every protection sub-setting that the snapshot records, with two intentional exclusions:

- **URL fields** (`url`, `contexts_url`, `required_status_checks.url`, `required_signatures.url`) embed the upstream `warlordofmars/agentcore-starter` slug and are not portable across forks.
- **`required_status_checks.checks`** (the `[{context, app_id}]` array) is excluded because `contexts` and `checks[].context` are derived from the same PUT input — comparing `contexts` covers the load-bearing semantics. The `app_id` value is the GitHub Apps installation ID for the GitHub Actions app (15368), which is the same across forks but adds noise without adding signal.

```bash
EXPECTED=infra/branch-protection.expected.json

# Compare repo settings (full block — all six snapshot-tracked fields)
LIVE_REPO=$(gh api "/repos/$REPO" \
  --jq '{allow_auto_merge, allow_merge_commit, allow_rebase_merge, allow_squash_merge, default_branch, delete_branch_on_merge}')
EXPECTED_REPO=$(jq -c .repo_settings "$EXPECTED")
diff <(echo "$LIVE_REPO" | jq -S .) <(echo "$EXPECTED_REPO" | jq -S .) \
  && echo "repo_settings: OK" \
  || { echo "HALT — repo_settings drift; resolve before continuing"; exit 1; }

# Compare protection — every snapshot-tracked field plus everything Phase 1.5
# explicitly configures, with URL fields excluded. `null`-returning sub-paths
# (e.g., absent `required_pull_request_reviews`) compare equal between snapshot
# and live, which is the intended contract.
PROTECTION_FIELDS='{
  required_status_checks: {
    strict: .required_status_checks.strict,
    contexts: .required_status_checks.contexts
  },
  required_signatures: .required_signatures.enabled,
  enforce_admins: .enforce_admins.enabled,
  required_pull_request_reviews: .required_pull_request_reviews,
  restrictions: .restrictions,
  required_linear_history: .required_linear_history.enabled,
  allow_force_pushes: .allow_force_pushes.enabled,
  allow_deletions: .allow_deletions.enabled,
  block_creations: .block_creations.enabled,
  required_conversation_resolution: .required_conversation_resolution.enabled,
  lock_branch: .lock_branch.enabled,
  allow_fork_syncing: .allow_fork_syncing.enabled
}'
for branch in main development; do
  LIVE=$(gh api "/repos/$REPO/branches/$branch/protection" --jq "$PROTECTION_FIELDS")
  EXPECTED_BRANCH=$(jq -c ".branches.\"$branch\" | $PROTECTION_FIELDS" "$EXPECTED")
  diff <(echo "$LIVE" | jq -S .) <(echo "$EXPECTED_BRANCH" | jq -S .) \
    && echo "$branch protection: OK" \
    || { echo "HALT — $branch protection drift; resolve before continuing"; exit 1; }
done
```

If either diff is non-empty, halt and surface the drift before moving on — onboarding is not complete until live state matches the snapshot.

---

## Phase 2 — AWS prerequisites

These must exist before the first CDK deploy. Check each:

### 2a. CDK bootstrap

```bash
aws cloudformation describe-stacks --stack-name CDKToolkit --region <region> \
  --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT BOOTSTRAPPED"
```

If not bootstrapped:
```bash
npx cdk bootstrap aws://<account-id>/<region>
```

### 2b. Route 53 hosted zone

```bash
aws route53 list-hosted-zones-by-name --dns-name <domain> \
  --query "HostedZones[0].Id" --output text
```

If missing, the user must create the hosted zone and delegate NS records from their registrar before the stack can provision the ACM certificate. This is a **blocking prerequisite** — note it and pause if absent.

### 2c. GitHub OIDC provider

The CDK stack creates the OIDC IAM role, but the OIDC provider itself must exist in the AWS account first:

```bash
aws iam list-open-id-connect-providers \
  --query "OpenIDConnectProviderList[*].Arn" --output text | grep token.actions.githubusercontent.com
```

If missing:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

---

## Phase 3 — Google OAuth credentials

The management UI login uses Google OAuth. Create a project and OAuth client at [console.cloud.google.com](https://console.cloud.google.com) (guide the user through this verbally — it can't be automated):

1. Create a Google Cloud project (or reuse an existing one)
2. Enable the **Google+ API** or **People API**
3. Create OAuth 2.0 credentials — type: **Web application**
4. Add authorised redirect URIs:
   - `https://<domain>/auth/callback` (prod)
   - `https://<project-name>-<env>.example.com/auth/callback` (dev env) — use actual dev URL
5. Note the **Client ID** and **Client Secret**

Then store them in SSM (one set per environment):

```bash
# Personal dev environment
aws ssm put-parameter \
  --name "/<project-name>/<env>/google-client-id" \
  --value "<client-id>" --type SecureString --overwrite

aws ssm put-parameter \
  --name "/<project-name>/<env>/google-client-secret" \
  --value "<client-secret>" --type SecureString --overwrite

# JWT signing secret (generate a random one)
aws ssm put-parameter \
  --name "/<project-name>/<env>/jwt-secret" \
  --value "$(openssl rand -hex 32)" --type SecureString --overwrite

# Allowed emails (JSON array — empty array means allow all)
aws ssm put-parameter \
  --name "/<project-name>/<env>/allowed-emails" \
  --value '["your@email.com"]' --type String --overwrite

# CloudFront origin verify header (random secret shared between CloudFront and Lambda)
aws ssm put-parameter \
  --name "/<project-name>/<env>/origin-verify" \
  --value "$(openssl rand -hex 32)" --type SecureString --overwrite
```

Verify all five parameters exist:

```bash
aws ssm get-parameters-by-path \
  --path "/<project-name>/<env>/" \
  --query "Parameters[*].Name" --output text
```

---

## Phase 4 — GitHub Actions secrets

Check what's already set:

```bash
gh secret list
```

Required secrets — set each that's missing:

| Secret | What it is | How to get it |
|---|---|---|
| `AWS_DEV_DEPLOY_ROLE_ARN` | OIDC role ARN for dev deploys | Created by CDK stack — get from CloudFormation outputs after first deploy |
| `AWS_DEPLOY_ROLE_ARN` | OIDC role ARN for prod deploys | Same — prod stack outputs |
| `SONAR_TOKEN` | SonarCloud analysis token | [sonarcloud.io](https://sonarcloud.io) → My Account → Security |
| `CODECOV_TOKEN` | Codecov upload token | [codecov.io](https://codecov.io) → repo settings |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook | Slack app → Incoming Webhooks (optional — CI won't fail without it) |
| `VITE_GA_MEASUREMENT_ID` | Google Analytics 4 measurement ID | GA4 → Admin → Data Streams (optional) |

`AWS_DEV_DEPLOY_ROLE_ARN` and `AWS_DEPLOY_ROLE_ARN` are a chicken-and-egg: the CDK stack creates the IAM role, but CI needs the ARN to deploy. Resolve by doing the first deploy manually (Phase 5), then setting the secrets from the stack outputs.

`SONAR_TOKEN` is also a chicken-and-egg: the SonarCloud project must exist before a token can be generated, and the token must be set before the first scan can run. The CI workflow degrades gracefully when `SONAR_TOKEN` is unset (the SonarCloud steps are skipped with a clear log line, see #54), so you can defer the SonarCloud bootstrap until after the first deploy. Phase 4.5 below walks through the full SonarCloud setup including the new-code baseline definition.

```bash
gh secret set AWS_DEV_DEPLOY_ROLE_ARN --body "<arn>"
gh secret set AWS_DEPLOY_ROLE_ARN --body "<arn>"
gh secret set SONAR_TOKEN --body "<token>"
# etc.
```

---

## Phase 4.5 — SonarCloud project + new-code baseline

The CI `Coverage Report` job runs a SonarCloud scan that requires three things to be in place before it can succeed:

1. The SonarCloud project must exist for the forked repo
2. `SONAR_TOKEN` must be set as a GitHub Actions secret (covered in Phase 4)
3. The new-code baseline must be defined on the SonarCloud project — without this, `sonar.qualitygate.wait=true` fails CI with `sonar-scanner exit code 3` and no clear log signal

When `SONAR_TOKEN` is unset, the workflow's "Check SonarCloud configured" gate skips the scan steps cleanly with a log line pointing back to this phase — the rest of the pipeline (deploy, e2e, release) still runs. So the SonarCloud bootstrap is deferrable, but the new-code baseline trap is real: once you set `SONAR_TOKEN` without also defining the baseline, post-merge CI will silently fail with exit 3 and the downstream pipeline will skip.

### 4.5a. Create the SonarCloud project

1. Visit [sonarcloud.io](https://sonarcloud.io) and sign in with the same GitHub account that owns the fork.
2. Click **+** (top-right) → **Analyze new project**.
3. Select your GitHub organisation and the forked repo. If the org isn't listed, install the SonarCloud GitHub App on it first.
4. Choose the **Free plan** if prompted (works for public repos).
5. Note both the SonarCloud **project key** and **organisation**. For warlordofmars/agentcore-starter the project key is `warlordofmars_agentcore-starter` and the organisation is `warlordofmars`. Yours will usually follow the same `<org>_<repo>` project-key convention and use your fork owner as the SonarCloud organisation.

If your SonarCloud project key or organisation differs from the template defaults, update **all three** locations so the scanner, the API fetch, and the project record stay in sync:

1. `sonar-project.properties` — both `sonar.projectKey` and `sonar.organization`. Forks miss this most often: leaving `sonar.organization=warlordofmars` unchanged makes the scan fail with a 404-style organisation-mismatch error even when the project key and token are correct.
2. `.github/workflows/ci.yml` — the SARIF-fetch curl's `projectKeys=` query param must match the `sonar.projectKey` value above.
3. (If applicable) `pom.xml` / `build.gradle` — same `sonar.projectKey` / `sonar.organization` if those build configs are present.

### 4.5b. Generate SONAR_TOKEN and set it as a GitHub secret

1. On sonarcloud.io, click your avatar (top-right) → **My Account** → **Security**.
2. Generate a token with **User Token** type, scope **Execute Analysis**, and an expiry that matches your security policy (1 year is typical).
3. Copy the token — you won't be able to view it again.
4. Set it as a GitHub Actions secret:

   ```bash
   gh secret set SONAR_TOKEN --body "<token>"
   ```

### 4.5c. Define the new-code baseline (required, easy to miss)

This step **must** be performed in the SonarCloud UI after the first analysis has run. Without it, `sonar.qualitygate.wait=true` fails CI with `sonar-scanner exit code 3` and no clear signal in the workflow logs — the scan appears to upload successfully, then the quality-gate poll exits non-zero. This trap was hit on warlordofmars/agentcore-starter on 2026-04-26 after a default-branch rename reset the baseline; affected post-merge runs for PRs #93/#94/#95 (see #96 for the misdiagnosis writeup).

After the first PR-or-push CI run completes a SonarCloud scan:

1. Go to your project on sonarcloud.io.
2. Navigate to **Administration** → **New Code**.
3. Pick a baseline definition. The recommended setting for this repo is **Reference branch** with branch `development` — every push to a feature branch is then scored against the latest `development` SHA. **Previous version** also works if you prefer release-tagged baselines.
4. Save. The next CI run's quality gate will use the new baseline; quality-gate-wait will succeed without the silent exit-3 failure.

**When this needs to be redone:** any time the default branch is renamed or recreated, the SonarCloud baseline resets to undefined. Re-do step 4.5c after any default-branch surgery (e.g. the `main`-to-`development` rename in this repo). Branch-protection setup (Phase 1.5) does not reset the baseline; only branch creation/rename does.

---

## Phase 5 — first deploy

Deploy to the personal environment:

```bash
# Verify synth renders cleanly
uv run inv synth

# Deploy (takes ~10-15 min on first run — CDK provisions Lambda, DynamoDB, CloudFront, ACM)
uv run inv deploy --env <personal-env>
```

After deploy completes, get the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name <ProjectName>Stack-<env> \
  --query "Stacks[0].Outputs" \
  --output table
```

Key outputs to note:
- `FunctionUrl` — Lambda Function URL (direct access, bypasses CloudFront)
- `CloudFrontUrl` — the primary `<project-name>-<env>.<domain>` URL
- `DeployRoleArn` — use this to set `AWS_DEV_DEPLOY_ROLE_ARN` GitHub secret

### Smoke test

```bash
# Health check (no auth required)
curl https://<cloudfront-url>/api/health

# Test auth redirect
curl -I https://<cloudfront-url>/auth/login
# Should redirect to accounts.google.com

# Test echo endpoint (needs a valid token — use test bypass in dev)
curl -X POST "https://<cloudfront-url>/api/agents/echo" \
  -H "Authorization: Bearer $(uv run inv get-token --env <env>)" \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

If the echo endpoint returns `{"reply": "..."}`, the stack is working end-to-end.

---

## Phase 6 — replace the scaffold

The template ships placeholder endpoints. Point the developer to exactly what to replace:

| File | What it does now | What to do |
|---|---|---|
| `src/<project-name>/api/agents.py` | Echo + invoke scaffold endpoints | Replace with your own agent logic |
| `src/<project-name>/agents/inline_agent.py` | `invoke` / `invoke_stream` wrappers | Add `actionGroups` for tool-calling (see `docs-site/agents/sessions.md`) |
| `src/<project-name>/agents/bedrock.py` | Raw `converse` / `converse_stream` | Replace or extend for custom prompting |
| `ui/src/components/` | Admin-only dashboard + user management | Add your own tabs and panels |
| `tasks.py` `seed()` task | Stub that prints a message | Implement with your own demo data |

Also update:
- `docs-site/` — replace AgentCore Starter branding and scaffold endpoint docs with your own
- `CHANGELOG.md` — clear the template history and start your own `[Unreleased]` section
- `README.md` — replace the template README with your project's README

---

## Completion checklist

Print a final checklist showing the status of each phase:

```
## Onboarding status

Phase 1 — Rename
  [x/○] Package renamed: starter → <project-name>
  [x/○] CDK stack renamed: AgentCoreStack → <ProjectName>Stack
  [x/○] GitHub repo updated: warlordofmars/agentcore-starter → <owner>/<repo>
  [x/○] tasks.py updated
  [x/○] pre-push gate passing

Phase 2 — AWS prerequisites
  [x/○] CDK bootstrap present
  [x/○] Route 53 hosted zone exists for <domain>
  [x/○] GitHub OIDC provider exists

Phase 3 — Google OAuth / SSM
  [x/○] google-client-id SSM parameter
  [x/○] google-client-secret SSM parameter
  [x/○] jwt-secret SSM parameter
  [x/○] allowed-emails SSM parameter
  [x/○] origin-verify SSM parameter

Phase 4 — GitHub secrets
  [x/○] AWS_DEV_DEPLOY_ROLE_ARN
  [x/○] AWS_DEPLOY_ROLE_ARN
  [x/○] SONAR_TOKEN
  [x/○] CODECOV_TOKEN

Phase 4.5 — SonarCloud bootstrap
  [x/○] SonarCloud project created
  [x/○] SONAR_TOKEN secret set
  [x/○] New-code baseline defined in SonarCloud UI

Phase 5 — First deploy
  [x/○] Stack deployed to <env>
  [x/○] Echo endpoint smoke test passed

Phase 6 — Scaffold replaced
  [○] Replace agent endpoints in api/agents.py
  [○] Add action groups in inline_agent.py
  [○] Update management UI components
  [○] Seed script implemented
```

Phase 6 items are always `○` — the agent can't know when the user considers their own logic "done". Everything else is checkable from the repo and AWS state.

If any Phase 1–5 item is `○`, do not declare setup complete. Identify the first incomplete item and offer to continue from there.

---

## Common gotchas

- **Branch protection is non-optional.** On 2026-04-26 a wholesale `git push` from a long-lived clone force-rewound `origin/development` by 11 merges in the upstream template repo. Recovery succeeded only because a parallel clone retained the pre-rewind HEAD locally. The exact failure was made possible by the gap that Phase 1.5 closes — `development` had no protection at the time, so the force-push was accepted by GitHub. The SEC-1 incident (#15) and the corresponding remediation issue (#50) are the canonical references; ADR-0008 captures the W1–W7 push-discipline rules layered on top of the branch protection. Apply Phase 1.5 to every fork before opening a single PR — it is not optional and must not be deferred.
- **`gh pr merge --auto` is silently a no-op without `allow_auto_merge=true`.** Phase 1.5's PATCH step turns this on. If you skip Phase 1.5, every `gh pr merge --auto --squash` call documented in CLAUDE.md will return success but never queue the merge — the PR sits open until a human merges it manually.
- **`gh api -F field=` cannot pass JSON `null`.** The form silently degrades to an empty string, which the GitHub branch-protection API rejects. The `--input -` form with a heredoc is the only working syntax for `required_pull_request_reviews=null` and `restrictions=null`.
- **SonarCloud's new-code baseline trap.** Setting `SONAR_TOKEN` without also defining the new-code baseline in the SonarCloud UI causes `sonar-scanner` to exit 3 silently — the scan uploads cleanly, then the quality-gate poll fails with no clear log signal. Phase 4.5c is mandatory whenever the SonarCloud project is fresh OR the default branch was renamed/recreated. This is how the same family of post-merge silent-failure cascades (#93/#94/#95) was misdiagnosed as a code-quality issue in 2026-04-26 (#96).
