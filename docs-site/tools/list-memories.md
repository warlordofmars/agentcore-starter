# list_memories

List all memories that have a specific tag.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `tag` | string | Yes | The tag to filter by. |
| `limit` | integer | No | Maximum number of results (1–500, default 100). |
| `cursor` | string | No | Pagination cursor from a previous call. |

## Behaviour

- Returns all memories that include the specified tag, along with their keys, values, and full tag lists.
- Results are paginated — if there are more results, a `next_cursor` is returned and the caller can request the next page.

## Examples

```
List all my memories tagged "project".
```

```
Show me everything tagged "decision".
```

## Pagination

For large tag groups, the agent may make multiple calls automatically, passing the cursor to retrieve subsequent pages.

## Related tools

- [`search_memories`](/tools/search-memories) — find memories by meaning rather than tag
- [`summarize_context`](/tools/summarize-context) — get a summary of all memories on a topic
