# Backup & restore runbook

How to recover AgentCore Starter's DynamoDB data when something has gone catastrophically wrong. Read this before you need it.

## When to use this

- **Data corruption** — bad code wrote bad data; recent state is wrong.
- **Accidental delete** — `inv` task or admin script wiped real data.
- **Ransomware / hostile actor** — attacker scrubbed or encrypted the table.
- **Region failure** — `us-east-1` is unavailable and won't be back soon.

If the issue is *latency*, *errors*, or *one bad record*, this runbook is overkill — check CloudWatch alarms first.

## What you have to work with

- DynamoDB **Point-in-time recovery** (PITR) is enabled on the prod table (`infra/stacks/starter_stack.py` → `point_in_time_recovery_enabled=is_prod`). PITR retains a continuous recovery window of **35 days**.
- A weekly restore drill (`.github/workflows/backup-test.yml`) PITR-restores to a temp table, validates row count > 0, deletes the temp table. If it fails, an issue with `reliability` label is opened automatically.
- `inv export` / `inv import` produce JSONL dumps for ad-hoc backups — use when you need a portable copy outside AWS.

## Pre-flight (≤ 10 min)

1. **Notify** — drop a note in the ops channel. State the symptom and an ETA for next status update (15 min is reasonable; resist under-promising).
2. **Freeze writes** to limit blast radius:

   ```bash
   aws lambda put-function-concurrency \
     --function-name agentcore-starter-api-fn \
     --reserved-concurrent-executions 0
   ```

   This 200's all incoming requests with throttling but keeps the stack intact — operators and admins can still inspect via the AWS console.
3. **Capture the symptom.** Screenshot the dashboard, save a sample of the bad data, copy any error stack traces. You'll want this for the post-mortem.

## PITR restore

1. **Pick the restore time.** Aim for the latest moment *before* the corruption. PITR resolution is one second.

   ```bash
   # Example: restore to the state at 13:42 UTC today
   RESTORE_TIME=2026-04-18T13:42:00Z
   SOURCE_TABLE=agentcore-starter-prod
   ```

2. **Restore to a new table.** Never restore in-place — you want the bad table preserved for forensics.

   ```bash
   RESTORE_TABLE=agentcore-starter-restore-$(date -u +%Y%m%d-%H%M)
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name "$SOURCE_TABLE" \
     --target-table-name "$RESTORE_TABLE" \
     --restore-date-time "$RESTORE_TIME"
   ```

   If you can't pick a precise moment, use `--use-latest-restorable-time` instead of `--restore-date-time`.

3. **Wait for `ACTIVE`.** Restores take 5–30 min depending on table size.

   ```bash
   aws dynamodb wait table-exists --table-name "$RESTORE_TABLE"
   aws dynamodb describe-table --table-name "$RESTORE_TABLE" \
     --query 'Table.TableStatus' --output text
   # Expect: ACTIVE
   ```

4. **Spot-check the restored data.** Run a few targeted queries to confirm the bad data is gone and the good data is back.

   ```bash
   aws dynamodb get-item --table-name "$RESTORE_TABLE" \
     --key '{"PK": {"S": "USER#known-id"}, "SK": {"S": "META"}}'
   ```

## Swap procedure

The Lambda environment variable `STARTER_TABLE_NAME` controls which table the app reads/writes. Swap it to the restored table.

1. **Update CDK** — set the table name override in `infra/stacks/starter_stack.py`. Cleanest path is a one-line CDK change + redeploy:

   ```python
   # Temporary override — reset after data is migrated back
   table_name = "agentcore-starter-restore-20260418-1342"
   ```

2. **Deploy:**

   ```bash
   uv run inv deploy --env prod
   ```

3. **Lift the write freeze** by removing the concurrency limit:

   ```bash
   aws lambda delete-function-concurrency --function-name agentcore-starter-api-fn
   ```

## Validation

1. **Smoke-test the API:**

   ```bash
   curl -s https://<your-domain>/health
   # Expect: 200 OK
   ```

2. **Watch CloudWatch.** The CloudFront 5xx, API error-rate, and DDB throttle alarms should all stay quiet for at least 15 minutes after the swap.

3. **Verify a real user flow.** Sign in to the management UI and confirm users appear and the activity log shows recent events.

## Cleanup (24–48 h after restore)

Don't rush this — the original table is your evidence and your fallback if the restore turns out to be incomplete.

1. **Migrate any writes** that hit the restored table back to a permanent table with the canonical name (`agentcore-starter-prod`). Easiest path: export + reimport under the canonical name, then update the Lambda env back.
2. **Delete the corrupt table** *only after* the restore has been running cleanly for at least 24 h:

   ```bash
   aws dynamodb delete-table --table-name "$SOURCE_TABLE"  # the corrupt one
   ```

3. **Re-enable PITR** on the new permanent table — it isn't automatically inherited from the source on restore:

   ```bash
   aws dynamodb update-continuous-backups \
     --table-name agentcore-starter-prod \
     --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
   ```

   In CDK this is the `point_in_time_recovery_enabled=is_prod` parameter; redeploying after the rename should re-apply it automatically.

## Post-mortem

After the dust settles, file a follow-up issue (label `reliability`) with:

- **Timeline** — when corruption started, when noticed, when restored, when validated.
- **Root cause** — what wrote the bad data; what (if anything) failed to catch it.
- **Customer impact** — how many users affected, what they saw, whether anyone needs to be notified directly.
- **Action items** — what to add to the test suite, the alarm set, the runbook, or the deploy gate so this is harder to do again.

## Annual restore drill

Restoring under pressure is the wrong time to discover that the runbook drifted. Once a year (calendar reminder for the operator), follow this entire runbook end-to-end against a non-prod environment:

- File a tracking issue: `chore: annual restore drill — 20YY`.
- Run through every step. Time each one.
- Update this runbook for anything that was unclear, missing, or changed.
- Close the tracking issue with a short summary (drill duration, things to fix, follow-up issues filed).

## Related

- `.github/workflows/backup-test.yml` — weekly automated PITR restore + validation.
- `infra/stacks/starter_stack.py` — DynamoDB table and PITR config.
