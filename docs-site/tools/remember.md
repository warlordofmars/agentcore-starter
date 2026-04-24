# remember

Store or update a memory.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | Yes | Unique identifier for the memory. Use a path-like convention, e.g. `project/myapp/conventions`. |
| `value` | string | Yes | The content to store. Can be any text — a sentence, a list, a JSON blob, a code snippet. |
| `tags` | list of strings | No | Tags for grouping and retrieval. A memory can have multiple tags. |

## Behaviour

- If no memory with the given `key` exists, a new memory is created.
- If a memory with that `key` already exists, it is **updated** in place (same `memory_id`, new `value` and `tags`).
- If the value and tags are identical to the existing memory, no write occurs (idempotent).
- Values larger than **100 KB** are automatically stored in S3 (`value_type="text-large"`). The promotion is transparent — you still call `remember` and `recall` as normal. See [Large memory](/concepts/large-memory) for details.

## Examples

Store a new memory:

```
Remember that our API uses JWT authentication with a 1-hour expiry.
Tag it with "project" and "auth".
```

Update an existing memory:

```
Update the memory at key "project/deadline" — the deadline has moved to April 15th.
```

## Limits

- **Value size**: up to ~100 KB stored inline; values above that are transparently promoted to S3-backed `text-large` storage, up to a maximum of **10 MB** (see [Large memory](/concepts/large-memory))
- **Tags per memory**: no hard limit, but keep it reasonable
- **Key length**: up to 512 characters

## Related tools

- [`recall`](/tools/recall) — retrieve a memory by key
- [`forget`](/tools/forget) — delete a memory
- [`remember_blob`](/tools/remember-blob) — store binary content (images, PDFs, etc.)
