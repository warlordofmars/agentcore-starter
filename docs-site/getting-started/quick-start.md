# Quick start

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- AWS CLI configured with credentials
- AWS CDK v2 (`npm install -g aws-cdk`)

## Deploy

```bash
# Install dependencies
uv sync

# Bootstrap CDK (first time only)
cd infra && cdk bootstrap -c account=YOUR_ACCOUNT_ID -c env=dev

# Deploy to dev
uv run inv deploy --env dev
```

## Run locally

```bash
# Start all services (DynamoDB Local, API, UI)
uv run inv dev
```

Open `http://localhost:5173` and sign in with the bypass URL:
`http://localhost:5173?test_email=you@example.com`
