# ADR-0007: Codify orchestrator protocols surfaced during skills epic
Date: 2026-04-25  
Status: Accepted

## Context

The orchestrator agent (ADR-0005, `.claude/agents/orchestrator.md`)
landed in PR #61 and saw its first real workload during the skills
epic (#62, ADR-0006). The epic spanned seven sub-issues — foundation
(#63), four full skills (#64–#67), two stubs (#69, #72) — giving the
orchestrator the first sustained autonomous workflow it had ever
sequenced.

The retrospective Phase 5 observations log captured 12 protocol
gaps (G1–G12) plus several positive patterns. The orchestrator
improvised correctly each time — but improvisation is precisely
the failure mode ADR-0005 was designed to prevent. ADR-0005's
thesis is that orchestrator behaviour is a pure function of
state + directive; every undocumented judgement call is a place
where two invocations on the same state can diverge.

Without codification, the patterns persist only in the Phase 5
observations log and the model's working memory of one specific
session. The next workflow re-derives them from zero. This ADR
captures them in the agent file directly so subsequent invocations
inherit the protocol vocabulary without re-derivation.

## Decision

Decision rests on ADR-0005's purity thesis: orchestrator behaviour
is a pure function of state + directive, so the **default
codification mode is hard rule unless ≥95% mechanical correctness
fails**. Soft rules erode the thesis whenever the underlying
pattern is actually mechanical — every "judgement call" hedge
becomes a place where two invocations on the same state can
diverge.

### Codify G1–G11 as named protocols in `orchestrator.md`

Eleven protocols from the Phase 5 observations log become named
sections in the agent definition. G6 is preserved as a numbering
placeholder; mechanical scope-boundary enforcement is being
designed under #77 and would land there, not here. The gap in
the G-numbering is intentional so retrospective references to
the Phase 5 log resolve cleanly.

| Gap | Section in `orchestrator.md` |
|---|---|
| G1 — Surface verbs | New `## Surface verbs` H2 |
| G2 — Sub-agent IDs / SendMessage handling | Subsection under existing `## Delegation patterns` |
| G3 — Halt-before-merge modified cycle | New `## Halt-before-merge` H2 |
| G4 — Small-fix-on-open-PR decision tree | Subsection under new `## Plan-vs-act` H2 (originally landed as `## Delegate-vs-act`; renamed in PR #140 — see Consequences) |
| G5 — Conflict-of-interest verification | Subsection under new `## Verification protocols` H2 |
| G6 — Mechanical scope-boundary enforcement | Deferred to #77; placeholder in `## Note on numbering` |
| G7 — Plan-vs-act (originally Delegate-vs-act, renamed in PR #140) | New `## Plan-vs-act` H2 (originally landed as `## Delegate-vs-act`; renamed in PR #140 — see Consequences) |
| G8 — Epic-close housekeeping | New `## Epic-close housekeeping` H2 |
| G9 — Content-driven section inclusion | New `## Guidelines` H2 |
| G10 — Empirical reasoning over rule-letter | New `## Guidelines` H2 (shared with G9) |
| G11 — Round-trip verification | Subsection under new `## Verification protocols` H2 |

### Split positive patterns: hard rules vs guidelines

| Pattern | Classification | Rationale |
|---|---|---|
| Atomic delegation (close + file in one brief, never split across messages) | Hard rule | Mechanical |
| Bundled-PR-as-default (ADR + agent-definition share-decision → one PR) | Hard rule | Mechanical with a documented "explicit reason" override |
| Stub closing paragraph discipline (header + frontmatter `status: stub` + `## Gaps` + `## Follow-up`) | Hard rule | Mechanical shape, matches ADR-0006's stub contract |
| Content-driven section inclusion (G9) | Guideline | "Real content" is judgement-defined |
| Empirical reasoning over rule-letter (G10) | Guideline | Intent inference is judgement |

The two AC2-mandated H2s (`## Hard rules` and `## Guidelines`)
make the split visible in the agent file itself, not just in
this ADR.

## Alternatives considered

**(a) Codify all observations as guidelines.** Rejected. The
≥95% mechanical correctness criterion settles this directly:
soft-rules erode the ADR-0005 purity thesis whenever the
underlying pattern is actually mechanical, which three of the
five positive patterns are (atomic delegation,
bundled-PR-as-default, stub closing paragraph discipline).
Demoting them to guidelines would invite post-hoc rationalised
divergence on the next similar invocation. Hard rules with
explicit "deviation requires explicit reason" escape hatches
preserve the thesis without being brittle.

**(b) Inline G-codes into existing sections without dedicated
headings.** Rejected. The G-numbering is the durable handle for
retrospective investigation — Phase 5 observations log references
"G3", future retrospectives will reference these protocols by
number. Burying them inside generic sections like `## Halt
conditions` makes them ungrep-able when a future workflow needs
to locate "the G7 plan-vs-act protocol" (or "delegate-vs-act" — the original H2 name; renamed in PR #140). Dedicated H2s cost
~50 lines of TOC weight and earn it back the first time a
retrospective resolves cleanly.

**(c) Split into per-protocol ADRs.** Rejected. All eleven gaps
trace back to the same Phase 5 source and share the same
ADR-0005 purity thesis as their justification. Splitting would
force eleven small ADRs with identical Context sections and
duplicate the bundling overhead of ADR-0005 + #61 across each.
One ADR with a placement table is cheaper and matches ADR-0006's
precedent of a single ADR settling a multi-part contract.

## Consequences

- **PR is not `agent-safe`.** Modifies an agent definition. Same
  human-review policy as ADR-0005 (orchestrator definition) and
  ADR-0006 (skills foundation). LLM-only review is insufficient —
  a regression in the new halt-before-merge protocol could let
  the autonomous loop merge precedent-setting work without
  surfacing it for human review.

- **Bundled PR shape.** ADR-0007 + orchestrator.md revisions ship
  in a single PR. Same shape as #59 (ADR-0005 + orchestrator
  definition) and #73 (ADR-0006 + agent wiring). Splitting would
  separate the design rationale from the concrete consumption,
  inviting drift and forcing a follow-up PR to be reviewed against
  partial context.

- **G3 halt-before-merge validation lands post-merge.** AC3
  requires the next precedent-setting orchestrator invocation
  after this PR to trigger the G3 protocol — surfacing complete
  content inline before any merge fires. Validation is recorded
  by linking the invocation log in the resolution PR's body.
  Issue #48 (CDK construct partition) is the most plausible
  next precedent-setter — it introduces the `infra/constructs/`
  convention from scratch and unblocks the `cdk-construct` skill
  stub. Issue #49 (admin rebuild) is a backup if #48's
  design-review breakdown reorders the queue.

- **G6 deferral preserves Phase 5 numbering alignment.** The gap
  in the G-numbering is intentional. Phase 5 observations log
  references "G6" for mechanical scope-boundary enforcement;
  renumbering G7–G11 to close the gap would break those references
  and force every future retrospective citation to disambiguate.
  #77 will land G6 as part of agent-safe scope-enforcement
  machinery.

- **Out-of-scope follow-up filed separately.** G13–G15 (orchestrator
  pre-delegation scope brief; bundled-PR-as-default-as-protocol-not-pattern;
  stub-skill discipline as numbered rule) and the `brief #N`
  `Replaces #N` enhancement are deferred to a follow-up issue
  filed via `backlog-manager` against the `chat-app-ready` milestone.
  Adding them mid-design pushes #82 from `size:m` to `size:l`.

- **Future work — orchestrator-output validator.** Once the protocol
  vocabulary stabilises (after the first cycle of G3 validation,
  G4 small-fix decisions, G5 conflict-of-interest invocations),
  a mechanical validator parallel to ADR-0006's
  `skill-format-validator` becomes possible: parse orchestrator
  outputs for the named verbs (`HALT:`, `surface-inline`, etc.)
  and reject malformed reports. Out of scope for this PR — file
  when the vocabulary has survived contact with several real
  workflows.

- **No production code changes.** Like ADR-0004, ADR-0005, and
  ADR-0006, this ADR ships docs + agent-definition updates only.
  Behaviour changes manifest the next time the orchestrator is
  invoked.

- **Plan-emitting reframe of G7 (PR #140) — purity thesis preserved.**
  When the Claude Code subagent runtime
  ([docs](https://code.claude.com/docs/en/sub-agents)) made
  subagent-from-subagent spawning a silent no-op, G7 was reframed from
  "Delegate-vs-act" to "Plan-vs-act" — orchestrator emits a delegation
  plan for the parent main-thread to dispatch rather than spawning the
  specialist itself. The protocol's intent is unchanged (route through
  the appropriate specialist; never act directly); only the mechanism
  shifted. G1–G6 and G8–G11 are orthogonal to dispatch mechanism and
  translate unchanged. The placement-table row for G7 is amended above
  to reflect the renamed H2. See #139 for the broader subagent
  tooling-model gap epic and #140 for the orchestrator refactor.
