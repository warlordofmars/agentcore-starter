# Quotas and rate limits

Every Hive tool response carries the caller's current quota usage and rate-limit configuration under a top-level `_meta.hive` block. Well-behaved agents can read this to self-throttle before they hit a hard limit.

## Response shape

Every MCP tool call returns metadata alongside the usual result:

```json
{
  "content": [...],
  "structuredContent": {...},
  "_meta": {
    "hive": {
      "memory_quota": {
        "used": 42,
        "limit": 500,
        "remaining": 458
      },
      "rate_limit": {
        "per_minute_limit": 60,
        "per_day_limit": 10000
      }
    }
  }
}
```

The `_meta.hive` block is present on **every** Hive tool response, including error-adjacent paths like "no memories found" or vector-index-missing.

## Fields

### `memory_quota`

| Field | Type | Meaning |
| --- | --- | --- |
| `used` | int | Number of memories currently owned by the caller's user |
| `limit` | int | Hard cap on memories per user (default 500) |
| `remaining` | int | `max(0, limit - used)` |

When `remaining` hits zero, the next `remember` call for a new key will raise a `ToolError` with a quota-exceeded message. Updates to existing memories do not consume quota.

### `rate_limit`

| Field | Type | Meaning |
| --- | --- | --- |
| `per_minute_limit` | int | Maximum tool calls per minute per client (default 60) |
| `per_day_limit` | int | Maximum tool calls per day per client (default 10000) |

The rate-limit block reports the configured limits, not the caller's remaining budget. Current consumption isn't returned because it would cost extra DynamoDB reads on every response. If you hit the limit, the next call raises a `ToolError` with a `Retry after Ns` hint.

## Use cases

- **Self-throttling agents** — back off proactively when `memory_quota.remaining` falls below a threshold, rather than waiting for a hard error
- **Fleet dashboards** — aggregate `used` across clients to visualise per-user usage without hitting the management API
- **Write-planning** — an agent about to store a batch of memories can check `remaining` and pick which ones to keep if the batch would overflow

## Overrides

Both quota and rate limits are configurable via environment variables on the Hive server:

- `HIVE_QUOTA_MAX_MEMORIES` — memory quota per user
- `HIVE_QUOTA_EXEMPT_USERS` — comma-separated user IDs that skip the memory quota check
- `HIVE_RATE_LIMIT_RPM` — per-minute rate limit
- `HIVE_RATE_LIMIT_RPD` — per-day rate limit

Exempt users still receive the metadata block — the `limit` and `remaining` values reflect the baseline config, not the bypass.
