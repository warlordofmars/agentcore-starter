# forget

Delete a memory by its key.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | Yes | The exact key of the memory to delete. |

## Behaviour

- Permanently deletes the memory with the given key.
- Raises an error if no memory with that key exists.
- Deletion is **irreversible** — there is no trash or undo.

## Examples

```
Forget the memory about the old database URL — we've migrated.
```
→ agent calls `forget("project/old-db-url")`

```
Delete everything we stored about the cancelled feature.
```
→ agent may call `forget` for each relevant key, or use [`list_memories`](/tools/list-memories) first to find them.

## Related tools

- [`remember`](/tools/remember) — store or update a memory
- [`list_memories`](/tools/list-memories) — list memories by tag to find keys to delete
