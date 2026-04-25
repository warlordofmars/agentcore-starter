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

```bash
gh secret set AWS_DEV_DEPLOY_ROLE_ARN --body "<arn>"
gh secret set AWS_DEPLOY_ROLE_ARN --body "<arn>"
gh secret set SONAR_TOKEN --body "<token>"
# etc.
```

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
