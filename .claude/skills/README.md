# Skills

Task-shaped reference material that agents load on demand when an
issue's context matches a skill's declared triggers. Skills capture
domain knowledge an agent would otherwise re-derive (badly) on
every relevant invocation. Skills *inform*; agents *do*.

The format and discovery contract are settled in
[ADR-0006](../../docs/adr/0006-skills-system.md). Read the ADR
before adding or modifying a skill.

## Layout

```text
.claude/skills/
├── README.md                    # this file
└── <skill-name>/
    ├── SKILL.md                 # entrypoint with required frontmatter
    └── <supporting-files>       # examples, fixtures, optional
```

One directory per skill. The `SKILL.md` entrypoint is the only
file agents read during discovery; supporting files are linked
from the body when needed.

## Required frontmatter

Every `SKILL.md` MUST declare:

```yaml
---
name: <skill-name>           # matches directory name; kebab-case
description: <one-line>      # surfaced when an agent considers loading
status: full | stub          # honest signal of coverage
triggers:
  paths:                     # glob list; may be empty []
    - "<glob>"
  areas:                     # area-label list; may be empty []
    - "<area>"
---
```

At least one trigger entry must exist across `paths` and `areas`
combined. A skill with no triggers can never load and is invalid.

Skills MUST NOT add `load: always` or any other field that
bypasses match-time loading — load-on-demand is what keeps the
context-window budget tractable.

## Discovery

Consuming agents (`issue-worker`, `code-reviewer`) scan all
`SKILL.md` files at a defined lifecycle point and load any whose
triggers match the current issue. Match is **hybrid OR**: a skill
loads if its path globs intersect the diff (or predicted diff) OR
its areas intersect the issue's labels. See ADR-0006 §Discovery
for the full rules.

## When to add a new skill

Soft rule:

- Friction noticed twice → file an issue
- Friction noticed three times → write the skill

If the content benefits *every* issue (not just a particular
shape), it belongs in `CLAUDE.md`, not in a skill.

## Stubs

A skill MAY ship as `status: stub` when its surface depends on
in-flight work. Stubs participate fully in discovery but their
body MUST contain a `## Gaps` section. Each gap entry MUST use
this structure:

````markdown
### <gap title>

- **What's missing:** <one line>
- **Why deferred:** <one line>
- **Unblocks when:** #<issue> [optional brief context]
````

Without this prescribed format, stubs degrade into
wishful-thinking documents. With it, stubs are honest
scaffolding pointing at real follow-up work. See
[ADR-0006 §Stub skill convention](../../docs/adr/0006-skills-system.md)
for the full rules.
