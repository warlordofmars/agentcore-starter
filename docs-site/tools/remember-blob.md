# remember_blob

Store a binary memory — an image, document, audio file, or any other non-text content.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | Yes | Unique identifier for the memory. Same path-like convention as [`remember`](/tools/remember). |
| `data` | string | Yes | Standard Base64-encoded bytes of the binary content. |
| `content_type` | string | Yes | MIME type of the content, e.g. `image/png`, `application/pdf`. |
| `tags` | list of strings | No | Tags for grouping and retrieval. |

## Behaviour

- Content is stored in S3; only metadata is written to DynamoDB.
- If `content_type` starts with `image/` (e.g. `image/png`, `image/jpeg`, `image/webp`), the memory gets `value_type="image"`.
- All other MIME types produce `value_type="blob"`.
- Calling `remember_blob` with the same key again **replaces** the existing binary content (upsert semantics, same `memory_id`).
- The `data` payload (after Base64 decoding) must not exceed **10 MB**.

## Examples

Store a PNG screenshot:

```
Store this screenshot as a memory with key "project/myapp/ui-screenshot".
Tag it "project" and "screenshot".
```

Store a PDF document:

```
Save this architecture PDF as "project/myapp/architecture-doc" with tag "docs".
```

## Limits

| Limit | Value |
| --- | --- |
| Maximum payload (decoded bytes) | 10 MB |
| Supported MIME types | Any non-empty string (typically a MIME type such as `image/png`) |
| Key length | Up to 512 characters |

## Retrieval

Use [`recall`](/tools/recall) to retrieve a binary memory. For both `value_type="image"` and `value_type="blob"`, the tool returns an MCP `ImageContent` block whose `data` contains the Base64-encoded bytes and whose `mimeType` is set from the stored `content_type`. Non-image blobs (e.g. PDFs, audio) are still returned as `ImageContent` with `type="image"`; client implementations must use `mimeType` to determine the actual content type and must not assume the payload is an image.

Binary memories are not embedded, so they generally won't appear in semantic search (`search_memories`) results — retrieve them by key or tag only.

## Related tools

- [`remember`](/tools/remember) — store text (handles large text transparently via S3)
- [`recall`](/tools/recall) — retrieve any memory by key
- [`list_memories`](/tools/list-memories) — list memories by tag (shows metadata for binary memories)
