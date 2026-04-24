# hive (Python package)

The `hive` package contains the MCP server, OAuth 2.1 authorization server, management API, storage layer, and data models.

## Package layout

```
src/hive/
├── server.py       # FastMCP server + 5 MCP tool definitions
├── storage.py      # DynamoDB read/write (HiveStorage class)
├── models.py       # Pydantic models + DynamoDB serialization
├── auth/
│   ├── oauth.py    # OAuth 2.1 router (authorize/token/revoke/DCR/discovery)
│   ├── dcr.py      # Dynamic Client Registration logic (RFC 7591)
│   └── tokens.py   # JWT issuance, decoding, and Bearer token validation
└── api/
    ├── main.py     # FastAPI app wiring (CORS, routers, Lambda handler)
    ├── _auth.py    # require_token FastAPI dependency
    ├── memories.py # GET/POST/PATCH/DELETE /api/memories
    ├── clients.py  # GET/POST/DELETE /api/clients
    └── stats.py    # GET /api/stats, GET /api/activity
```

## MCP server (`server.py`)

Defines five tools on a `FastMCP` instance. Each tool:
1. Calls `_auth(ctx)` to extract and validate the Bearer token from the HTTP request
2. Gets a `HiveStorage` instance
3. Performs the storage operation
4. Logs an `ActivityEvent`

The Lambda entry point wraps the FastMCP ASGI app with Mangum:

```python
asgi_app = mcp.http_app(stateless_http=True, json_response=True)
handler = Mangum(asgi_app, lifespan="on")
```

Key choices:
- `stateless_http=True` — each Lambda invocation creates a fresh MCP session (no session persistence needed)
- `json_response=True` — returns `application/json` instead of SSE, compatible with Lambda's buffered response model
- `lifespan="on"` — Mangum must run ASGI startup/shutdown so FastMCP's `StreamableHTTPSessionManager` initializes its task group

## Storage (`storage.py`)

`HiveStorage` is a thin wrapper around a DynamoDB `Table` resource. The constructor reads configuration from environment variables at call time (not module-import time) to support test isolation:

```python
HiveStorage(
    table_name=None,   # → HIVE_TABLE_NAME env var or "hive"
    region=None,       # → AWS_REGION env var or "us-east-1"
    endpoint_url=None, # → DYNAMODB_ENDPOINT env var (for local testing)
)
```

### DynamoDB single-table design

| Entity | PK | SK | GSIs |
|---|---|---|---|
| Memory (canonical) | `MEMORY#{id}` | `META` | `GSI1PK=KEY#{key}` (KeyIndex) |
| Memory (tag projection) | `MEMORY#{id}` | `TAG#{tag}` | `GSI2PK=TAG#{tag}` (TagIndex) |
| OAuth client | `CLIENT#{id}` | `META` | `GSI3PK=CLIENT#{id}` (ClientIndex) |
| Token | `TOKEN#{jti}` | `META` | — (TTL enabled) |
| Auth code | `AUTHCODE#{code}` | `META` | — (TTL enabled) |
| Activity log | `LOG#{date}` | `{timestamp}#{event_id}` | — |

**TagIndex** (`GSI2PK=TAG#{tag}`) powers `list_memories(tag)` — a single GSI query returns all memories for a given tag.

**KeyIndex** (`GSI1PK=KEY#{key}`) powers `recall(key)` and duplicate-key checks — O(1) key lookup without a table scan.

## Auth (`auth/`)

### `tokens.py`

- `_jwt_secret()` — lazily loads the signing secret from `HIVE_JWT_SECRET` env var (tests/local) or SSM `/hive/jwt-secret` (Lambda runtime); cached with `lru_cache`
- `issue_jwt(token)` → signed JWT string
- `decode_jwt(token_str)` → claims dict (raises `JWTError` if invalid/expired)
- `validate_bearer_token(header, storage)` → `Token` model (raises `ValueError` on any failure)

### `dcr.py`

Validates client registration requests and creates `OAuthClient` records. Enforces:
- Only `authorization_code` and `refresh_token` grant types
- Valid `token_endpoint_auth_method` values
- Auto-generates `client_secret` for confidential clients (stored hashed)

### `oauth.py`

Full OAuth 2.1 router. Key behaviours:
- `GET /oauth/authorize` — validates PKCE challenge, creates `AuthorizationCode`, redirects
- `POST /oauth/token` — verifies PKCE verifier, issues `access_token` + `refresh_token`
- `POST /oauth/revoke` — marks token as revoked in DynamoDB
- Authorization codes are stored as SHA-256 hashes; the plain code only travels in the redirect URL

## Running locally

```bash
# MCP server (stdio transport — connect with Claude Desktop local config)
uv run python -m hive.server

# Management API (HTTP)
uv run uvicorn hive.api.main:app --port 8001 --reload
```

For local API development, set `HIVE_JWT_SECRET` to a fixed value so tokens survive process restarts:

```bash
HIVE_JWT_SECRET=dev-secret \
HIVE_TABLE_NAME=hive \
DYNAMODB_ENDPOINT=http://localhost:8000 \
uv run uvicorn hive.api.main:app --port 8001 --reload
```
