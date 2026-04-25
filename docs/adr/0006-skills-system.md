# ADR-0006: Skills system for agent-loaded reference material
Date: 2026-04-25  
Status: Accepted

## Context

Two pieces of project knowledge already live alongside the agents
under `.claude/`:

- **CLAUDE.md** — always-on conventions every agent invocation needs
  (label taxonomy, copyright headers, PR workflow, product decisions).
  ~574 lines, ~23K characters, loaded into every conversation.
- **`.claude/agents/*.md`** — agent definitions describing *how* a
  specialist works (lifecycle, tool envelope, halt conditions).

A third category has surfaced repeatedly during the autonomous
issue cycle and is currently re-derived by the model on every
relevant invocation: **task-shaped reference material** — the
recipe for adding a FastAPI route, the single-table key pattern
for a new DynamoDB item type, the convention for writing an
ADR. This material is not always-on (the next issue may touch a
React component, not a route) and is not agent-behaviour (any
agent benefits — `issue-worker`, `code-reviewer`, future
specialists). Adding it to CLAUDE.md would bloat every
conversation with content most invocations do not need.

The autonomous loop has crossed the threshold where this
re-derivation friction is observable rather than hypothetical
(see #62 rationale). Six skills are already filed for the first
wave (#64–#67, #69, #72) plus stubs for surfaces that depend on
in-flight work (#48 partition, AgentCore Runtime integration).

This ADR settles the format and discovery contract before any
skill is written, so subsequent skill PRs inherit the pattern
cheaply and the autonomous agent can trust it.

## Decision

Adopt a **load-on-demand, frontmatter-routed** skills system
rooted at `.claude/skills/`. Each skill is a single directory
containing a `SKILL.md` entrypoint with a prescriptive YAML
frontmatter schema. Agents scan skill frontmatter at a defined
lifecycle point, match against the current issue context, and
inline matching skill bodies into their working context. Skill
content is never always-on.

### Skill file layout

- One directory per skill: `.claude/skills/<skill-name>/`
- Entrypoint: `<skill-name>/SKILL.md` — required, agents only
  read this file during discovery
- Supporting files (examples, fixtures) may live alongside in
  the same directory; the skill body links to them as needed
- Skill name in the directory matches the `name:` field in
  frontmatter

### Frontmatter schema (prescriptive, mechanically checkable)

Every `SKILL.md` MUST declare these fields:

```yaml
---
name: <skill-name>           # matches directory name; kebab-case
description: <one-line>      # surfaced when an agent considers loading
status: full | stub          # honest signal of coverage; stubs have ## Gaps
triggers:
  paths:                     # glob list; may be empty []
    - "<glob>"
  areas:                     # area-label list; may be empty []
    - "<area>"
---
```

`triggers.paths` and `triggers.areas` may each be empty, but at
least one trigger entry must exist across the two — a skill that
declares no triggers can never load and is invalid.

The schema is closed. Skills MUST NOT add a `load: always` field
or any other mechanism that bypasses match-time loading — the
context-window budget only works if every skill obeys the
load-on-demand rule.

### Discovery trigger — hybrid OR-semantics

An agent loads a skill when **any** of:

- The current issue's diff (or predicted diff scope, when the
  diff does not yet exist) intersects any glob in
  `triggers.paths`
- The current issue carries any label listed in
  `triggers.areas`

OR-semantics is permissive on purpose. False-positive cost is
~5KB of extra context for one un-needed skill; false-negative
cost is "the skill exists but never loads when it should." The
former is recoverable per-invocation; the latter degrades the
system silently.

When the diff does not yet exist (e.g. `issue-worker` running
before implementation), match `triggers.paths` against the
issue body's "Files to touch" section, augmented by area labels
and title heuristics. The prediction is best-effort;
load-on-demand cost of false positives is small enough that
aggressive matching is preferred to under-coverage.

Match logic lives **in the skill's frontmatter**, not in the
agent files. Routing rules are decentralized so a contributor
reading `<skill-name>/SKILL.md` sees both what the skill teaches
and when it applies. Centralizing match logic in
`issue-worker.md` / `code-reviewer.md` would scatter the
contract across files and force two-place edits whenever a
skill's scope changes.

### Loading mechanism — eager-load at match time

Sequence executed by each consuming agent:

1. Glob `.claude/skills/*/SKILL.md`
2. Parse each skill's frontmatter
3. Compute matches against current issue context (diff or
   predicted scope + labels)
4. Read the body of every matched skill into working context
   before the agent's primary task begins
5. The agent's primary task (implementation, review) runs with
   skills inlined alongside CLAUDE.md

One pass, deterministic, no LLM-driven retrieval. The pass
costs one glob and N small reads — negligible relative to the
issue cycle.

### Relationship to CLAUDE.md

The line is **frequency of applicability**:

- **CLAUDE.md** — content that benefits every issue (label
  taxonomy, copyright headers, PR workflow, product decisions)
- **Skills** — content that benefits a specific kind of issue
  (FastAPI route recipe, DynamoDB single-table key pattern,
  ADR writing convention)

When in doubt: if removing the content would degrade *every*
agent invocation, it belongs in CLAUDE.md; if it would only
degrade invocations of a particular shape, it belongs in a
skill. CLAUDE.md does not shrink as part of this ADR — but new
conventions filed after this lands should default to the
skill side of the line and only graduate to CLAUDE.md if the
"every issue" test holds.

### Threshold for adding a new skill

Soft rule, document in the skills README:

- Friction noticed twice → file an issue under the skills epic
  (or its successor)
- Friction noticed three times → write the skill

Stricter enforcement (counting mechanism, automated detection)
would calcify too early. The soft rule matches how product
decisions emerged in CLAUDE.md.

### Stub skill convention

A skill MAY ship as `status: stub` when its surface depends on
in-flight work that is not yet ready (e.g. `cdk-construct`
needs partition #48; `bedrock-agent` needs Runtime integration).
Stubs participate fully in discovery — same frontmatter, same
triggers — but their body MUST contain a `## Gaps` section.

Each gap entry MUST use this structure:

````markdown
### <gap title>

- **What's missing:** <one line>
- **Why deferred:** <one line>
- **Unblocks when:** #<issue> [optional brief context]
````

Without this prescribed format, stubs degrade into
wishful-thinking documents that pretend coverage they do not
have. With it, stubs are honest scaffolding that points the
autonomous agent at real follow-up work, and the format is
mechanically checkable by the future `skill-format-validator`
CI job.

### Agent integration — identical scan, role-specific consumption

`issue-worker` and `code-reviewer` run the same match step
against the same frontmatter schema. Divergence is in *how*
the loaded body is consumed:

- `issue-worker` reads matched skills as **implementation
  guidance** during step §1.5 (between Understand and Branch),
  using the issue body to predict diff scope
- `code-reviewer` reads matched skills as a **convention
  checklist source** in a new `## Skill discovery` section
  between `## Invocation` and `## Checklist`, matching against
  the actual diff (more precise than `issue-worker`'s
  prediction since the diff exists)

Single source of truth for skill format; no per-agent skill
subset. Future agents that consume skills (e.g. `docs-sync`)
inherit the same scan logic when their lifecycle warrants it.

### Context-window discipline

Always-on loading is the wrong default. CLAUDE.md is already
~23K characters in every conversation; six skills at ~150
lines each would compound that to ~5K extra lines per
invocation regardless of relevance. Match-time scanning costs
one glob per agent invocation (~50ms). The wrong default is
permanent; the cheap scan is per-call. Load-on-demand is
locked, and the frontmatter schema's prohibition of
`load: always` enforces the discipline mechanically.

## Alternatives considered

**(a) Single flat `.claude/skills/<skill-name>.md` (no
directory).** Tighter today, but forces a rename and
restructure as soon as the first skill needs supporting
material (example code, fixture data). Directory-per-skill
costs nothing extra now and avoids the future churn.

**(b) Always-on skills inlined into CLAUDE.md or a
sibling.** Rejected. Every always-loaded skill compounds
context cost across all conversations regardless of
relevance, and CLAUDE.md is already substantial. The whole
point of the system is that task-shaped reference material
does not belong in always-on memory.

**(c) Centralized routing in agent files (agent declares
which skills apply to which work).** Rejected. Scatters the
"when does this skill apply" contract across two agent
files; doubles the edit cost when a skill's scope changes;
hides the trigger from a contributor reading the skill
directly. Skill-side routing keeps each skill
self-contained and inspectable.

**(d) AND-semantics for triggers (skill must match both
path and area).** Rejected. Too many real cases match one
side only — a chore issue touching API code carries `dx`
not `api`; a label-only issue may not yet have a diff.
False-negative cost (skill silently doesn't load) is worse
than false-positive cost (one extra ~5KB skill in context).

## Consequences

- **Skills become the default home for new task-shaped
  reference material.** New conventions filed after this ADR
  default to a skill; CLAUDE.md additions need to clear the
  "every issue benefits" bar. The product-decisions section
  of CLAUDE.md remains the canonical home for durable
  architectural decisions, not skills.

- **Six skill issues become unblocked.** #64–#67, #69, #72
  all carry `Blocked by #63`. Once this lands they enter the
  ready queue. #69 and #72 land as stubs per the contract
  above; #64–#67 land as `status: full`.

- **Agent-file changes ship in this PR, not later.** Adding
  the scan step retroactively after skills exist would mean
  a window in which skills are written but not consumed.
  Bundling the foundation prevents that drift.

- **The `Skill` tool is not the loading mechanism.** Claude
  Code's runtime `Skill` tool surfaces skills via the CLI
  harness; this template's discovery runs inside subagents
  via file reads. The two systems do not share runtime —
  this ADR's contract governs only the in-repo
  `.claude/skills/` directory consumed by this template's
  agent definitions.

- **PR is not `agent-safe`.** Touches `.claude/agents/*.md`
  which control autonomous-agent behaviour. Same human-review
  policy as ADR-0005's orchestrator definition. An LLM-only
  review is insufficient because a regression in the scan
  step (e.g. matching too aggressively) would silently bloat
  every issue cycle's context.

- **Future work — `skill-format-validator` CI check.** A
  CI job that validates every `SKILL.md` against the
  frontmatter schema, rejects skills declaring always-on
  loading, and verifies stubs have a non-empty `## Gaps`
  section meeting the three-line contract. Trivial to write
  once the schema is locked, and prevents drift as the
  catalogue grows. Out of scope for this PR — file when the
  first wave of full skills lands and the schema has
  survived contact with real authors. Same shape as
  ADR-0005's "teach issue-worker about the bootstrap halt
  list" follow-up.

- **Future work — `docs-sync` skill consumption.** When
  `docs-sync` next runs against changed agent or
  documentation surfaces, teach it the same scan step. Out
  of scope here; the bottleneck is `issue-worker` and
  `code-reviewer` first.

- **No production code changes.** Like ADR-0004 and
  ADR-0005, this ADR ships docs + agent-definition updates
  only. Behaviour changes manifest the next time an agent
  runs against an issue whose triggers match a written skill.
