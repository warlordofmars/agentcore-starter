# ADR-0002: Streaming via AWS Lambda Web Adapter
Date: 2026-04-25  
Status: Accepted

## Context

SSE (server-sent events) streaming from a Lambda function requires the
response bytes to be forwarded to the caller incrementally, not buffered.

The existing setup uses **Mangum** as an ASGI adapter.  Mangum collects the
full FastAPI response in memory and returns it as a single Lambda invocation
result, so `StreamingResponse` endpoints are silently buffered — the client
receives all data at once after the model finishes.

Lambda supports true streaming via **Function URL `RESPONSE_STREAM` invoke
mode**, which allows the function to write bytes incrementally.  To use this
mode from a standard ASGI application the packaging must change: the runtime
is no longer driven by a Mangum handler but by a long-lived web server that
AWSLWA proxies.

The **AWS Lambda Web Adapter (AWSLWA)** project (account `753240598075`,
Apache 2.0) solves this cleanly:

1. It runs as a Lambda Extension inside the same execution environment.
2. It starts the application (`run.sh`) before the first invocation.
3. Each Lambda event is translated into an HTTP request forwarded to the
   local port (8080).
4. With `AWS_LWA_INVOKE_MODE=response_stream` it pipes the HTTP response
   body back to the caller chunk-by-chunk, enabling true SSE.

Alternatives considered:

* **Custom streaming handler** — writing raw Lambda response-streaming code
  bypasses FastAPI entirely and loses routing, auth middleware, and type
  safety.  High maintenance burden.
* **Separate streaming Lambda** — a second function for streaming endpoints
  doubles the infra surface for no architectural gain.
* **API Gateway** — lacks native SSE support; WebSocket-based workarounds
  are significantly more complex.

## Decision

1. **Replace Mangum** with AWSLWA + uvicorn.
   * Lambda handler set to `run.sh` (starts `uvicorn starter.api.main:app
     --host 0.0.0.0 --port 8080`).
   * AWSLWA layer `arn:aws:lambda:{region}:753240598075:layer:LambdaAdapterLayerX86:24`
     (v0.8.4) added to the function.
   * `run.sh` is bundled into the Lambda asset alongside the Python package.

2. **Function URL invoke mode → `RESPONSE_STREAM`.**  
   All Function URL traffic flows through AWSLWA; non-streaming endpoints
   are unaffected because AWSLWA buffers and returns them normally.

3. **Add `bedrock:InvokeModelWithResponseStream`** to the Lambda IAM policy
   alongside the existing `bedrock:InvokeModel`.

4. **SSE event schema** (defined in `bedrock.converse_stream`):
   * `data: {"type": "delta", "text": "..."}` — incremental token.
   * `data: {"type": "done", "stop_reason": "...", "input_tokens": N,
     "output_tokens": M}` — final event.

5. **CloudFront note**: the `/api/*` CloudFront behaviour routes to the
   Function URL.  CloudFront may buffer SSE when its own response buffering
   is active.  For low-latency streaming use the Function URL directly
   (available in the `ApiFunctionUrl` CFN output).  A future ADR can address
   a CloudFront bypass path or a dedicated streaming behaviour if needed.

## Consequences

* **Mangum is retained** in `pyproject.toml` and `api/main.py` as a
  documented fallback for local development (`lambda_handler` is still valid
  for unit testing).  It is no longer invoked in the deployed Lambda.
* **Cold-start overhead** increases slightly because uvicorn must finish
  starting before the first request is handled.  AWSLWA waits up to
  `AWS_LWA_READINESS_CHECK_TIMEOUT` (default 3 s) for a successful health
  probe on `/health` before accepting traffic.
* **Streaming is opt-in per endpoint.**  Existing `POST /api/agents/echo`
  is unchanged.  The new `POST /api/agents/echo/stream` endpoint returns
  `text/event-stream`.
* **AWSLWA version pinning**: the layer ARN in `starter_stack.py` contains
  an explicit version suffix.  Update it when a new AWSLWA release is
  available.
