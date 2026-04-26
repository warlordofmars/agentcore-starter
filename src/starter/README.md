# `starter` package

Module index for `src/starter/`. The OAuth 2.1 discovery endpoints,
management API, and agent wrappers live here.

For project-wide architecture, conventions, and the data model,
see the top-level [`CLAUDE.md`](../../CLAUDE.md) and
[`README.md`](../../README.md).

## Layout

```text
src/starter/
├── logging_config.py    # Structured JSON logging setup
├── metrics.py           # CloudWatch EMF metrics helpers
├── auth/
│   ├── oauth.py         # OAuth 2.1 discovery endpoints (RFC 8414 + RFC 9728); authorize/token/revoke/register not yet implemented
│   ├── tokens.py        # JWT issuance and validation (OAuth 2.1 + management sessions)
│   ├── google.py        # Google OAuth integration (management UI login)
│   └── mgmt_auth.py     # Management UI auth routes (/auth/login, /auth/callback)
├── agents/
│   ├── bedrock.py       # Converse + converse_stream (raw Bedrock)
│   └── inline_agent.py  # invoke + invoke_stream (Bedrock inline agent)
└── api/
    ├── main.py          # FastAPI app wiring (CORS, middleware, routers, /health)
    ├── _auth.py         # require_mgmt_user / require_admin FastAPI dependencies
    ├── agents.py        # Agent scaffold endpoints
    └── csp.py           # CSP violation reporting endpoint
```
