# starter (Python package)

The `starter` package contains the OAuth 2.1 authorization server, management API, storage layer, and data models.

## Package layout

```
src/starter/
├── storage.py      # DynamoDB read/write (StarterStorage class)
├── models.py       # Pydantic models + DynamoDB serialization
├── auth/
│   ├── oauth.py    # OAuth 2.1 router (authorize/token/revoke/DCR/discovery)
│   ├── dcr.py      # Dynamic Client Registration logic (RFC 7591)
│   └── tokens.py   # JWT issuance, decoding, and Bearer token validation
└── api/
    ├── main.py     # FastAPI app wiring (CORS, routers, Lambda handler)
    ├── _auth.py    # require_token FastAPI dependency
    ├── users.py    # GET/POST/PATCH/DELETE /api/users
    ├── clients.py  # GET/POST/DELETE /api/clients
    └── stats.py    # GET /api/stats, GET /api/activity
```

## Storage (`storage.py`)

`StarterStorage` is a thin wrapper around a DynamoDB `Table` resource. The constructor reads configuration from environment variables at call time (not module-import time) to support test isolation:

```python
StarterStorage(
    table_name=None,   # → STARTER_TABLE_NAME env var or "agentcore-starter-dev"
    region=None,       # → AWS_REGION env var or "us-east-1"
    endpoint_url=None, # → DYNAMODB_ENDPOINT env var (for local testing)
)
```

### DynamoDB single-table design

| Entity | PK | SK | GSIs |
|---|---|---|---|
| OAuth client | `CLIENT#{id}` | `META` | `GSI3PK=CLIENT#{id}` (ClientIndex) |
| Token | `TOKEN#{jti}` | `META` | — (TTL enabled) |
| Auth code | `AUTHCODE#{code}` | `META` | — (TTL enabled) |
| Activity log | `LOG#{date}` | `{timestamp}#{event_id}` | — |
| User | `USER#{id}` | `META` | `GSI4PK=EMAIL#{email}` (UserEmailIndex) |

## Auth (`auth/`)

### `tokens.py`

- `_jwt_secret()` — lazily loads the signing secret from `STARTER_JWT_SECRET` env var (tests/local) or SSM `/agentcore-starter/jwt-secret` (Lambda runtime); cached with `lru_cache`
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
# Management API (HTTP)
uv run uvicorn starter.api.main:app --port 8001 --reload
```

For local API development, set `STARTER_JWT_SECRET` to a fixed value so tokens survive process restarts:

```bash
STARTER_JWT_SECRET=dev-secret \
STARTER_TABLE_NAME=agentcore-starter-dev \
DYNAMODB_ENDPOINT=http://localhost:8000 \
uv run uvicorn starter.api.main:app --port 8001 --reload
```
