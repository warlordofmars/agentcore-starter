# Infrastructure

AWS CDK (Python) stack that provisions all Hive resources. Defined in `stacks/hive_stack.py`.

## Resources created

| Resource | Name / ID | Notes |
|---|---|---|
| DynamoDB table | `hive` | Single-table, PAY_PER_REQUEST, PITR enabled, TTL on `ttl` attribute |
| DynamoDB GSI | `KeyIndex` | `GSI1PK` + `GSI1SK` — memory key lookups |
| DynamoDB GSI | `TagIndex` | `GSI2PK` + `GSI2SK` — list memories by tag |
| DynamoDB GSI | `ClientIndex` | `GSI3PK` — OAuth client lookups |
| Lambda | `McpFunction` | FastMCP server, Python 3.12, 512 MB, 30s timeout |
| Lambda | `ApiFunction` | FastAPI management API, Python 3.12, 512 MB, 30s timeout |
| Lambda Function URL | (MCP) | `auth=NONE`, CORS open, HTTPS only |
| Lambda Function URL | (API) | `auth=NONE`, CORS open, HTTPS only |
| S3 Bucket | `UiBucket` | Private, OAC, auto-delete on stack removal |
| CloudFront Distribution | `UiDistribution` | UI from S3, `/api/*` + `/oauth/*` → API Lambda |
| SSM Parameter | `/hive/jwt-secret` | JWT signing secret, `RETAIN` policy |
| IAM Role | `McpLambdaRole` | DynamoDB + SSM read, Lambda basic execution |
| IAM Role | `ApiLambdaRole` | DynamoDB + SSM read, Lambda basic execution |

### CloudFront routing

| Path | Origin |
|---|---|
| `/*` (default) | S3 bucket (React UI) |
| `/api/*` | API Lambda Function URL |
| `/oauth/*` | API Lambda Function URL |
| `/.well-known/*` | API Lambda Function URL |
| `/health` | API Lambda Function URL |

### Stack outputs

| Output | Description |
|---|---|
| `HiveStack.McpFunctionUrl` | MCP server URL (use in MCP client config) |
| `HiveStack.ApiFunctionUrl` | Direct API Lambda URL |
| `HiveStack.UiUrl` | CloudFront URL (use for admin UI + API) |
| `HiveStack.TableName` | DynamoDB table name |

## Lambda bundling

The Lambda package is built inside a Docker container (the Lambda Python 3.12 build image) during CDK synthesis:

1. Install `uv` via pip
2. `uv export --no-group dev --no-group infra` → `/tmp/requirements.txt` (runtime deps only)
3. `pip install -r /tmp/requirements.txt -t /asset-output`
4. `cp -r src/hive /asset-output/hive`

The `dev` and `infra` dependency groups are excluded to keep the Lambda package under the 250 MB limit.

## Initial deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 20+ (for CDK CLI)
- Docker (for Lambda bundling)
- `uv` installed

```bash
# Install CDK CLI
npm install -g aws-cdk

# Install infra dependencies
cd hive
uv sync --group dev --group infra

# Bootstrap CDK (first time only, per account/region)
cd infra
cdk bootstrap aws://<account-id>/us-east-1

# Build the UI first (CDK uploads it during deploy)
cd ../ui && npm install && npm run build && cd ../infra

# Deploy
cdk deploy
```

On first deploy, rotate the JWT secret from the placeholder value:

```bash
aws ssm put-parameter \
  --name /hive/jwt-secret \
  --value "$(openssl rand -hex 32)" \
  --overwrite
```

## CI/CD deployment (GitHub Actions)

Subsequent deployments happen automatically on push to `main`. See [../.github/workflows/ci.yml](../.github/workflows/ci.yml).

### Required GitHub secrets

| Secret | Description |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN of the OIDC IAM role for GitHub Actions |

### OIDC IAM role

The deploy job assumes `HiveGitHubActionsDeployRole` via OIDC (no long-lived access keys). The trust policy is scoped to `repo:warlordofmars/hive:environment:production`.

Required IAM permissions: CloudFormation, S3, IAM, Lambda, DynamoDB, SSM, ECR (for bundling image pull), STS.

## Useful CDK commands

```bash
cd infra

# Show what will change before deploying
cdk diff

# Deploy without approval prompts
cdk deploy --require-approval never

# Synthesize CloudFormation template
cdk synth

# Destroy the stack (DynamoDB table and SSM parameter are RETAINED)
cdk destroy
```

## Configuration

All Lambda configuration is via environment variables set in the CDK stack:

| Variable | Set by | Description |
|---|---|---|
| `HIVE_TABLE_NAME` | CDK | DynamoDB table name |
| `HIVE_ISSUER` | CDK | JWT issuer URL |
| `HIVE_JWT_SECRET_PARAM` | (optional) | SSM parameter name for JWT secret (defaults to `/hive/jwt-secret`) |
| `DYNAMODB_ENDPOINT` | (local only) | Override DynamoDB endpoint for local development |
