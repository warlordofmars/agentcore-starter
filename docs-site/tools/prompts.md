# MCP Prompts

Hive ships four MCP **Prompts** — pre-built, parameterised templates that supported clients (Claude Code, Cursor) surface as slash commands. Prompts let you kick off a Hive workflow with one keystroke instead of asking your agent to pick a tool name.

::: tip What's the difference between a Tool and a Prompt?
A [Tool](/tools/overview) is something the agent *calls* — a function with a JSON response. A Prompt is a template the *client* surfaces to the user; the user picks it, the client sends the rendered template to the agent, and the agent then calls the appropriate tool. Tools do work; Prompts route you to the right tool.
:::

## Available prompts

| Prompt | Arguments | What it does |
| --- | --- | --- |
| `/recall-context` | `topic` | Summarises everything Hive knows about `topic` and makes the agent use it as foreground context. |
| `/what-do-you-know-about` | `query` | Runs a semantic search and weaves the top hits into the agent's next response. |
| `/remember-this` | `key`, `value`, `tags` (optional) | Stores the current selection under `key`, tagged if you provide comma-separated tags. |
| `/forget-older-than` | `days` | Enumerates memories older than `days` and interactively asks you to confirm each deletion. |

## `/recall-context`

Pulls in everything Hive already knows about a subject so the agent can answer follow-up questions from that context.

**Example**

```
/recall-context topic="the billing rewrite"
```

The agent calls `summarize_context(topic='the billing rewrite')` and uses the returned summary as its working context. If no memories match, the agent tells you so rather than hallucinating.

## `/what-do-you-know-about`

Semantic search across your memories; handy when you remember a concept but not a specific key.

**Example**

```
/what-do-you-know-about query="our stance on Redis"
```

Runs `search_memories(query='our stance on Redis', top_k=10)` and cites each result by memory key.

## `/remember-this`

Stores a memory without you having to say "remember that…" in prose. Most clients default `value` to the current editor selection.

**Example**

```
/remember-this key="release-cadence" value="Weekly, Thursdays at 2pm UTC" tags="ops,release"
```

Tags are comma-separated; blank entries are trimmed. If you omit tags the memory is still stored — the template always passes `tags=[]` to the `remember` tool so the argument never drifts.

## `/forget-older-than`

Interactive prune using only Hive's actual MCP tools: the agent calls `list_tags`, walks each tag with `list_memories(tag)`, and compares every memory's `last_accessed_at` to the threshold. If `last_accessed_at` is null (memory written but never recalled), the agent falls back to the `version` timestamp — a UTC ISO string that updates on every write and is always present in the response. The agent shows the key + the timestamp it used and asks for per-memory confirmation before calling `forget`.

**Example**

```
/forget-older-than days=180
```

The template explicitly forbids batch-delete without confirmation, so even if the agent returns many stale memories you stay in control.

## Client support

Prompts only appear in clients that implement the MCP Prompts capability:

- **Claude Code** — surfaces prompts in the slash-command menu when Hive is connected.
- **Cursor** — shows prompts under the MCP panel.
- **Claude Desktop** — lists prompts alongside tools in the connector picker.

Clients that don't support Prompts ignore them — nothing breaks. You can still invoke the underlying tools directly by asking the agent in prose.

## Why we ship Prompts

- **Lower friction.** "What does Hive know about X?" takes one slash command, not a sentence of natural language that the agent has to parse.
- **Consistent invocation.** The template passes the right tool name and parameters every time, so agents never forget to set `top_k` or `tags`.
- **Discoverable.** Connect Hive, type `/`, and see everything Hive can do for you — no need to read docs first.
