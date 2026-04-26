# ADR-0008: Issue-worker push discipline against wholesale-push damage
Date: 2026-04-26  
Status: Accepted

## Context

At 23:07:07 EDT on 2026-04-25 an issue-worker session running in
`/Users/john/Projects/agentcore-starter-spike` rewound
`origin/development` by 11 merges. The 2026-04-26 strategy session
retro (`docs/retros/2026-04-26-strategy-session-retro.md` Part B)
captures the full forensic; the load-bearing details for this ADR
are:

- Bash history is not recoverable. Claude Code's Bash tool runs in
  a non-interactive shell that doesn't write to the user's
  interactive `$HISTFILE`. The exact `git push` command that caused
  the rewind is unknown. Most likely candidates: `git push --all
  --force`, `git push --force` with `push.default = matching`, or
  a misfired multi-ref refspec.
- The clone's local `development` ref was at `943923a` (the SEC-1
  fix from earlier that day, never updated through any of the
  subsequent merges); origin's `development` was at `14ea24e`
  (post-PR-#80 merge). The wholesale push targeted every local
  branch with a remote counterpart, including stale `development`,
  rewinding origin to the stale local SHA.
- Branch protection on `development` was *not yet applied* at
  incident time. `#50` in the bootstrap epic tracked the gap as a
  known unknown; this incident materialised it as actual data loss.
- `--force-with-lease` (if used) would have been satisfied — the
  bare lease's default uses the local clone's remote-tracking ref,
  which had been updated to `14ea24e` via fetch four minutes
  earlier. The lease saw origin matching the expected SHA and
  accepted the push.
- The agent's understanding of `halt-before-merge` was narrowly
  scoped to `gh pr merge --auto` and didn't extend to git
  operations on shared refs. The verbal rule covered what it
  explicitly said; everything else was open.

Recovery succeeded via cross-clone restore — the cleared
orchestrator session's clone retained `14ea24e` on local
`development`, and a `--force-with-lease=development:943923a`
push pinned to the rewound state restored origin first try. The
fact that recovery worked at all was accidental redundancy, not
a deliberate safeguard.

The broader pattern the incident exposed: verbal hedges
(`don't do dangerous things`, `be careful with pushes`) cover
what they explicitly say; everything else is open. The
2026-04-26 retro Synthesis observation 1 captures this directly:
*mechanical defenses beat verbal hedges, every time*. Branch
protection on `development` (now applied as #50) is the
load-bearing GitHub-side defense; this ADR adds the agent-side
defense layered on top, because branch protection only catches
what reaches the protected branch — agent-level rules catch
dangerous categories before they reach origin at all. Both
layers are needed. (Retro Synthesis observation 2:
*defensive layers should be non-overlapping*.)

The clone-topology angle is also load-bearing. The `-spike`
clone was originally created for issue #17 (the AgentCore
Runtime spike, ADR-0004) and kept around past its purpose.
Naming clones with feature-suffixes (`-spike`, `-experiment`,
etc.) creates ghost workspaces — they outlive their purpose
and get repurposed, with stale state baked in. Issue #91
explored three options for that surface (decommission
per-purpose clones; pre-push staleness check; canonical clone
with worktrees) and concluded the mechanical pre-push check
is the load-bearing defense. This ADR captures that
conclusion: the staleness check ships as W7 in the rule set
below, and #91 closes as resolved by this PR.

## Decision

Add a `## Push discipline` section to
`.claude/agents/issue-worker.md` between `## Issue cycle` and
`## Keeping CLAUDE.md current`. The section codifies seven
mechanical rules, W1–W7, each expressed as a pattern-match
against command strings or git config values rather than a
behavioural hedge. The W-numbering parallels the orchestrator's
G1–G11 (ADR-0007) so retrospective references resolve cleanly
and future additions extend the same vocabulary.

### Rule set

| Rule | Mechanism |
|---|---|
| W1 — Allowlist of valid push targets | `git rev-parse --abbrev-ref HEAD` must start with `feat/`, `fix/`, or `chore/` before any push |
| W2 — Prohibition on wholesale pushes | Command string must not contain ` --all` or ` --mirror`; must contain a `<branch>:<branch>` refspec |
| W3 — Prohibition on bare `git push` | Refspec is mandatory; bare `git push` and `git push origin` are forbidden |
| W4 — Required pre-fetch + shadow fast-forward | `git fetch origin` before any branch operation; then fast-forward protected shadow branches (`development`, `main`) to their origin counterparts. Three sub-cases: not checked out → `git fetch origin <b>:<b>`; currently checked out as HEAD → `git merge --ff-only origin/<b>`; locked by another linked worktree → leave alone (W7's ancestry check absorbs it). Current feature branch exempt |
| W5 — `push.default` config check | `git config --get push.default` must return `simple`, `current`, or `nothing`; `matching` is forbidden |
| W6 — Refspec verification | Both sides of the `<src>:<dst>` refspec must equal the current branch from `git rev-parse --abbrev-ref HEAD` |
| W7 — Stale-clone signal check | After W4's fast-forward, run `git merge-base --is-ancestor <branch> origin/<branch>` for each protected shadow. The check must succeed (local is an ancestor of origin = healthy, possibly worktree-locked lag); failure means true divergence — halt and surface. Current feature branch is exempt |

W1, W2, W5, W6, W7 each catch a distinct failure mode the
2026-04-26 incident exposed. W3 (no bare `git push`) and W4
(required pre-fetch) are partly redundant with existing
workflow steps, but promoting them to explicit prohibitions
captures the explicit-over-implicit principle — which survives
context loss in a way procedural conventions don't. The
project's current §6 `git push --force-with-lease` example
without explicit refspec is itself an instance of the verbal-
hedge pattern that needs replacing; the canonical forms
shipped with this ADR move §6 to the explicit refspec shape
required by W3/W6.

W4 and W7 are deliberately coupled: W4 absorbs healthy lag by
fast-forwarding shadow refs that can be moved (not currently
checked out, not worktree-locked); W7 then runs an ancestry
check on the remaining refs to distinguish worktree-locked
healthy lag from true divergence. W4's individual fetch/merge
calls tolerate failure (`|| true`) because a fast-forward
failure means *either* divergence *or* worktree-lock, and
only W7 can tell those apart. The coupling is encoded in
W4's prose as "W4 must always be followed immediately by W7"
and surfaced in the W4 inline comments; removing W7 or
running it before W4 breaks the contract.

### Worked counter-example, transcript-shaped

The section closes with a transcript-shaped worked counter-
example reconstructing the 2026-04-26 incident with the rules
in force. The shape mirrors the G7/#79 exemplar in
`.claude/agents/orchestrator.md:255` — a concrete scenario
showing what the agent MUST refuse. The exemplar is deliberately
the actual incident; abstracting it to a hypothetical would
break the chain back to the forensic record.

### CLAUDE.md cross-reference

CLAUDE.md §"Opening a PR" gets one paragraph cross-referencing
W1–W7. The cross-reference is a pointer, not a restatement —
CLAUDE.md is loaded into every agent context, so duplicating
the rules would invite drift between the two surfaces.
The pointer keeps CLAUDE.md authoritative on what's referenced
and `issue-worker.md` authoritative on the rules themselves.

### Bundled #91 closure

#91 (decommission per-spike clones / clone-hygiene) explored
three options:

- **Option A — decommission per-purpose clones after work
  merges.** Procedural rule. Rejected because the issue body
  itself flags it as "easy to forget" and notes it "doesn't
  cover legitimate parallel-work cases." Procedural conventions
  don't survive context loss across agent sessions — exactly
  the failure mode the 2026-04-26 incident exposed.
- **Option B — pre-push staleness check in
  `issue-worker.md`.** Mechanical rule. Catches the actual
  failure mode at push time, which is where the damage
  happens. The "false-positive when intentionally working with
  stale clone" concern is addressed by W7's halt-and-surface
  shape — the user can explicitly override after the halt; the
  rule surfaces, it doesn't silently block.
- **Option C — canonical clone + worktrees.** Structurally
  strong but requires worktree adoption and migration of
  existing clones. Disproportionate to the residual risk once
  Option B is in place — Option B catches the stale-baseline
  failure mode regardless of clone naming.

Option B is identical to W7 in this ADR's rule set. #91
resolves to the same mechanism W7 ships, so #91 closes as
"implemented under #89" rather than forking off a parallel
PR. The PR body cites both `Closes #89` and `Closes #91` so
the GitHub auto-close fires for both.

## Alternatives considered

**(a) Verbal hedges only — strengthen the existing
"halt-before-merge" wording without adding mechanical rules.**
Rejected. The 2026-04-26 incident is itself the rejection of
this option — verbal `halt-before-merge` covered what it
explicitly said and the `git push --all` collateral was
outside the wording. Strengthening the verbal rule produces
the same failure mode at a slightly higher threshold.

**(b) Codify only W1, W2, W5, W7 (drop W3/W4/W6 as redundant
with existing workflow).** Rejected. W3 (no bare `git push`)
and W4 (required pre-fetch) are partly redundant with §6's
explicit `git fetch origin` and `git push -u origin <branch>`
examples — but promoting them to explicit prohibitions captures
the explicit-over-implicit principle. The 2026-04-26 incident
demonstrates that "convention says do X" doesn't survive
context loss; "rule W3 forbids Y" does. W6 (refspec
verification) similarly looks redundant with W2 (refspec
required) but catches a different failure mode: W2 stops a
push without a refspec; W6 stops a push *with* a refspec that
targets the wrong branch. Both catch real failure modes.

**(c) Implement as a git pre-push hook rather than agent
rules.** Rejected for this PR; viable as future work. A pre-
push hook would catch the exact failure mode mechanically at
the git layer, regardless of agent compliance. But hooks are
per-clone, opt-in, and bypassable with `--no-verify`. They
don't help if a clone (like `-spike`) was created before the
hook existed. Agent-level rules apply to every issue-worker
invocation regardless of clone state. The two approaches are
complementary; the hook can be filed as a follow-up if W1–W7
prove insufficient in practice.

**(d) Defer #91 to a separate PR.** Rejected. The W7 mechanism
ships in this PR regardless — #89's adopted rule set always
included it. #91 resolves to the same mechanism. Splitting
into two PRs would force #91's PR to be reviewed against an
already-merged W7, which is overhead with no benefit. The
bundled-PR shape matches ADR-0006 + #73 and ADR-0007 + #85
precedent: when two issues resolve to the same diff surface,
ship them in one PR.

## Consequences

- **PR is not `agent-safe`.** Modifies an agent definition.
  Same human-review policy as #59 (orchestrator definition),
  #82 (orchestrator codification, ADR-0007), and #77 (scope-
  boundary enforcement). LLM-only review is insufficient — a
  regression in the new push-discipline protocol could allow
  the autonomous loop to misfire on a wholesale push without
  surfacing it for human review. The cycle implementing this
  PR halts at §7.5 with `HUMAN_INPUT_REQUIRED: PR #NNN ready
  for human review + merge`.

- **Bundled PR shape covers #89 and #91.** The PR body
  carries both `Closes #89` and `Closes #91`. This shape
  matches ADR-0007's combined rationale: when the underlying
  mechanism is the same and the design conclusions converge,
  one PR is cheaper than two and preserves the chain from
  rationale to consumption.

- **§6 push examples in `issue-worker.md` change shape.** The
  old `git push -u origin <branch>` and `git push --force-
  with-lease` lines move to explicit refspec forms
  (`git push -u origin <branch>:<branch>` and `git push
  --force-with-lease=<branch>:<expected-sha> origin
  <branch>:<branch>`). `<expected-sha>` is the previous remote
  tip of the *feature branch itself* (capture with
  `git rev-parse origin/<branch>` before rebasing) — not the
  rebase base. This is consistent with W3/W6 — the examples
  now demonstrate the rules rather than contradicting them.
  The §7 fix-and-push loop similarly changes from `git push`
  to `git push origin <branch>:<branch>`.

- **W7 ships with halt semantics, not silent block.** The
  rule surfaces stale-clone state with `HUMAN_INPUT_REQUIRED:
  stale-clone signal — ...` and lets the human explicitly
  override. This preserves the legitimate-stale-clone use case
  (working from a clone that was intentionally pinned to an
  older state) while catching the failure mode the 2026-04-26
  incident exposed.

- **#91 closes when this PR merges.** The GitHub auto-close
  fires from the `Closes #91` line in the PR body. No
  separate PR is opened for #91. The 2026-04-26 retro Action
  Items entry "5. File issue: clone-hygiene rules
  (decommission per-spike clones, or pre-push staleness check)"
  resolves to W7 in this PR.

- **Validation lands post-merge.** The acceptance criterion
  "after merge, the next agent-safe issue-worker run validates
  no false-positive halts under the new constraints" is
  satisfied by the next agent-safe issue-worker invocation.
  The validation is implicit in normal operation — if the
  rules cause a false-positive halt, the human will see it and
  the rule will be revisited; if the rules don't fire on
  legitimate pushes, the validation passes silently.

- **Future work — git pre-push hook.** Alternative (c) above
  is viable as a complementary defense layer. File when W1–W7
  prove insufficient in practice (e.g. an incident where the
  agent followed the rules but the hook would have caught
  something the rules missed). Out of scope for this PR.

- **Future work — `push.default` set repo-wide.** W5 forbids
  `matching` but doesn't enforce a specific value. A `git
  config --local push.default simple` committed to a repo
  setup script (or documented in `onboarding.md`) would
  ensure the W5 check passes on every clone of this repo
  without per-clone configuration. Defer to a separate issue
  once the W5 check has surfaced any per-clone configuration
  drift.

- **No production code changes.** Like ADR-0005, ADR-0006,
  and ADR-0007, this ADR ships docs + agent-definition
  updates only. Behaviour changes manifest the next time the
  issue-worker is invoked and tries to push.
