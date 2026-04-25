# ADR-0003: Inline Agent and session memory conventions
Date: 2026-04-25  
Status: Accepted

## Context

Bedrock Agents offers two invocation modes:

1. **Pre-configured agents** — an agent resource is created in the AWS console
   or via IaC, given an agent ID and alias, then invoked with `invoke_agent`.
   The agent instructions, model, knowledge bases, and action groups are
   stored in the agent resource and referenced at invocation time.

2. **Inline agents** — the entire agent configuration (instructions, model,
   action groups) is supplied in the request body via `invoke_inline_agent`.
   No agent resource is pre-provisioned; the configuration is ephemeral.

For a starter template the key requirement is minimal setup: a new team
should be able to clone the repo and call an agent endpoint without any
out-of-band AWS console configuration.  Pre-configured agents fail this
requirement because the agent resource must exist before the Lambda runs.

### Session memory

Bedrock Agents maintains short-term conversational memory within a *session*.
A session is identified by a `sessionId` string; subsequent calls with the
same `sessionId` continue the conversation.  There is no cross-session
memory by default (long-term memory requires a knowledge base with session
summarization enabled).

The starter must ensure that session IDs are scoped to a single user so that
user A cannot replay or read user B's conversation by guessing a session ID.
The JWT `sub` claim identifies the authenticated user.

## Decision

1. **Use `invoke_inline_agent`** for all agent endpoints in this template.
   This enables zero-console-setup for new adopters.  Teams that want
   pre-configured agents can replace the `agentcore.py` wrapper with an
   `invoke_agent` call and supply an agent ID via an environment variable or
   SSM parameter.

2. **Session ID namespace convention**: the wrapper computes the Bedrock
   `sessionId` as `f"{user_id}:{caller_session_id}"` where `user_id` is the
   JWT `sub` claim and `caller_session_id` is the opaque value supplied by
   the API caller.  The caller never sees the namespaced form — only their
   own `session_id` is echoed back.  This ensures:
   - Sessions cannot bleed across users even if the caller reuses the same
     `session_id` string.
   - Agents do not require a `user_id` parameter on every call — the token
     claim provides the scope.

3. **No cross-session memory by default.**  The `invoke_inline_agent`
   `inlineSessionState` field is initialised with empty
   `promptSessionAttributes`.  Adopters that need long-term memory can
   populate this dict from a DynamoDB lookup before calling the Bedrock API.

4. **Model selection follows `BEDROCK_MODEL_ID`** (same env var as the
   Converse wrapper in `bedrock.py`).  Default is `anthropic.claude-sonnet-4-6`.

## Consequences

* **Zero pre-provisioning** — the `POST /api/agents/invoke` and
  `POST /api/agents/invoke/stream` endpoints work in a fresh deploy without
  any Bedrock console configuration.
* **Action groups not wired up by default** — the starter passes an empty
  `actionGroups` list.  Adopters add tool definitions here for structured
  function-calling workflows.
* **IAM**: `bedrock:InvokeInlineAgent` is added to the Lambda role with
  resource `arn:aws:bedrock:{region}:{account}:agent/*`.  The wildcard
  on the agent resource suffix is required because inline agents do not
  have a fixed ARN.
* **Pre-configured agent migration path**: replace `agentcore.py` with a
  thin wrapper around `invoke_agent`, read `BEDROCK_AGENT_ID` and
  `BEDROCK_AGENT_ALIAS_ID` from env/SSM, and update the IAM policy to scope
  the `InvokeAgent` action to those specific ARNs.
