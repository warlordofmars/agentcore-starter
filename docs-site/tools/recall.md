# recall

Retrieve a memory by its exact key.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | Yes | The exact key of the memory to retrieve. |

## Behaviour

- Returns the `value` string stored under the given key.
- Raises an error if no memory with that key exists.

## Examples

```
What's the API deadline we agreed on?
```
→ agent calls `recall("project/deadline")`

```
Recall the memory at key "preferences/code-style".
```

## When to use vs. search_memories

Use `recall` when you know the **exact key**. If you only remember roughly what something was about, use [`search_memories`](/tools/search-memories) instead.

## Related tools

- [`remember`](/tools/remember) — store or update a memory
- [`search_memories`](/tools/search-memories) — find memories by meaning
