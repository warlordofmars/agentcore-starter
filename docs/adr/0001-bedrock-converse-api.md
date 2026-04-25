# ADR-0001: Bedrock Converse API as the agent LLM interface
Date: 2026-04-24  
Status: Accepted

## Context

AgentCore Starter needed a standard interface for Lambda functions to invoke
large language models. The initial design goals were:

- **Model-agnostic** — swap Claude for another model without touching call
  sites.
- **AWS-native** — avoid third-party LLM SDKs to keep the dependency
  footprint small and stay within the AWS trust boundary.
- **Non-streaming first** — the existing Lambda Function URL is configured
  in buffered mode (`Mangum` with `lifespan="off"`), which does not support
  streaming responses. Streaming support is deferred to a follow-on PR
  that will switch to `RESPONSE_STREAM` + AWS Lambda Web Adapter.

The two main API options on Bedrock are the legacy per-model APIs
(`InvokeModel`) and the newer Converse API (`converse` / `converse_stream`).

## Decision

Use the **Bedrock Converse API** (`bedrock-runtime.converse`) as the sole
LLM invocation interface.

- The Converse API provides a single request/response shape for all
  supported models, eliminating per-model serialization logic.
- IAM access is scoped to specific model ARNs
  (`anthropic.claude-sonnet-4-6` and `anthropic.claude-haiku-4-5-20251001-v1:0`)
  to satisfy cdk-nag `AwsSolutions-IAM5` without a wildcard resource.
- The default model is `anthropic.claude-sonnet-4-6`, overridable at
  runtime via the `BEDROCK_MODEL_ID` environment variable.
- Typed stubs (`mypy_boto3_bedrock_runtime`) are added as a dev-only
  dependency, guarded by `TYPE_CHECKING`, so they are never bundled into
  the Lambda deployment package.

## Consequences

- **Model switching** — changing models requires only an env var update;
  no code changes needed as long as the target model supports the Converse
  API and is added to the IAM policy.
- **Streaming deferred** — `converse_stream` cannot be used with the current
  Mangum buffered handler. PR #2 (streaming) will add `RESPONSE_STREAM`
  Function URL mode + AWS Lambda Web Adapter to unlock `converse_stream`.
- **Converse API model coverage** — not every Bedrock model supports the
  Converse API. Models that only expose `InvokeModel` cannot be used
  without adding a separate invocation path.
