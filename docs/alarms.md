# Alarm runbook

Hive ships with a set of CloudWatch alarms that page the operator via SNS
when something goes wrong. This page lists every alarm, what it means,
and the first things to check when it fires.

## First-deploy: subscribing to alerts

On the first deploy of a new environment, the SNS topic exists but has
**no subscribers**. Alarms fire into the void until you subscribe.

1. Set the alarm-recipient email in SSM:

   ```bash
   aws ssm put-parameter \
     --name /hive/prod/alarm-email \
     --value "you@example.com" \
     --type String \
     --overwrite
   ```

2. Subscribe the SNS topic to that email:

   ```bash
   EMAIL=$(aws ssm get-parameter --name /hive/prod/alarm-email \
             --query 'Parameter.Value' --output text)
   TOPIC_ARN=$(aws cloudformation describe-stack-resource \
                 --stack-name HiveStack \
                 --logical-resource-id AlarmTopic \
                 --query 'StackResourceDetail.PhysicalResourceId' \
                 --output text)
   aws sns subscribe \
     --topic-arn "$TOPIC_ARN" \
     --protocol email \
     --notification-endpoint "$EMAIL"
   ```

3. Confirm the subscription from the confirmation email AWS sends.

Every alarm wires both `alarm_action` and `ok_action` to the same topic,
so you'll get both "firing" and "recovered" emails.

## Alarms

### `Hive-{env}-McpErrorRate` / `Hive-{env}-ApiErrorRate`

Fires when **Lambda error rate exceeds 5 %** for 2 of 3 × 5-minute windows.

First checks:

- Recent deploys in `#deploys` and on the `development`/`main` CI runs — any
  failure you missed?
- `Dashboard → MCP/API Lambda → Invocations & Errors` chart — is it a spike
  or sustained?
- `aws logs tail /aws/lambda/hive-mcp-fn` (or `-api-fn`) — read the most
  recent stack trace.

### `Hive-{env}-McpP99Duration`

MCP Lambda p99 latency > 25 s over 2 × 5 min. **Timeout canary** — if this
fires we're very close to the 30 s Lambda cutoff.

First checks:

- DynamoDB throttles (`Hive-{env}-DdbThrottles`). Throttles + slow Lambda
  usually move together.
- S3 Vectors health — semantic search is the slowest call in `remember`.
- Any recent change to `hive.storage` or `vector_store` that could hot-
  path a new scan.

### `Hive-{env}-McpP95Latency`

MCP p95 > 2000 ms over a 1-hour window. **SLO breach** — slower than what
we promise to users. Usually a leading indicator for `McpP99Duration`.

### `Hive-{env}-McpThrottles` / `Hive-{env}-ApiThrottles`

Any Lambda throttle in a 5-minute window. Reserved concurrency may be too
low, or a noisy client is hammering one endpoint.

First checks:

- `aws lambda get-function-concurrency --function-name <fn>` — does it
  match the expected config?
- Identify the client via `/api/activity?limit=200` — is one `client_id`
  dominating?
- If sustained: temporarily raise reserved concurrency and open a ticket
  to investigate.

### `Hive-{env}-DdbThrottles`

Any DynamoDB throttle in 5 min. We're pay-per-request so this shouldn't
happen unless we're hot-partitioning (all traffic to one `PK`).

First checks:

- `AWS/DynamoDB` → `ReadThrottleEvents` + `WriteThrottleEvents` per
  `TableName` — which op is throttling?
- Activity log: is there a bug writing many items to one `PK` (the
  `LOG#{date}#{hour}` partition is the most common offender — see
  `storage.py` sharding comment).

### `Hive-{env}-DdbUserErrors`

> 10 `AWS/DynamoDB` `UserErrors` in 5 min. Conditional-check failures,
ValidationException, etc.

First checks:

- Tail the Lambda log for `botocore.exceptions.ClientError` — which
  item / condition is failing?
- `ConditionalCheckFailed` is expected for optimistic writes; a spike
  usually means concurrent writers to the same key.
- Schema mismatch after a migration? Check the latest CloudFormation
  deploy diff.

### `Hive-{env}-CloudFront5xx`

CloudFront 5xx rate > 1 % over 5 min. Upstream Lambda is likely the
cause; check the MCP/API error alarms first.

### `Hive-{env}-ToolErrors`

Custom `Hive/ToolErrors` EMF metric exceeds 10 in 5 min for 2 of 3
windows. Fires when MCP tools return `ToolError` (quota, size limit,
storage error).

First checks:

- Which `operation` dimension is spiking? (Dashboard → Custom metrics).
- `remember` spikes are usually quota or size-limit hits — check
  `check_memory_quota` + `HIVE_MAX_VALUE_BYTES`.
- `recall` / `forget` spikes are usually "not found" — a client using
  stale keys.

### `Hive-{env}-StorageLatencyHigh`

`Hive/StorageLatencyMs` p99 > 2000 ms for 2 × 5 min. DynamoDB's own slow
path (not Lambda overhead).

First checks:

- Paginated tag queries (`list_memories`, `forget_all`) — large tags can
  sweep many pages.
- Vector store `upsert_memory` failures that cause `put_memory` to retry.

### `Hive-{env}-AuthFailures`

Bearer token rejections (`Hive/TokenValidationFailures`) > 10 in 5 min
for 2 of 3 windows.

First checks:

- One client that just rotated its key and hasn't updated the config?
- Credential leak — scan recent activity for unusual client IDs / IP
  ranges (see `api/logs` CloudWatch log viewer).
- If sustained and multi-client, consider temporarily tightening WAF
  rate limits.

### `Hive-{env}-McpFastBurn` / `McpSlowBurn` / `ApiFastBurn` / `ApiSlowBurn`

SLO burn-rate alarms. Fast burn = 5× error budget over 1 hour, slow burn
= 2× over 6 hours. See [Google SRE workbook — burn-rate alerts](
https://sre.google/workbook/alerting-on-slos/) for the methodology.

Treat these like the plain error-rate alarms but with more urgency — they
mean the error budget will run out within hours if nothing changes.

## Adding a new alarm

1. Declare the `cw.Alarm` in `infra/stacks/hive_stack.py`.
2. Call `_notify(alarm)` to wire both alarm + OK actions in prod.
3. Add it to the dashboard (`HiveDashboard` widgets) so it's visible
   even when it isn't firing.
4. Add an entry to this runbook.
