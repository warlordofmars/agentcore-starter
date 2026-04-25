# ADR-0004: AWS Bedrock AgentCore Runtime + Memory feasibility for chat-app fork
Date: 2026-04-25  
Status: Accepted

## Context

This ADR captures the outcome of a 1–2 day research spike (issue #17)
investigating whether and how to integrate AWS Bedrock AgentCore Runtime and
AgentCore Memory into a chat-application fork of this template. AgentCore
went generally available on **2025-10-13**; boto3 1.42.78 (already in our
lockfile) ships both `bedrock-agentcore` (data plane) and
`bedrock-agentcore-control` (control plane) clients, so there is no
preview-blocker.

A naming clarification is essential: this template's
`src/starter/agents/inline_agent.py` wraps **Bedrock inline agents**
(`bedrock-agent-runtime.invoke_inline_agent`), **not** AWS Bedrock AgentCore.
The two services are unrelated; the wrapper was renamed under #27 to make
this explicit.

The spike informs:

- **#48 (C1 — infra partition)** — partition needs to know whether Runtime
  introduces a new IAM scope, a separate compute artifact, or new constructs
  before committing to its breakdown.
- **#37 (workspace primitive design)** — Memory's namespacing primitives may
  constrain or unblock the workspace tenancy model.

### Findings

The spike covered six investigation areas. Citations are to AWS
documentation, the boto3 service models inspected via
`boto3.client('bedrock-agentcore').meta.service_model`, and the existing
repo state where relevant.

**1. Runtime endpoint shape — not a drop-in retarget.**

`InvokeAgentRuntime` is a fundamentally different surface from
`invoke_inline_agent`:

- Inline-agent: `invoke_inline_agent(foundationModel, agentInstruction,
  inputText, sessionId, …)` — AWS-managed agent loop, configuration only.
- Runtime: `invoke_agent_runtime(agentRuntimeArn, payload=<bytes>,
  runtimeSessionId, runtimeUserId, mcpSessionId, contentType, accept, …)` —
  bring-your-own ARM64 container, deployed via
  `bedrock-agentcore-control.create_agent_runtime`, exposing
  `POST /invocations` and `GET /ping` on port 8080. The container is the
  agent loop.

Notable: Runtime has `runtimeUserId` as a first-class invocation field and
supports MCP, A2A, AG-UI, or plain HTTP via the `serverProtocol` parameter.
Runtime supports OAuth 2.1 inbound JWT authorization
(`authorizerConfiguration.customJWTAuthorizer.discoveryUrl`) but requires an
OIDC discovery endpoint (`/.well-known/openid-configuration`) — this
template currently publishes only the RFC 8414 form
(`/.well-known/oauth-authorization-server`).

**2. Streaming compatibility — works end-to-end through Lambda + AWSLWA.**

`InvokeAgentRuntime` returns a streaming HTTP body whose content type is
whatever the Runtime container emits; for SSE the container yields
`text/event-stream` chunks (`data: …\n\n`) and AWS proxies them through.
The boto3 consumer pattern is `for line in response["response"].iter_lines():
…` — raw HTTP chunked stream. This is a different shape from the existing
inline-agent path, which iterates the Bedrock event stream via
`for event in response["completion"]:` and forwards decoded chunks through
FastAPI `StreamingResponse`. Wiring Runtime SSE into that existing
`StreamingResponse` path (proven in ADR-0002) is still mechanical, even
though the upstream stream surface is HTTP/SSE rather than Bedrock event
objects.

Hard quotas to plan against: 60-min streaming maximum, 100 MB request
payload, 8-hour session lifetime, 15-minute idle timeout, 1000 active
sessions per account in us-east/us-west (500 elsewhere), 2 vCPU / 8 GB RAM
per session.

**3. AgentCore Memory model — opinionated, LLM-driven, not a transcript
store.**

Memory's hierarchy:

```text
Memory (resource, account-scoped)
  ARN: arn:aws:bedrock-agentcore:<region>:<acct>:memory/<id>
  └── actorId    (string, implicit — declared at CreateEvent)
        └── sessionId  (string, implicit — declared at CreateEvent)
              └── events  (raw turns; payload[].conversational.role/text)
                          → strategies extract LLM-derived records
                            into namespaces (templated strings)
```

Strategy types: `semantic`, `summary`, `userPreference`, `episodic`,
`custom`. Each runs LLM extraction + consolidation against events and emits
records into a namespace.

**Namespace templates accept only the predefined variables `{actorId}`,
`{sessionId}`, `{strategyId}` / `{memoryStrategyId}`. Custom variables (no
`{workspaceId}`) are not supported.** Hardcoded prefixes work but bake
values in at `CreateMemory` time and are not viable for dynamic
per-workspace tenancy.

Quotas: 150 Memory resources per region per account (one-Memory-per-workspace
does not scale); 6 strategies per Memory; event retention 7–365 days.
Pricing: $0.25 per 1k events, $0.75 per 1k records per month (built-in
strategies), $0.50 per 1k retrievals.

**4. IAM scopes — fully fleshed out, with namespace-level granularity for
Memory.**

ARN formats:

```text
arn:aws:bedrock-agentcore:<region>:<acct>:runtime/<id>
arn:aws:bedrock-agentcore:<region>:<acct>:runtime/<id>/runtime-endpoint/<name>
arn:aws:bedrock-agentcore:<region>:<acct>:memory/<id>
```

Inline-agent ARNs (`arn:aws:bedrock:…:agent/*`) are a different scheme — the
existing `bedrock:InvokeInlineAgent` policy in
`infra/stacks/starter_stack.py` does not transfer.

Memory permissions can be scoped below the resource via
`bedrock-agentcore:namespace` and `bedrock-agentcore:namespacePath` condition
keys, allowing per-tenant IAM policies (e.g., `namespacePath` matches
`workspaces/<id>/*`) provided the namespace encoding is stable.

**5. Migration path — three architectures, sidecar option preferred.**

| Option | Description | Cost |
|---|---|---|
| A. Sidecar Runtime + thin Lambda proxy | Build ARM64 agent container; deploy as Runtime; existing FastAPI Lambda calls `invoke_agent_runtime` from new `/api/chat/*` routes; SigV4 from Lambda → Runtime | New CDK construct; new IAM scope `bedrock-agentcore:InvokeAgentRuntime`; ECR image build (~1–2 min CD) |
| B. Runtime as front-door | Frontend calls Runtime directly via JWT authorizer; FastAPI Lambda no longer in chat hot path | Requires OIDC discovery endpoint; CORS / browser SigV4 story; major architecture shift |
| C. Full replacement | Delete `inline_agent.py`, retire inline-agent | Loses zero-pre-provisioning property; supersedes ADR-0003 |

Option A keeps both code paths in coexistence at near-zero IAM/code carry
cost.

**6. Memory namespace × workspace tenancy interaction.**

Because namespace templates accept only `{actorId}`, `{sessionId}`,
`{strategyId}`, **workspace tenancy must be encoded inside `actorId`**:
`actorId = f"{workspace_id}:{user_id}"`. This generalises the existing
convention from CLAUDE.md (`sessionId = f"{user_id}:{caller_session_id}"`)
and aligns with the workspace-as-tenancy-root product decision without
forcing a second tenancy axis. Per-workspace IAM scoping then works via
`bedrock-agentcore:namespacePath` against templated namespace prefixes.

The actorId encoding convention (workspace-ID format and escaping) **must
be locked before any Memory writes occur**. Events are immutable; namespace
records are rebuilt only on full re-extraction; changing the encoding after
data exists is destructive. Memory does not require the workspace primitive
to be fully implemented in code first, but its design (#37) must produce a
stable encoding before Memory integration begins.

### Sources

- AWS what's new — [Amazon Bedrock AgentCore is now generally available](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/)
  (2025-10-13).
- [AgentCore Runtime overview blog](https://aws.amazon.com/blogs/machine-learning/securely-launch-and-scale-your-agents-and-tools-on-amazon-bedrock-agentcore-runtime/).
- [Runtime service contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)
  and [HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html).
- [`InvokeAgentRuntime` API reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html).
- [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html).
- [Memory organization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-organization.html)
  and [Memory namespace scoping](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/session-actor-namespace.html).
- [AWS SDK Memory worked example](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/aws-sdk-memory.html).
- [Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/).
- [Service Authorization Reference for `bedrock-agentcore`](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbedrockagentcore.html).
- [Inbound JWT authorizer](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/inbound-jwt-authorizer.html).
- boto3 1.42.78 service models for `bedrock-agentcore` and
  `bedrock-agentcore-control`, inspected locally via
  `boto3.client(...).meta.service_model`.

## Decision

1. **Decision A — Runtime vs inline-agent (chat-app fork only).**
   AgentCore Runtime replaces inline-agent for the chat-app fork via
   **migration Option A (sidecar)**. The chat-app fork will run both code
   paths during transition: `/api/agents/*` (inline-agent, pedagogical) and
   `/api/chat/*` (Runtime). The template itself does **not** migrate to
   Runtime. The template's positioning as "starter for AWS-native AI
   agents" deliberately preserves the simplest path (inline-agent) for
   forks that don't need a custom container; ADR-0003 remains in force for
   the template.

2. **Decision B — Memory vs DynamoDB.**
   Memory and DynamoDB **coexist**. Memory handles semantic recall
   (LLM-extracted facts, summaries, preferences) and is invoked by the
   agent as a tool via `RetrieveMemoryRecords`. DynamoDB retains ownership
   of the raw turn-by-turn transcript and the immutable audit log.
   **Memory is not a transcript store**; conversation state remains
   DynamoDB-backed.

3. **D1 directive (captured verbatim from issue #17, applies to the Memory
   findings in this ADR):**

   > "Spike must capture findings on how AgentCore Memory namespace design
   > interacts with the workspace-as-tenancy-root product decision. If the
   > spike concludes that workspace primitive must be locked before Memory
   > integration can proceed, promote #37 to `chat-app-ready` as a
   > follow-up."

   Spike conclusion: the workspace primitive does not need to be fully
   implemented in code before Memory integration, but its **design**
   (specifically the actorId encoding format) must be locked first. A
   follow-up on #37 will surface this dependency and propose promotion;
   promotion is for design-review's call.

4. **Recommendation: spike-further.**
   Memory is mature and immediately usable. Runtime requires non-trivial
   container scaffolding (ARM64 image build, ECR push, CDK construct,
   deploy pipeline integration), sized at `size:l` minimum. Findings
   should be folded into #48 before construct breakdown — specifically, a
   **`ChatRuntimeConstruct`** should be planned alongside the existing six
   constructs in #48's scope, and the partition's Storage construct should
   anticipate the `actorId` encoding convention.

   The two recommendations not chosen:
   - *Integrate-now* — premature; the Runtime container artifact, ECR
     pipeline, and CDK construct are non-trivial and would consume the
     chat-app fork's first sprint without #48's partition landing.
   - *Defer-indefinitely* — both services are GA, are in our region, and
     address concrete chat-app needs (semantic recall, durable agent
     compute). Deferring forfeits these without offsetting savings.

## Consequences

- **No production code changes.** This ADR is the spike's deliverable;
  integration work is deferred to follow-up issues.

- **CLAUDE.md update needed.** The `inline_agent.py` user-namespacing
  convention (`sessionId = f"{user_id}:{caller_session_id}"`) is preserved
  for the inline-agent path but extended for the chat-app fork's
  Runtime/Memory path: `actorId = f"{workspace_id}:{user_id}"`,
  `sessionId = caller_session_id` (no user prefix needed because Memory's
  `actorId` provides user scope natively). This is a design note, not a
  behaviour change for the template.

- **#37 is on the critical path for chat-app Memory work.** The actorId
  encoding format must be locked in #37's design before any Memory
  integration begins. A follow-up comment on #37 will surface this and
  propose promotion from `priority:p2` to `chat-app-ready`. Promotion
  decision is for design-review.

- **#48 (C1 partition) needs a `ChatRuntimeConstruct` scoped in.**
  Specifically: a CDK construct owning the AgentCore Runtime resource, its
  Endpoint, the ECR image asset, and the `bedrock-agentcore:InvokeAgentRuntime`
  IAM scope. This is additive to the existing six-construct breakdown.

- **OIDC discovery endpoint is a future-iteration prereq for migration
  Option B.** Not blocking sidecar Option A. If the chat-app fork later
  wants frontend-direct Runtime calls (Option B), the OAuth 2.1 server
  must publish `/.well-known/openid-configuration` — a small addition (the
  issuer + `jwks_uri` are already published under the RFC 8414 form).
  Tracked separately if and when Option B is in scope.

- **ADR-0003 remains in force for the template.** Inline-agent and the
  user-namespaced session convention are unchanged for `/api/agents/*`.
  The chat-app fork's `/api/chat/*` path operates under this ADR's
  conventions.

- **Quotas to monitor when integration begins.** Active session cap (1000
  us-east/west, 500 elsewhere) and Memory resource cap (150 per region).
  Both are adjustable by AWS support but not via tags or CDK; raise tickets
  early in scaling.

- **Pricing model is consumption-based, no minimums.** Runtime:
  $0.0895/vCPU-hr + $0.00945/GB-hr, billed per second. Memory: $0.25/1k
  events + $0.75/1k records/month (built-in) + $0.50/1k retrievals.
  Adopters of the chat-app fork should plan synthetic-traffic budgets
  accordingly.
