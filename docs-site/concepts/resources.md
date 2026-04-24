# MCP Resources

Alongside its [tools](/tools/overview) and [prompts](/tools/prompts), Hive exposes memories as **MCP Resources** — read-only, URI-addressable content that supporting clients can reference declaratively without a tool round-trip.

::: tip Tool vs Resource vs Prompt
- A **[Tool](/tools/overview)** is something the agent *calls*. It does work and returns a JSON response.
- A **Resource** is *content* the agent can read by URI. Clients can pre-fetch or cache it.
- A **[Prompt](/tools/prompts)** is a *template* the client surfaces as a slash command.
:::

## URI scheme

| URI | What it returns |
| --- | --- |
| `memory://_index` | A newline-separated list of every `memory://{key}` URI the authenticated client owns. The leading underscore is a reserved namespace — a user can still store a memory with the literal key `index` and read it via `memory://index`. |
| `memory://{key}` | The value of one specific memory |

All reads are scoped to the authenticated OAuth client (`client_id`) and require the `memories:read` scope. The token flows through the same `Authorization: Bearer <token>` header as the tools — nothing new to configure.

## Reading the index first

Resources are listed in two places:

- `resources/list` returns the concrete `memory://_index` resource
- `resources/templates/list` returns the template `memory://{key}`

Clients typically read `memory://_index` first to discover what's available. Keys that contain `/` or `:` are [percent-encoded](https://datatracker.ietf.org/doc/html/rfc3986#section-2.1) so each URI is parseable by standard URI tooling and round-trips losslessly:

```
memory://release-cadence
memory://release-back-merge
memory://release%2Fsmoke-tests
```

(The third example shows a key `release/smoke-tests` with the `/` encoded as `%2F`. Clients should always read the URI verbatim from the index rather than reconstructing it — that's the only way to guarantee an exact match for the read.)

Then read a specific entry:

```
memory://release-cadence
→ "Weekly on Thursdays at 2pm UTC"
```

## Why resources, not just tools

- **Lower latency** — clients can cache resources and stream them into context without a round-trip through the model
- **Declarative referencing** — the agent can point at `memory://release-cadence` in a prompt instead of calling a tool and pasting the response
- **MCP primitive alignment** — using the full primitive set (tools, resources, prompts) lets Hive slot into any compliant client without custom client glue

## Tenant isolation

Resource reads enforce tenant isolation at the handler level:

- `memory://{key}` returns "not found" (not "forbidden") when the key belongs to another OAuth client, so the existence of another tenant's keys never leaks
- `memory://_index` only enumerates memories owned by the authenticated client — other tenants' keys never appear

## Redacted memories

Memories that have been tombstoned via the `redact_memory` tool are excluded from the index and reject `memory://{key}` reads with an explicit "redacted" error. The error distinguishes a redacted memory from a missing one so client UIs can surface the right message.

## Truncation

`memory://_index` caps at the first 500 entries (sorted alphabetically). Redacted and expired memories are filtered out of the rendered body, so the visible URI count is often smaller than the cap. When the cap triggers, the body ends with a note directing the agent to fall back to the [`list_memories`](/tools/list-memories) tool for narrower retrieval — tags are the right primitive for large corpora.

## Writes still go through tools

Resources are intentionally read-only. Storing, updating, and deleting memories continues to go through [`remember`](/tools/remember) / [`forget`](/tools/forget) plus the `redact_memory` tool (advertised via `tools/list` on supported clients). Centralising writes in one place keeps the quota, TTL, version, and audit-log machinery in a single code path.

## Client support

Resources only appear in clients that implement the MCP Resources capability:

- **Claude Code** — lists resources in the MCP panel
- **Claude Desktop** — shows resources under connected servers
- **Cursor** — lists resources in the MCP resources menu

Clients that don't support Resources can still reach every memory via the tool surface; nothing breaks.
