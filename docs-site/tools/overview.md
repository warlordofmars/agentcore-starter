# MCP tools overview

Hive exposes MCP tools that your AI agent can call during a conversation. You don't invoke these directly — your agent decides when to use them based on your instructions.

## Tool summary

| Tool | What it does |
| --- | --- |
| [`remember`](/tools/remember) | Store or update a memory |
| [`recall`](/tools/recall) | Retrieve a memory by its key |
| [`forget`](/tools/forget) | Delete a memory by its key |
| [`list_memories`](/tools/list-memories) | List all memories with a given tag |
| [`search_memories`](/tools/search-memories) | Search memories by semantic similarity |
| [`summarize_context`](/tools/summarize-context) | Summarise all memories on a topic |
| [`pack_context`](/tools/pack-context) | Token-budget-aware context pack for agents |

## Scopes

OAuth tokens may carry `memories:read` and/or `memories:write`. Each scope grants the tools listed below; `ping` is the one tool that needs only a valid Bearer token.

| Scope | Grants access to |
| --- | --- |
| `memories:read` | `recall`, `list_memories`, `list_tags`, `memory_history`, `relate_memories`, `search_memories`, `summarize_context`, `pack_context` |
| `memories:write` | `remember`, `remember_if_absent`, `forget`, `forget_all`, `redact_memory`, `restore_memory` |
| _(none required)_ | `ping` — health check, requires only a valid Bearer token |

Tokens issued through the standard OAuth flow get both scopes by default.

## How your agent uses the tools

You typically don't need to tell your agent which tool to use — just give natural language instructions:

- *"Remember that..."* → `remember`
- *"What did we decide about...?"* → `recall` or `search_memories`
- *"List everything tagged..."* → `list_memories`
- *"Forget the..."* → `forget`
- *"Give me a summary of..."* → `summarize_context`
- *"Fill my remaining context window with..."* → `pack_context`

## Progress notifications

Tools whose expected duration exceeds ~2 seconds emit MCP [`notifications/progress`](https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress) events at each major stage of work. Supporting clients (Claude Desktop, Claude Code) render these as a progress indicator or streaming status line.

Currently emitted by:

- `search_memories` — reports at 3 stages (vector search → hydrate → rank)
- `summarize_context` — reports at 2 stages (retrieve → synthesise)

Clients that don't support progress notifications ignore them — the tool still returns its normal final result. Emission is best-effort: if the transport rejects a notification, the tool continues without raising.
