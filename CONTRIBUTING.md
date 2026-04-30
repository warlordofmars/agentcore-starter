# Contributing to AgentCore Starter

Thanks for your interest in contributing! This guide covers local dev setup, the test workflow, and how to open a PR.

## Prerequisites

- Python 3.12+
- Node 20+
- Docker (for DynamoDB Local in integration tests)
- [uv](https://docs.astral.sh/uv/) — all Python dependency management goes through `uv`, never `pip`

## Local setup

```bash
git clone <your-fork>
cd agentcore-starter

# Python deps (creates .venv automatically)
uv sync --all-extras

# JS deps
cd ui && npm install && cd ..

# Install the git pre-push hook (runs the same gate as CI)
uv run inv install-hooks
```

## Running the stack locally

```bash
# Start all services (DynamoDB Local, API, Vite dev server)
uv run inv dev

# Or start the API manually (port 8001)
STARTER_BYPASS_GOOGLE_AUTH=1 \
uv run uvicorn starter.api.main:app --port 8001 --reload

# React UI (port 5173)
cd ui && npm run dev
```

DynamoDB Local is required for the API. Start it with Docker:

```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
```

Or use the invoke task which spins up the full local stack:

```bash
uv run inv dev
```

## Tests

```bash
# Unit tests — no external dependencies
uv run inv test-unit

# Integration tests — requires DynamoDB Local
uv run inv test-integration

# Frontend tests
uv run inv test-frontend

# Full pre-push gate (lint + type check + unit + frontend)
uv run inv pre-push
```

E2E tests run against a deployed environment and are handled by CI after merging to `development`. See [tests/README.md](tests/README.md) for details.

CI also runs a SonarCloud quality-gate scan in the `Coverage Report` job — the scan is skipped cleanly when `SONAR_TOKEN` is unset (typical on a fresh fork), so the rest of the pipeline still runs; see Phase 4.5 of [`.claude/agents/onboarding.md`](.claude/agents/onboarding.md) for the full SonarCloud bootstrap including the new-code baseline definition (#54).

## Code style

- **Python**: [ruff](https://docs.astral.sh/ruff/) for lint + format, [mypy](https://mypy-lang.org/) for type checking
- **JavaScript**: ESLint (run via `npm run lint` in `ui/`)
- Line length: 100 characters
- All new Python files must have a copyright header: `# Copyright (c) 2026 John Carter. All rights reserved.`

Run the full gate before opening a PR:

```bash
uv run inv pre-push
```

## Dependency management

Always use `uv` — never `pip` or `requirements.txt`:

```bash
uv add <package>           # add a runtime dependency
uv add --dev <package>     # add a dev dependency
uv sync --all-extras       # sync all deps from lockfile
```

## Branching and PRs

- Branch from `development` (not `main`)
- Use descriptive branch names: `feat/my-feature`, `fix/bug-description`, `docs/update-readme`
- Every PR must reference the associated GitHub issue: `Closes #NNN`
- Squash merge to `development`; `--merge` commits for `development → main` releases

## What makes a good PR

- Focused — one thing per PR
- Tests included for new behaviour
- Coverage stays at 100% (CI enforces this)
- `uv run inv pre-push` passes locally before pushing
- PR description explains *why*, not just *what*
