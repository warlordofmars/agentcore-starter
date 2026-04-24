# search_memories

Search memories by semantic similarity to a natural language query.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | string | Yes | A natural language description of what you're looking for. |
| `top_k` | integer | No | Maximum number of results (1–50, default 10). |

## Behaviour

- Converts your query to a vector embedding and finds the most semantically similar memories.
- Results are ranked by relevance (`score` from 0.0 to 1.0, higher = more relevant).
- Returns up to `top_k` results — there is no pagination.
- Returns an empty list if no memories have been stored yet.

## Examples

```
Search my memories for anything about authentication.
```

```
Find memories related to the database schema.
```

```
What have I stored about project deadlines?
```

## How it differs from recall and list_memories

| Tool | Use when |
| --- | --- |
| `recall` | You know the **exact key** |
| `list_memories` | You want everything with a specific **tag** |
| `search_memories` | You remember roughly **what** it was about but not the key or tag |

## Related tools

- [`recall`](/tools/recall) — retrieve a memory by exact key
- [`list_memories`](/tools/list-memories) — list by tag
