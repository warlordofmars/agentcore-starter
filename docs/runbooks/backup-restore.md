# Backup & restore runbook

How to recover Hive's DynamoDB data when something has gone catastrophically
wrong. Read this before you need it.

## When to use this

- **Data corruption** — bad code wrote bad data; recent state is wrong.
- **Accidental delete** — `inv` task or admin script wiped real data.
- **Ransomware / hostile actor** — attacker scrubbed or encrypted the table.
- **Region failure** — `us-east-1` is unavailable and won't be back soon.

If the issue is *latency*, *errors*, or *one bad record*, this runbook is
overkill — see `docs/alarms.md` first.

## What you have to work with

- DynamoDB **Point-in-time recovery** (PITR) is enabled on the prod
  `hive` table (`infra/stacks/hive_stack.py` →
  `point_in_time_recovery_enabled=is_prod`). PITR retains a continuous
  recovery window of **35 days**.
- A weekly restore drill (`.github/workflows/backup-test.yml`) PITR-restores
  to a temp table, validates row count > 0, deletes the temp table. If
  it fails, an issue with `reliability` label is opened automatically.
- `inv export` / `inv import` produce JSONL dumps for ad-hoc backups —
  use when you need a portable copy outside AWS.

## Pre-flight (≤ 10 min)

1. **Notify** — drop a note in the ops channel. State the symptom and an
   ETA for next status update (15 min is reasonable; resist
   under-promising).
2. **Freeze writes** to limit blast radius:

   ```bash
   aws lambda put-function-concurrency \
     --function-name hive-mcp-fn \
     --reserved-concurrent-executions 0
   aws lambda put-function-concurrency \
     --function-name hive-api-fn \
     --reserved-concurrent-executions 0
   ```

   This 200's all incoming requests with throttling but keeps the
   stack intact — operators and admins can still inspect via the AWS
   console.
3. **Capture the symptom.** Screenshot the dashboard, save a sample of
   the bad data, copy any error stack traces. You'll want this for the
   post-mortem.

## PITR restore

1. **Pick the restore time.** Aim for the latest moment *before* the
   corruption. PITR resolution is one second.

   ```bash
   # Example: restore to the state at 13:42 UTC today
   RESTORE_TIME=2026-04-18T13:42:00Z
   ```

2. **Restore to a new table.** Never restore in-place — you want the
   bad table preserved for forensics.

   ```bash
   RESTORE_TABLE=hive-restore-$(date -u +%Y%m%d-%H%M)
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name hive \
     --target-table-name "$RESTORE_TABLE" \
     --restore-date-time "$RESTORE_TIME"
   ```

   If you can't pick a precise moment, use `--use-latest-restorable-time`
   instead of `--restore-date-time`.

3. **Wait for `ACTIVE`.** Restores take 5–30 min depending on table size.

   ```bash
   aws dynamodb wait table-exists --table-name "$RESTORE_TABLE"
   aws dynamodb describe-table --table-name "$RESTORE_TABLE" \
     --query 'Table.TableStatus' --output text
   # Expect: ACTIVE
   ```

4. **Spot-check the restored data.** Run a few targeted queries to
   confirm the bad data is gone and the good data is back.

   ```bash
   # Example: pull a memory you know existed before the incident
   aws dynamodb get-item --table-name "$RESTORE_TABLE" \
     --key '{"PK": {"S": "MEMORY#known-id"}, "SK": {"S": "META"}}'
   ```

## Swap procedure

The Lambda environment variable `HIVE_TABLE_NAME` controls which table
the app reads/writes. Swap it to the restored table.

1. **Update CDK** — set the table name override in
   `infra/stacks/hive_stack.py` (or temporarily via Lambda env var).
   Cleanest path is a one-line CDK change + redeploy:

   ```python
   # Temporary override — reset after data is migrated back
   table_name = "hive-restore-20260418-1342"  # was: "hive"
   ```

2. **Deploy:**

   ```bash
   uv run inv deploy --env prod
   ```

3. **Lift the write freeze** by setting concurrency back to its prior
   value (or removing the limit):

   ```bash
   aws lambda delete-function-concurrency --function-name hive-mcp-fn
   aws lambda delete-function-concurrency --function-name hive-api-fn
   ```

## Validation

1. **Smoke-test the API:**

   ```bash
   curl -s https://hive.warlordofmars.net/health
   # Expect: 200 OK
   ```

2. **Smoke-test MCP tools** with a known-good token:

   ```bash
   # Set $TOKEN to a working API key
   curl -s -X POST https://hive.warlordofmars.net/mcp \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ping"}}'
   # Expect: "result": {"content": [{"text": "ok"}]}
   ```

3. **Watch CloudWatch.** The CloudFront 5xx, MCP/API error-rate, and
   DDB throttle alarms should all stay quiet for at least 15 minutes
   after the swap. See `docs/alarms.md` for what each one means.

4. **Verify a real user flow.** Sign in to the management UI and
   confirm your memories appear, you can `recall` one, and the
   activity log shows recent events.

## Cleanup (24–48 h after restore)

Don't rush this — the original table is your evidence and your
fallback if the restore turns out to be incomplete.

1. **Migrate any writes** that hit the restored table back to a
   permanent table named `hive` (the original convention). Easiest
   path: rename the restored table by exporting + reimporting under
   the canonical name, then update the Lambda env back to `"hive"`.
2. **Delete the corrupt table** *only after* the restore has been
   running cleanly for at least 24 h:

   ```bash
   aws dynamodb delete-table --table-name hive  # the corrupt one
   ```

   (If the rename in step 1 already used the `hive` name, this means
   deleting the temp table whose data you migrated out of.)
3. **Re-enable PITR** on the new permanent table — it isn't
   automatically inherited from the source on restore:

   ```bash
   aws dynamodb update-continuous-backups \
     --table-name hive \
     --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
   ```

   In CDK this is the `point_in_time_recovery_enabled=is_prod`
   parameter; redeploying after the rename should re-apply it
   automatically.

## Post-mortem

After the dust settles, file a follow-up issue (label `reliability`)
with:

- **Timeline** — when corruption started, when noticed, when restored,
  when validated.
- **Root cause** — what wrote the bad data; what (if anything) failed
  to catch it.
- **Customer impact** — how many users affected, what they saw,
  whether anyone needs to be notified directly.
- **Action items** — what to add to the test suite, the alarm set,
  the runbook, or the deploy gate so this is harder to do again.

A template file lives at `docs/runbooks/postmortem-template.md` (TODO
— file alongside this runbook in a follow-up).

## Annual restore drill

Restoring under pressure is the wrong time to discover that the
runbook drifted. Once a year (calendar reminder for the operator),
follow this entire runbook end-to-end against a non-prod environment:

- File a tracking issue: `chore: annual restore drill — 20YY`.
- Run through every step. Time each one.
- Update this runbook for anything that was unclear, missing, or
  changed. CDK / API surface drift is the common culprit.
- Close the tracking issue with a short summary (drill duration,
  things to fix, follow-up issues filed).

## Related

- `docs/alarms.md` — CloudWatch alarms that surface backup/restore
  health.
- `.github/workflows/backup-test.yml` — weekly automated PITR
  restore + validation.
- `infra/stacks/hive_stack.py` — DynamoDB table and PITR config.
