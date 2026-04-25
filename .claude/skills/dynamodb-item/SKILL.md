---
name: dynamodb-item
description: Conventions for adding a new item type to the DynamoDB single-table design — PK/SK prefix taxonomy, TTL semantics, GSI naming, hour-shard pattern, and the CLAUDE.md update protocol.
status: full
triggers:
  paths:
    - "src/starter/storage.py"
    - "src/starter/models.py"
  areas: []
---

# dynamodb-item

Adding a new item type to the AgentCore Starter single-table
DynamoDB design follows a fixed set of conventions. Each is
mechanically checkable against the existing codebase; the canonical
reference is `src/starter/storage.py` (the `StarterStorage`
wrapper) plus the table definition at
`infra/stacks/starter_stack.py:84-127`.

The conventions exist because single-table design only stays
discoverable when keys are predictable. A new prefix that doesn't
match the taxonomy means future agents have to scan the whole
table to find your items.

## 1. PK/SK pattern

All keys are prefixed strings. Prefix is the entity type, suffix
is the entity identifier:

```python
PK = "USER#alice-123"        # entity type # entity id
SK = "META"                  # singleton item per entity
```

Composite SKs are allowed when an entity owns a collection of
sub-items. The SK shape orders the collection lexicographically:

```python
PK = "LOG#2026-04-25#14"     # hour-sharded partition (see §4)
SK = "1745595600#evt-abc"    # {unix_timestamp}#{event_id}
```

Two patterns to avoid:

- **Unprefixed keys.** A bare `PK="alice-123"` collides with any
  other entity that happens to share that id space. Always use the
  `TYPE#id` form.
- **Hierarchical SKs without a fixed-width prefix.**
  `SK="2026-04-25T14:00:00Z#alice"` sorts correctly only because
  ISO-8601 is lexicographic. If you mix epoch ints and ISO strings
  in the same partition, sort order breaks. Pick one per partition
  and stick to it.

## 2. Prefix taxonomy

Current item types in the single table (canonical list — keep
CLAUDE.md §"DynamoDB single table design" in sync):

| Prefix | Purpose | TTL | Notes |
| --- | --- | --- | --- |
| `CLIENT#{client_id}` | OAuth 2.1 client registration (RFC 7591) | no | `SK="META"`. Indexed by `ClientIndex` GSI on `GSI3PK`. |
| `TOKEN#{jti}` | Issued access / refresh tokens | yes | `SK="META"`. TTL drives automatic expiry of expired tokens. |
| `LOG#{date}#{hour}` | Activity log entries | no | Hour-sharded; SK is `{timestamp}#{event_id}`. See §4. |
| `AUDIT#{date}#{hour}` | Immutable compliance audit trail | yes | Hour-sharded same as `LOG#`. TTL via `STARTER_AUDIT_RETENTION_DAYS` (default 365). |
| `USER#{user_id}` | Human user records | no | `SK="META"`. Indexed by `UserEmailIndex` GSI on `GSI4PK=EMAIL#{email}`. |
| `MGMT_STATE#{state}` | OAuth state parameter for mgmt UI login | yes | `SK="META"`. Short TTL — state is single-use. |
| `EMAIL#{email}` | GSI key only (not a base PK) | n/a | Set as `GSI4PK` on `USER#` items to surface them on `UserEmailIndex`. There is no item with `PK="EMAIL#..."` — querying the GSI returns the underlying `USER#` row. |

Adding a new prefix:

1. Pick a `TYPE#id` form that doesn't collide with the table
   above.
2. Decide TTL up-front — see §3.
3. If the item needs a secondary lookup path (e.g. by email,
   by tag), pick or add a GSI per §5.
4. **Update CLAUDE.md §"DynamoDB single table design" in the
   same PR.** This is non-negotiable; the taxonomy table is the
   discovery contract for every future agent and stale entries
   silently break key derivation. See §7.

## 3. TTL semantics

The table has `time_to_live_attribute="ttl"` configured at
`infra/stacks/starter_stack.py:96`. To enable expiry on a new
item type, set the `ttl` attribute on the item.

Two rules, both enforced by `code-reviewer` check 8:

- **Attribute name is `ttl`** — lowercase, exact. The CDK
  configuration only honours that one name; setting `expires_at`
  or `TTL` is silently ignored by DynamoDB.
- **Value is a Unix timestamp integer.** Never an ISO-8601 string,
  never a `datetime` object — DynamoDB's TTL service reads
  unsigned integers and discards anything else. Compute via
  `int(time.time()) + ttl_seconds` or
  `int(expires_at.timestamp())`.

```python
import time

item = {
    "PK": f"TOKEN#{jti}",
    "SK": "META",
    "client_id": client_id,
    "scope": scope,
    "ttl": int(time.time()) + 3600,  # 1 hour from now, integer
}
```

### Retention env-var pattern

Items whose retention is configurable (audit logs are the current
example) read the retention window from a per-item env var:

```python
retention_days = int(os.environ.get("STARTER_AUDIT_RETENTION_DAYS", "365"))
ttl_value = int(time.time()) + retention_days * 86400
```

When introducing a new retention-tunable item type, follow the
same `STARTER_<ITEM>_RETENTION_DAYS` env-var naming and document
the default in CLAUDE.md alongside the prefix entry.

## 4. Hour-shard pattern for log items

`LOG#` and `AUDIT#` partition by `{date}#{hour}` — UTC date plus
zero-padded hour — to avoid hot partitions during traffic spikes.
A single date partition would funnel every event in 24 hours into
one DynamoDB partition; sharding by hour spreads writes across
24 partitions per day.

Canonical PK/SK for log-type items:

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
PK = f"LOG#{now:%Y-%m-%d}#{now:%H}"      # e.g. "LOG#2026-04-25#14"
SK = f"{int(now.timestamp())}#{event_id}"  # e.g. "1745595600#evt-abc"
```

When querying a time range, fan out: enumerate the hours in the
range and issue one `query` per partition. Don't try to scan
across hours with `begins_with(PK, "LOG#2026-04-25")` — a `Scan`
with that filter pulls every partition and defeats the shard.

Use the hour-shard pattern for any new item type that:

- Carries time-series semantics (events, requests, audit
  entries)
- Has bursty write traffic that would otherwise cluster on one
  partition

For low-volume time-series data (e.g. one event per user per
day), a daily shard is fine — pick the granularity that keeps
each partition under DynamoDB's 1000 WCU / 3000 RCU limit at
peak.

## 5. GSI naming and the GSI3PK/GSI4PK convention

The table has four GSIs defined in
`infra/stacks/starter_stack.py:99-127`. Each GSI's partition key
attribute name encodes its slot number:

| GSI | Partition key attr | Sort key attr | Purpose |
| --- | --- | --- | --- |
| `KeyIndex` (GSI1) | `GSI1PK` | `GSI1SK` | (legacy — being removed in #29) |
| `TagIndex` (GSI2) | `GSI2PK` | `GSI2SK` | (legacy — being removed in #29) |
| `ClientIndex` (GSI3) | `GSI3PK` | — | OAuth client lookups by `client_id` |
| `UserEmailIndex` (GSI4) | `GSI4PK` | — | User lookups by email (`EMAIL#{email}`) |

To put an item on a GSI, set the matching attribute on the item:

```python
# OAuth client item — also queryable on ClientIndex
item = {
    "PK": f"CLIENT#{client_id}",
    "SK": "META",
    "GSI3PK": f"CLIENT#{client_id}",
    "client_secret_hash": ...,
    ...
}
```

Conventions:

- **GSI naming.** `<Domain>Index` (PascalCase, "Index" suffix).
  Existing examples: `ClientIndex`, `UserEmailIndex`. Note that
  CLAUDE.md historically referred to `ClientIdIndex`; the actual
  CDK name is `ClientIndex`. Issue #29 tracks the reconciliation
  and the removal of the unused `KeyIndex` and `TagIndex` GSIs —
  do not add references to the legacy two indexes.
- **Sparse indexes are fine.** Items without the matching `GSIxPK`
  attribute simply do not appear on that GSI. This is the
  standard way to scope an index to a subset of item types.
- **Adding a new GSI is an infra change.** Update
  `infra/stacks/starter_stack.py` to declare the index, then add
  the storage code that writes the GSI keys. New GSI →
  per-environment migration; coordinate via a dedicated PR if
  prod data exists.

## 6. Table name source

Storage code reads the table name from the environment. The
project-specific env var is `STARTER_TABLE_NAME` (the
`STARTER_*` prefix scopes config to this template):

```python
import os

# Mirrors the StarterStorage constructor pattern documented in
# src/starter/README.md — env-driven with a sensible default for
# local dev.
table_name = os.environ.get("STARTER_TABLE_NAME", "agentcore-starter-dev")
```

Wired across the project at:

- `infra/stacks/starter_stack.py:271` — Lambda environment sets
  `STARTER_TABLE_NAME` to the per-env table name
- `tests/integration/conftest.py:21,26` — integration tests set
  the var before importing storage
- `infra/README.md` — documents the var as the storage contract

Never hardcode the table name — `code-reviewer` check 8 enforces
this. The runtime contract is `STARTER_TABLE_NAME`; CLAUDE.md
and `code-reviewer.md` use the shorter `TABLE_NAME` as a generic
shorthand, but production code and tests must read from
`STARTER_TABLE_NAME`. Code that reads only `TABLE_NAME` will fail
at runtime because the CDK stack and integration-test fixtures
do not set that alias.

The endpoint URL is also env-driven (`DYNAMODB_ENDPOINT`) so
tests point at DynamoDB Local without code changes. The
constructor pattern resolves all three at *call time*, not
import time — see `src/starter/README.md` — which keeps test
fixtures isolated from each other.

## 7. Update CLAUDE.md in the same PR

Adding a new item type means updating two places in the same PR:

1. The prefix table in CLAUDE.md §"DynamoDB single table design"
2. This skill's §2 prefix taxonomy table

Both updates ride with the storage code that introduces the new
item. The taxonomy table is the discovery contract for every
future agent — a stale entry means the next agent that adds an
item won't see your prefix and may collide with it.

If the new item type also adds a GSI or a retention env var,
extend §5 or §3 of this skill and the matching CLAUDE.md
sections in the same PR.

## 8. Anticipated: workspace_id partition (per ADR-0004 / #37)

Per ADR-0004 §inputs to #48 and the `workspace_id:user_id`
actor convention from #37, conversation and audit items are
expected to carry `workspace_id` and `user_id` columns once the
workspace primitive lands. The likely shape is:

```python
# anticipated — lock in once #37 ships
item = {
    "PK": f"AUDIT#{date}#{hour}",
    "SK": f"{timestamp}#{event_id}",
    "workspace_id": "ws-...",
    "user_id": "usr-...",
    "actor_id": f"{workspace_id}:{user_id}",  # composite for cross-workspace queries
    ...
}
```

**Status: anticipated, not active.** Don't add `workspace_id`
columns to existing item types in advance — wait for #37 to land
and update this skill's §8 plus CLAUDE.md once the convention is
real.

## See also

- [`example.py`](./example.py) — copy-pasteable item shape for a
  new prefix, covering PK/SK, TTL, GSI keys, and the table-name
  resolution pattern.
- CLAUDE.md §"DynamoDB single table design" — current prefix
  taxonomy (must stay in sync with §2 above).
- `infra/stacks/starter_stack.py:84-127` — table + GSI
  definitions.
- `.claude/agents/code-reviewer.md` §8 — review-time enforcement
  of the conventions above.
- ADR-0004 §inputs to #48 — workspace_id partition rationale
  (`docs/adr/0004-agentcore-runtime-feasibility.md`).
- Issue #29 — GSI reconciliation (`ClientIdIndex` vs
  `ClientIndex`, removal of `KeyIndex` / `TagIndex`).
