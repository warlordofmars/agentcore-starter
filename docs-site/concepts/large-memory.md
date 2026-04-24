# Large memory — text, images, and blobs

Hive stores three kinds of non-standard memory alongside ordinary inline text. Understanding the distinction helps you choose the right tool and set accurate expectations for retrieval behaviour.

## Memory value types

| `value_type` | Stored where | How it arrives | Max size |
| --- | --- | --- | --- |
| `text` | DynamoDB (inline) | `remember` with a short value | ~100 KB |
| `text-large` | S3 (auto-promoted) | `remember` with a long value | 10 MB |
| `image` | S3 | `remember_blob` with an `image/*` MIME type | 10 MB |
| `blob` | S3 | `remember_blob` with any other MIME type | 10 MB |

## Inline threshold — when text spills to S3

When you call `remember` with a text value, Hive checks the encoded byte length against a 100 KB threshold:

- **≤ 100 KB** — stored inline in DynamoDB as `value_type="text"`. `recall` stays DynamoDB-only and does not fetch from S3.
- **> 100 KB** — stored in S3 as `value_type="text-large"`. The DynamoDB item holds metadata only; the value is fetched from S3 when you `recall` the key.

The promotion to `text-large` is **transparent**: you call `remember` and `recall` exactly as before. The only observable differences are:

- `list_memories` returns an empty `value` string for `text-large` memories (the inline value is cleared on S3 promotion; use `recall` to fetch the full content).
- Retrieval adds a small S3 latency (~50–200 ms) on top of the DynamoDB read.

## Binary memories — images and blobs

Use [`remember_blob`](/tools/remember-blob) to store images, PDFs, audio, or any other binary content. Pass the bytes as standard Base64 and specify a MIME type.

Hive routes by MIME prefix:

- `image/*` (e.g. `image/png`, `image/jpeg`) → `value_type="image"`
- Everything else (e.g. `application/pdf`, `audio/mpeg`) → `value_type="blob"`

Both subtypes are stored in S3. A binary memory has no inline `value` — the management UI and `recall` fetch the bytes directly from S3.

## Semantic search

Semantic search (via `search_memories`) operates on **text embeddings**:

| `value_type` | Embedded? | Notes |
| --- | --- | --- |
| `text` | Yes | Full inline value is embedded |
| `text-large` | Yes | Large text is embedded; full S3 value is not fetched for list/search previews |
| `image` | No | Binary content is not embedded |
| `blob` | No | Binary content is not embedded |

`text-large` memories can appear in semantic search results. Binary memories (`image` and `blob`) are excluded from semantic search. For large text, `search_memories` and `list_memories` return an empty `value` string; use `recall` to fetch the complete content by key.

## Size limits summary

| Limit | Value |
| --- | --- |
| Inline text threshold (auto S3 promotion) | 100 KB |
| Maximum text value (`remember`, including S3-promoted) | 10 MB |
| Maximum binary payload (`remember_blob`) | 10 MB |
| DynamoDB item ceiling (hard) | 400 KB |

## Related pages

- [`remember`](/tools/remember) — store text memories (handles text-large transparently)
- [`remember_blob`](/tools/remember-blob) — store binary content
- [`recall`](/tools/recall) — retrieve any memory by key
- [Memory Browser](/ui-guide/memory-browser) — view and download large memories in the UI
