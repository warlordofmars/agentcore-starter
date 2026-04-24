# summarize_context

Retrieve all memories related to a topic and return a synthesised summary.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `topic` | string | Yes | The topic or tag to summarise. Matches memories by tag. |

## Behaviour

- Retrieves all memories tagged with the given topic (up to 500).
- Returns a formatted summary listing each memory, followed by an overview paragraph.
- Returns a "no memories found" message if no memories are tagged with that topic.

## Examples

```
Summarise everything I have stored about the project.
```
→ agent calls `summarize_context("project")`

```
Give me a context dump on the auth system before I start working on it.
```
→ agent calls `summarize_context("auth")`

## When to use

Use `summarize_context` at the start of a session when you want a quick overview of everything relevant to a topic, rather than recalling individual memories one by one.

## Related tools

- [`list_memories`](/tools/list-memories) — list individual memories by tag
- [`search_memories`](/tools/search-memories) — find memories by meaning
