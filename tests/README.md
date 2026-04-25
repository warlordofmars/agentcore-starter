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
    ├── conftest.py        # live_token fixture (DCR + PKCE)
    ├── test_auth_e2e.py
    └── test_ui_e2e.py     # Playwright
```

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
| `STARTER_UI_URL` | `test_ui_e2e.py` | CloudFront UI URL |

All can be found in the CloudFormation stack outputs:

```bash
aws cloudformation describe-stacks --stack-name AgentCoreStarterStack-dev \
  --query 'Stacks[0].Outputs' --output table
```

### Run e2e tests

```bash
# Auth tests
uv run pytest tests/e2e/test_auth_e2e.py -v

# UI tests (Playwright — requires Chromium)
uv run playwright install chromium --with-deps
uv run pytest tests/e2e/test_ui_e2e.py -v

# All e2e
uv run pytest tests/e2e -v
```

### Token management

E2E tests **self-issue tokens** via the `live_token` fixture in `conftest.py`. It performs a full DCR + PKCE flow against `STARTER_API_URL` at session start — no pre-issued token needed.

### Skip behaviour

Tests skip gracefully when the required env vars are not set:
- `test_auth_e2e.py` — skips if `STARTER_API_URL` unset
- `test_ui_e2e.py` — skips if `STARTER_UI_URL` unset

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
