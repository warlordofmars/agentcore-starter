# ADR-0004 summary — input to #48 (C1 infra partition)

This is the distilled "what does the C1 partition need to know" version of
[ADR-0004](0004-agentcore-runtime-feasibility.md). Read the ADR for full
findings and citations.

## Bottom line

**Spike-further.** Both AgentCore Runtime and Memory are GA (2025-10-13),
supported in boto3 1.42.78, and address concrete chat-app needs. Neither is
a drop-in retarget of the existing inline-agent path; integration requires
new IAM scope, new CDK constructs, ARM64 container scaffolding, and an ECR
pipeline. The C1 partition should account for these before construct
breakdown lands.

## Decisions

- **Decision A** — Runtime replaces inline-agent **for the chat-app fork
  only**, via sidecar (Option A). Both code paths coexist: `/api/agents/*`
  (inline-agent, pedagogical) and `/api/chat/*` (Runtime). The template
  itself stays on inline-agent; ADR-0003 remains in force.
- **Decision B** — Memory and DynamoDB coexist. Memory for LLM-extracted
  recall (facts/summaries/preferences); DynamoDB for transcript and audit.
  Memory is **not** a transcript store; conversation state remains
  DynamoDB-backed.

## Inputs to #48

1. **Add a `ChatRuntimeConstruct` to the partition.** Scope: AgentCore
   Runtime resource, Runtime Endpoint, ECR image asset, IAM permission
   `bedrock-agentcore:InvokeAgentRuntime` against the runtime /
   runtime-endpoint ARN.
2. **Add a `MemoryConstruct` (or fold into Storage construct).** Scope:
   AgentCore Memory resource with semantic + summary + userPreference
   strategies; IAM permissions `bedrock-agentcore:CreateEvent | ListEvents
   | ListSessions | RetrieveMemoryRecords | GetMemoryRecord` scoped to the
   Memory ARN, optionally further constrained by
   `bedrock-agentcore:namespacePath` condition keys.
3. **Storage construct anticipates actorId encoding.** Conversation /
   audit DynamoDB items should carry `workspace_id` + `user_id` columns to
   match the `actorId = "{workspace_id}:{user_id}"` convention from #37's
   design.
4. **No changes to the existing inline-agent path.** Lambda IAM keeps
   `bedrock:InvokeInlineAgent` and `bedrock:InvokeModel*`. The chat-app
   fork adds new permissions; it does not subtract.

## Hard prerequisites before any chat-app integration begins

- **#37 design must produce a stable workspace-ID encoding format.**
  Memory events and namespace records cannot be re-keyed without
  destructive re-extraction. The exact `actorId =
  f"{workspace_id}:{user_id}"` shape (separator, escaping, length) must
  be locked in #37 before the first Memory write.
- **CLAUDE.md product-decisions update**: extend the user-namespacing
  convention for the Runtime/Memory path so future agents in the fork
  follow the same encoding.

## Hard quotas to plan against

- **Runtime**: 60-min streaming max, 100 MB payload, 8 hr session, 15 min
  idle timeout, 1000 active sessions per account in us-east/us-west (500
  elsewhere), 2 vCPU / 8 GB RAM per session.
- **Memory**: 150 resources per region (one-Memory-per-workspace does not
  scale), 6 strategies per Memory, 7–365 day event retention.

## What this spike explicitly does NOT decide

- **OIDC discovery endpoint** — not needed for sidecar (Option A); only
  needed if chat-app fork later moves to Option B (frontend → Runtime
  direct). Tracked separately if and when Option B is in scope.
- **Concrete ECR / CD pipeline shape** — depends on #48's final partition
  structure.
- **Memory strategy choice and namespace template strings** — design work
  for the chat-app fork's first integration issue, not this spike.
