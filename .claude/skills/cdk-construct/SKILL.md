---
name: cdk-construct
description: "Conventions for authoring CDK constructs in the AgentCore Starter stack — placeholder stub until the partition work in #48 settles props, public-attribute, and CDK Nag suppression patterns."
status: stub
triggers:
  paths:
    - "infra/stacks/**.py"
    - "infra/app.py"
  areas:
    - "infra"
---
> STUB — full skill blocked by #48 (infra partition); follow-up #68

# cdk-construct

Skill scope: CDK construct conventions for the AgentCore Starter
stack — props pattern, cross-construct value exposure, IAM scoping,
and CDK Nag suppression placement. The conventions are not yet
stable; the partition work in #48 (which splits
`infra/stacks/starter_stack.py` into 6-7 constructs) is what
stabilises them.

Until #48 lands, all infra lives in a single
`AgentCoreStarterStack` class at
`infra/stacks/starter_stack.py` — the current shape reference for
how resources are wired, IAM grants are scoped, and CDK Nag
suppressions are attached. New infra work should follow the
existing patterns in that file rather than inventing a partitioned
shape ahead of #48.

## What we know now (intent only)

These three conventions are settled in principle and will carry
forward into the partitioned shape:

- **Each construct owns its own IAM scope.** Cross-construct
  grants happen at the composer (stack) level, not inside the
  construct that needs the grant. A construct never reaches into
  another construct's resource to attach a policy.
- **Constructs expose typed values to one another.** The exact
  shape of the props pattern (typed kwargs vs dataclass) is part
  of what #48 settles.
- **CDK Nag suppressions live with the construct that owns the
  suppressed resource** — per the #48 acceptance criterion. A
  suppression on a Lambda role lives in the construct that
  defines that Lambda, not in the composer.

## Gaps

### Props convention not settled

- **What's missing:** Whether constructs accept typed `**kwargs`, a `@dataclass` props object, or a TypedDict — and the naming convention for the props type.
- **Why deferred:** The partition PR is what picks the shape; picking it here would pre-commit a decision that belongs to the partition design.
- **Unblocks when:** #48 lands the first partitioned constructs and establishes the props shape used across them.

### Public-attribute pattern for cross-construct exposure

- **What's missing:** The exact convention for how one construct exposes a value (table ARN, function URL, role) to another — attribute on the construct instance, accessor method, or re-exposed via stack-level outputs.
- **Why deferred:** The pattern only emerges once two or more constructs need to consume each other's outputs at the composer level.
- **Unblocks when:** #48 wires the first cross-construct consumer and establishes the lookup shape.

### Construct-level vs composer-level helpers

- **What's missing:** Whether helpers like `Edge.compress: bool` and `Secrets.validate_no_placeholders()` belong on the construct that owns the resource or on the composer that assembles them.
- **Why deferred:** The boundary depends on whether the helper is a per-resource invariant (construct) or a stack-wide validation (composer); the partition PR is what draws the line.
- **Unblocks when:** #48 places the first such helpers and the construct-vs-composer boundary becomes visible.

## Follow-up

Once #48 lands, #68 (which replaces this stub with a full skill)
takes over — covering the settled props convention,
public-attribute pattern, and CDK Nag suppression placement.

## See also

- `infra/stacks/starter_stack.py` — current single-class shape;
  the reference for how resources, IAM grants, and CDK Nag
  suppressions are wired today.
- [ADR-0006](../../../docs/adr/0006-skills-system.md)
  §"Stub skill convention" — the schema contract this stub
  follows.
- #48 — the partition work that stabilises CDK construct
  conventions in this repo.
- #68 — the follow-up that replaces this stub with a full skill.
