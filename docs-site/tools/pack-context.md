# `pack_context`

Retrieve as many relevant memories as fit within a token budget, ordered for usefulness, returned as a ready-to-paste markdown block.

`pack_context` is the token-aware counterpart to [`search_memories`](/tools/search-memories) and [`list_memories`](/tools/list-memories). Use it when your agent wants **"fill my remaining context window with the most useful memories about X"** — not top-K, not every memory with a tag, but "as much as will fit".

## Signature

```python
pack_context(
    topic: str,
    budget_tokens: int = 2000,       # 1 – 100_000
    ordering: str = "relevance+recency",
) -> str
```

| Argument | Default | Notes |
| --- | --- | --- |
| `topic` | — | Search query / subject to retrieve context for |
| `budget_tokens` | `2000` | Upper bound on the response token count |
| `ordering` | `"relevance+recency"` | One of `relevance`, `recency`, or `relevance+recency` |

The tool returns a single markdown-formatted string; the agent can drop it straight into its working context.

## How it works

1. Hybrid vector search finds the top ~50 candidate memories for `topic` (same retrieval backbone as `search_memories`)
2. Candidates are re-ranked by the chosen `ordering` strategy
3. Each candidate is token-estimated (4 chars ≈ 1 token — conservative, no `tiktoken` dependency)
4. The tool greedily packs memories into the budget, **skipping** any individual memory too big for the remaining budget rather than truncating it
5. The packed result is rendered as markdown with a summary header

## Output shape

```
## Context for 'release process' (8 memories, ~1847 tokens)

- **release/cadence**: Weekly on Thursdays at 2pm UTC
- **release/back-merge**: main → development immediately after every prod deploy
- **release/smoke-tests**: Playwright suite runs against dev after each deploy
- ...
```

## Ordering modes

| Mode | Picks by |
| --- | --- |
| `relevance` | Pure semantic similarity to `topic`. Useful when recency doesn't matter. |
| `recency` | Pure exponential decay on `last_accessed_at` / `updated_at`. Useful for "what did I touch recently about X". |
| `relevance+recency` | Weighted blend (default, matches `search_memories`). Recommended for most callers. |

## Why not do this client-side

- The agent doesn't know how expensive each memory is without fetching them all first — a single packing tool avoids the N+1 round-trip
- Token-aware truncation logic belongs where memory metadata is cheap to inspect
- Centralising it means every MCP client benefits equally

## Example workflow

An agent asked to summarise what it knows about a feature:

```
user: What do we know about the stats tab?

agent (internally):
  → pack_context(topic="stats tab", budget_tokens=1500)
  ← ## Context for 'stats tab' (6 memories, ~1423 tokens)
    - **stats/scaffolding**: Endpoint at /api/account/stats...
    - **stats/activity-heatmap**: GitHub-style 7×N grid with...
    ...

agent (response):
  The stats tab is a React SPA surface backed by /api/account/stats...
```

The agent's response is grounded in the packed memories, not its base training data.

## Edge cases

- **Budget smaller than any single memory** — returns an empty block with an explanatory note; the agent can retry with a higher budget.
- **Vector index unavailable** — returns an empty block silently (matches `search_memories`'s non-fatal behaviour).
- **Redacted memories** — always excluded; there is intentionally no `include_redacted` override.
- **`budget_tokens` out of range** — clamps to `[1, 100_000]` server-side.
