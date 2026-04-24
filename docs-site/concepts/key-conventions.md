# Key naming conventions

Hive stores memories under a **key** you choose. The server doesn't enforce any structure on that key — any non-empty string works. But keys left to grow organically become chaotic and collision-prone fast, and renaming them later is painful once a client has thousands.

This page describes the recommended convention. It's a guideline, not a rule; adopt as much or as little as suits your agent.

## The convention

```text
{domain}:{entity-type}/{entity-id}:{attribute}
```

- **domain** — top-level namespace (e.g. `project`, `user`, `session`, `team`, `global`)
- **entity-type/entity-id** — identifies a specific thing (optional, omit for domain-wide memories)
- **attribute** — what the value contains (e.g. `summary`, `preferences`, `context`)

Lowercase, hyphens within segments, colons as separators, `/` between an entity type and its id.

## Examples

| Key | Meaning |
|---|---|
| `project:task/42:summary` | Summary of task 42 in the project domain |
| `user:profile/alice:preferences` | Alice's user preferences |
| `session:current:context` | Context for the current session |
| `team:shared:coding-guidelines` | Team-wide coding guidelines |
| `global:env:database-schema` | A globally-shared piece of context |

## Why this works

- **Collision-resistant.** Two different domains never share a key space.
- **Queryable by prefix.** Pairs well with `list_memories` and `search_memories` when you want everything under `project:task/42`.
- **Readable.** An operator browsing the Memory Browser can tell what each memory is for at a glance.
- **Extensible.** Adding a new domain or attribute never forces a rename of existing keys.

## Tips

- Prefer a fixed, small set of domains per agent — don't invent a new one for every memory.
- Keep `entity-id` stable for the life of the entity (a database id works well; a slug is fine if it never changes).
- Use `tags` for cross-cutting groupings ("decision", "open-question") rather than stuffing them into the key.
- When in doubt, start simple (`domain:attribute`) and add structure only when a real collision shows up.

## What Hive does not enforce

The server accepts any key. This convention lives in your agent's system prompt or tool-use instructions — it's your choice how strictly to follow it. Hive may introduce opt-in key validation in a future release.
