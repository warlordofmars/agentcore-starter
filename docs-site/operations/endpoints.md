# Operational endpoints

Two operational endpoints sit outside the normal authenticated management
API surface: `/health` (Lambda warm-up / liveness probe) and
`/api/csp-report` (browser CSP violation receiver). Both are
unauthenticated by design. This page documents what they accept, what
they return, who can call them, and what their abuse-protection
posture looks like today vs after the planned hardening lands.

## `GET /health`

Lightweight liveness probe used by Lambda warm-up checks and any
external uptime monitor pointed at the Function URL or CloudFront
origin.

| Field | Value |
| --- | --- |
| Method | `GET` |
| Auth | Unauthenticated |
| Path | `/health` |
| Implementation | `src/starter/api/main.py` (`@app.get("/health")`) |
| OpenAPI | Hidden (`include_in_schema=False`) |
| Response | `200 OK`, `application/json` |

### Response shape

```json
{
  "status": "ok",
  "version": "<APP_VERSION>"
}
```

`version` is read from `APP_VERSION` at module import time and reflects
the deployed package version. Operators can use it as a quick sanity
check that a deploy actually rolled.

### Caching and rate limiting

CloudFront fronts the Lambda Function URL but does **not** cache
`/health` responses (the path is in the no-cache behaviour set so a
stale `200` can't mask a sick origin). No application-side rate limit
is applied — `/health` is intentionally cheap (no DynamoDB calls, no
Bedrock calls) so a flood of probes is a non-event.

## `POST /api/csp-report`

CSP violation receiver. Browsers POST violation reports here when a
resource is blocked (or would be blocked under
`Content-Security-Policy-Report-Only`). Each report is logged as
structured JSON and emits a `CSPViolations` EMF metric.

| Field | Value |
| --- | --- |
| Method | `POST` |
| Auth | Unauthenticated (browsers don't send credentials with CSP POSTs) |
| Path | `/api/csp-report` |
| Implementation | `src/starter/api/csp.py` (`receive_csp_report`) |
| OpenAPI | Hidden (`include_in_schema=False`) |
| Response | `204 No Content` (always — even on parse error) |

### Accepted content types

The endpoint accepts both report formats browsers actually send:

- **Legacy** (`application/csp-report`) — single JSON object with a
  top-level `csp-report` key. Sent by Chromium-family browsers when
  the page declares only a `report-uri` directive.
- **Modern** (`application/reports+json`) — JSON array of report
  envelopes, each with `type: "csp-violation"` and a `body` object.
  Sent when the page declares `report-to` (the spec replacement for
  `report-uri`).

The endpoint detects the shape from the JSON structure (object vs
array) rather than the `Content-Type` header, so reports survive
header munging by intermediaries.

### Logged fields

Each violation is emitted as a `WARNING`-level structured log entry
with the following fields (truncated to 2 KiB each):

```json
{
  "violated_directive": "script-src",
  "effective_directive": "script-src",
  "blocked_uri": "https://evil.example.com/foo.js",
  "document_uri": "https://app.example.com/some/page",
  "source_file": "https://app.example.com/some/page",
  "line_number": 42,
  "column_number": 7,
  "disposition": "enforce"
}
```

Two CloudWatch EMF metrics are emitted per violation: a counter
(`CSPViolations`) and a dimensioned counter
(`CSPViolations` with `directive` + `blocked_domain` dimensions) for
breakdown views.

### Always returns 204

The handler returns `204 No Content` whether the body parsed cleanly,
was empty, or was malformed JSON. This is intentional — browsers
fire-and-forget CSP reports and have no use for an error response,
and returning `4xx` would surface garbage to operator dashboards
without giving the browser anything actionable.

### Current rate-limit and body-cap posture

> **Hardening planned under proposal #4** (CSP-report abuse mitigation).
> The values below describe the **deployed** posture today; the
> proposal will tighten them when it lands.

| Control | Current | Planned (post-#proposal-4) |
| --- | --- | --- |
| Body cap | None at the FastAPI layer (Lambda Function URL caps at 6 MB) | 8 KiB per request |
| Per-IP rate limit | None | 60 requests / 5 minutes per source IP |
| `blocked_domain` cardinality | Unbounded (any hostname becomes a CloudWatch dimension value) | Bucketed to an allowlist; everything else collapses to `other` |

Until #proposal-4 lands, an attacker who finds the endpoint can
inflate CloudWatch costs by spamming reports with arbitrary
`blocked-uri` values. The endpoint does still gate at the JSON-parse
step (malformed bodies return 204 without emitting any metric) and at
the `csp-violation` type check (modern-format reports of unrelated
types are dropped), so the attack surface is bounded to "POST a
mostly-valid report at high QPS".

## See also

- [Security and secrets](/operations/security) — operational secret
  contracts and rotation procedures
