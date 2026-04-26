# Tests

Three layers of tests, each with different dependencies and scope.

```
tests/
├── unit/              # Pure logic, no AWS or network deps
│   ├── test_models.py
│   ├── test_auth.py
│   └── test_storage.py
├── integration/       # Against DynamoDB Local
│   ├── test_api.py
│   └── test_oauth.py
└── e2e/               # Against the deployed AWS stack
    ├── __init__.py
    └── conftest.py        # Shared fixtures (e.g. live_admin_token)
```

> **Note:** The per-suite e2e files (`test_auth_e2e.py`, `test_mcp_e2e.py`,
> `test_admin_e2e.py`, `test_ui_e2e.py`, `test_docs_e2e.py`,
> `test_dashboard_e2e.py`) were removed during the #47-era scaffolding
> strip-down and have not yet been reauthored against the current API/UI
> surface. The CI `e2e-dev` job currently runs a single curl smoke check
> against the deployed dev API's `/health` endpoint instead. Reauthoring
> proper e2e suites is tracked separately.

## Unit tests

No external dependencies. Use `moto` to mock AWS and `STARTER_JWT_SECRET` to fix the JWT signing secret.

```bash
STARTER_JWT_SECRET=test-secret uv run pytest tests/unit -v
```

Or simply:

```bash
uv run pytest tests/unit -v
# moto mocks AWS; JWT secret auto-generates (consistent within the process)
```

Covers: model serialization/deserialization, DynamoDB read/write patterns, token issuance/validation, OAuth code flow logic.

## Integration tests

Run against a real DynamoDB Local instance. Each test module creates its own table with a unique name to isolate state.

### Start DynamoDB Local

```bash
docker run -d --name dynamo-local -p 8000:8000 amazon/dynamodb-local:latest
```

### Run integration tests

```bash
DYNAMODB_ENDPOINT=http://localhost:8000 \
AWS_ACCESS_KEY_ID=local \
AWS_SECRET_ACCESS_KEY=local \
AWS_DEFAULT_REGION=us-east-1 \
STARTER_JWT_SECRET=test-secret \
uv run pytest tests/integration -v
```

### Teardown

```bash
docker rm -f dynamo-local
```

Covers: full API endpoint behavior, OAuth authorization code flow, token refresh, token revocation.

## E2E tests

Run against the **deployed AWS stack**. Require valid Lambda Function URLs and a CloudFront URL.

### Environment variables

| Variable | Required by | Description |
|---|---|---|
| `STARTER_API_URL` | all e2e | API Lambda Function URL |
| `STARTER_UI_URL` | UI Playwright suites (when restored) | CloudFront UI URL |
| `STARTER_ADMIN_EMAIL` | admin/dashboard suites (when restored) | Admin email used by the bypass login |

All can be found in the CloudFormation stack outputs:

```bash
aws cloudformation describe-stacks --stack-name AgentCoreStarterStack-dev \
  --query 'Stacks[0].Outputs' --output table
```

### Run e2e tests

```bash
# UI / Playwright suites (when restored — requires Chromium)
uv run playwright install chromium --with-deps

# All e2e (currently only conftest fixtures; no test files yet)
uv run pytest tests/e2e -v
```

### Token management

The shared `live_admin_token` fixture in `conftest.py` issues a management
JWT via the Google auth bypass (`/auth/login?test_email=`). It skips when
`STARTER_API_URL` or `STARTER_ADMIN_EMAIL` is unset, and when the bypass
is not enabled on the target environment.

### Skip behaviour

Tests skip gracefully when the required env vars are not set — each suite
declares its own dependencies on `STARTER_API_URL`, `STARTER_UI_URL`, or
`STARTER_ADMIN_EMAIL` as appropriate.

## CI pipeline

| Job | Tests | Trigger |
|---|---|---|
| Lint & Type Check | ruff + mypy | all PRs + pushes to main |
| Unit Tests | `tests/unit/` | all PRs + pushes to main |
| Integration Tests | `tests/integration/` | all PRs + pushes to main (spins up DynamoDB Local via Docker) |
| Frontend Tests & Build | vitest + `npm run build` | all PRs + pushes to main |
| CDK Deploy | — | pushes to main only (after all CI jobs pass) |
| E2E Tests | `tests/e2e/` | pushes to main only (after CDK Deploy succeeds) |

See [../.github/workflows/ci.yml](../.github/workflows/ci.yml) for the full workflow definition.

## Test configuration

`pyproject.toml` configures pytest:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # all async tests run automatically
testpaths = ["tests"]
```

All async test functions and fixtures work without explicit `@pytest.mark.asyncio` decoration (covered by `asyncio_mode = "auto"`).
