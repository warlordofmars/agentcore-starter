# ADR-0005: Orchestrator agent for cross-session sequencing and delegation
Date: 2026-04-25  
Status: Accepted

## Context

Prior to this ADR, this template shipped eight specialist agents under
`.claude/agents/`: `issue-worker`, `design-review`, `backlog-manager`,
`code-reviewer`, `docs-sync`, `security-auditor`, `incident-responder`,
and `onboarding`. Each owned a tightly-scoped workflow. None owned the
layer above them — the sequencing of in-flight work, the resolution of
human directives against live state, the cross-session continuity that
lets autonomous loops actually loop.

That orchestration role has been performed by an external Claude session
(`chat.anthropic.com`) during the `chat-app-ready` milestone push. It works,
but with observable friction:

- **Stale issue numbers in prompts.** External Claude works from
  conversation memory, not live repo state. Issue numbers have been crossed
  multiple times across the milestone (`#33` referenced as the dead-code
  sweep when it is the streaming test, etc). `issue-worker` caught the
  mismatches by reading bodies, not by trusting numbers — robust, but the
  friction shouldn't be there.
- **Cross-session state has to be reconstructed every invocation.**
  Which spike is where, which PR is awaiting review, which template-bootstrap
  failures are tracked — all rebuilt from human messages each time.
- **Delegation requires copy-paste.** No in-repo path that says "delegate
  this to `issue-worker` with this context" — the human ferries prompts
  between sessions.
- **Recurring patterns get re-explained.** "Halt without filing duplicates
  when the post-merge SonarCloud step fails — that's a tracked
  template-bootstrap gap" must be re-stated each session because there is
  nothing in the repo that codifies it.

The chat-app fork (Channel) will lean heavily on autonomous workflows.
Closing the orchestration loop before the fork is `chat-app-ready`
infrastructure work even though it didn't make the original 34-issue
planning pass.

## Findings

The friction is fundamentally a **freshness problem**, not a missing-data
problem. Repo state is rich enough today to drive every sequencing decision
the external Claude has been making:

- `gh issue list` returns labels, milestone, assignees, and body in one call
- Open PRs carry `Closes #N` body markers identifying the issue they will
  close on merge — sufficient to compute "what's in flight"
- `Blocked by #N` body markers on issues, mirrored in the `status:blocked`
  label, identify dependency chains
- The bootstrap-pattern epic (#56) collects template-bootstrap gaps via
  `Part of #56` body markers on each instance (currently #50, #54, #55) —
  a durable, auto-detectable halt list
- `gh run list --branch development` returns post-merge pipeline state

The `.autonomous-progress` convention used by `issue-worker` to resume
interrupted batches (a runtime-written file at the repo root, not
committed — see `.claude/agents/issue-worker.md`) demonstrates that
in-repo persistence works at the right scale when it is genuinely
needed. Orchestration sequencing is not that scale — every input is
already in `gh`.

## Decision

Add a new `.claude/agents/orchestrator.md` agent that:

- Reads live repo state on every invocation (`gh issue list`, `gh pr list`,
  `gh run list`) before making any decision. No working from memory.
- Accepts named, mechanical directives — `status`, `work next <filter>`,
  `delegate <#N> to <agent>`, `check #N`, `brief #N`, `epic #N` — and
  resolves them against the live state.
- Delegates to specialists via the `Agent` tool with the right context
  pre-assembled. Never implements work itself, never files issues
  directly, never modifies other agents' definitions.
- Halts cleanly on directive ambiguity, unresolved `Blocked by`, the
  bootstrap-pattern halt list (auto-detected via `Part of #56` body
  markers), a red post-merge pipeline, or any work that would require
  changing CLAUDE.md product decisions.
- Reports a structured cross-session state snapshot (in flight / merged /
  blocked / next pick / halts) on every invocation so any human picking up
  the loop has the same view the previous session had.

**State mechanism: live queries only, no persistent store.** The friction
this agent solves is the staleness of memory-derived state; introducing a
new persistence layer would replicate the same failure mode in a new place.
Repo state is the source of truth, `gh` is fast, and the existing
`.autonomous-progress` pattern shows that in-repo persistence is acceptable
when (and only when) live queries cannot answer the question — which is
not the case here.

**Tool envelope: read-and-delegate only.** `Bash, Read, Glob, Grep, Agent,
AskUserQuestion`. No `Edit`, no `Write`. The agent cannot modify code,
cannot file issues directly, and cannot rewrite other agents — this is
enforced by the tool list, not by convention alone.

**`work next <filter>` proposes, does not auto-fire.** It picks an issue,
prints the prompt that would go to `issue-worker`, and halts for human
confirmation. Auto-delegation is deferred until the picker is trusted in
practice. Consistent with the current "review the prompt before pasting"
pattern in the chat-app-ready loop.

## Alternatives considered

**(a) Session log file committed each invocation
(`.claude/orchestrator-log.md` or similar).** Rejected. Records what the
last session saw, not what is true now. Drift risk: the file says "PR #N is
awaiting review" but the PR has merged and the issue has closed. Every
multi-step orchestration becomes a question of "log or live?" — the agent
ends up doing the live query anyway and the log becomes redundant
overhead. Partial-write hazards on a crashed session add a recovery surface
this template doesn't need.

**(b) Hive MCP memory (the user's personal MCP memory server).** Rejected.
Hive is per-user, not per-project. Coupling the template's orchestration
loop to a specific user's MCP server would mean adopters either provision
their own Hive (overhead) or run a degraded loop (worse). The template
ships agents; agents should not depend on per-user infrastructure that
isn't in the repo. Staleness risk persists regardless.

**(c) No persistent state, live queries only.** Chosen. Source of truth is
repo state. Every invocation pays a sub-second `gh` query and gets a fresh
view. No drift, no merge conflicts, no per-user dependency. This frames
orchestration as a pure function of repo state plus the directive — exactly
the property the friction observations are asking for.

## Consequences

- **Orchestrator becomes the canonical entry point for autonomous loops.**
  Future autonomous work — `chat-app-ready` finishing, the chat-app fork's
  release cadence, periodic security/docs sweeps — should be initiated
  through the orchestrator rather than directly invoking `issue-worker` or
  the other specialists. Direct invocation remains supported; orchestrator
  is additive.

- **Explicit non-overlap with `issue-worker`.** Orchestrator picks and
  hands off; `issue-worker` drives the implement → PR → CI → review
  cycle. The mental model is "orchestrator is the conductor, issue-worker
  is the player." Their tool envelopes reflect this: orchestrator cannot
  edit code; issue-worker cannot delegate to other agents through the
  orchestrator (it can call `code-reviewer` directly per its existing
  protocol).

- **Bootstrap-pattern halts use a durable marker, not a hardcoded list.**
  The halt list is computed each invocation by querying for open issues
  with `Part of #56` in their body. New bootstrap-pattern instances filed
  in future automatically join the halt list when their body cites the
  epic. This sidesteps the drift mode where a hardcoded list goes stale as
  the epic evolves, and matches how the chat-app-ready milestone has been
  using `Part of #N` markers throughout.

- **`status:design-needed` on issue #59 is satisfied by this ADR.**
  Normally `design-review` posts a decisions comment and flips the label
  before implementation. For this issue, the design is captured here — in
  ADR-0005 — and the implementation lands in the same PR. Design-review's
  decisions comment + label flip handoff is intentionally bypassed for
  cross-cutting agent infrastructure where the design rationale belongs in
  an ADR rather than an issue comment.

- **The PR is not `agent-safe`.** Agent definitions are load-bearing
  infrastructure for autonomous workflows. Even though the change is
  docs-only, an LLM-only review is insufficient — a regression in
  orchestrator's halt conditions could let the autonomous loop pile merges
  onto a broken pipeline or skip past a tracked bootstrap gap. Human
  review is required for this and any future change to the orchestrator
  definition.

- **Future work — teach `issue-worker` about the bootstrap-pattern halt
  list.** `issue-worker`'s post-merge pipeline-watch (step 8) currently
  emits `HUMAN_INPUT_REQUIRED: development pipeline failed` on a SonarCloud
  or AWS-deploy failure without recognising these as tracked under
  epic #56. Orchestrator recognises them; teaching `issue-worker` to do
  the same would let it self-halt rather than escalate. Out of scope for
  this ADR — file as a follow-up issue when the friction surfaces in
  practice.

- **Future work — standardise an inter-agent halt-sentinel format.** The
  existing agents emit `HUMAN_INPUT_REQUIRED:` strings inconsistently
  (some always, some never). A uniform structured sentinel —
  `HALT: <category> | <reason> | <evidence>` — would let orchestrator
  consume specialist outputs programmatically and chain agent calls more
  cleanly. Out of scope for this ADR — capture as a follow-up if
  orchestrator-driven chaining becomes a primary use case.

- **CLAUDE.md gets one new line in the agent ecosystem section.**
  Registration only; no rule changes. Orchestrator does not modify any
  product decision, label rule, milestone rule, or PR workflow already
  documented in CLAUDE.md.

- **No production code changes.** Like ADR-0004, this ADR is paired with
  documentation deliverables only. Behaviour changes manifest only when a
  human invokes the new agent.
