# OAuth 2.1

Hive includes a self-contained OAuth 2.1 authorization server. It issues Bearer tokens that gate access to both the MCP server and the management API.

## Overview

- **Standard:** OAuth 2.1 (draft), which mandates PKCE on all authorization code flows
- **Token format:** JWT (HS256), signed with a secret stored in AWS SSM
- **Token storage:** All tokens persisted in DynamoDB with TTL for expiry/revocation
- **Client registration:** Dynamic (RFC 7591) — no manual admin step needed

## Scopes

| Scope | Grants access to |
|---|---|
| `memories:read` | `recall`, `list_memories`, `summarize_context`, `GET /api/memories` |
| `memories:write` | `remember`, `forget`, `POST/PATCH/DELETE /api/memories` |

Both scopes are granted by default on client registration.

## Authorization code flow (PKCE)

The only supported flow. All steps:

```
1. Client generates code_verifier (random 32 bytes, base64url-encoded)
2. Client derives code_challenge = BASE64URL(SHA256(code_verifier))

3. GET /oauth/authorize
     ?response_type=code
     &client_id=<id>
     &redirect_uri=<uri>
     &code_challenge=<challenge>
     &code_challenge_method=S256

   → 302 redirect to redirect_uri?code=<auth-code>

4. POST /oauth/token
     grant_type=authorization_code
     &code=<auth-code>
     &redirect_uri=<uri>
     &client_id=<id>
     &code_verifier=<verifier>

   → { access_token, token_type, expires_in, refresh_token, scope }
```

Authorization codes expire after **10 minutes** and are single-use.

## Token refresh

```
POST /oauth/token
  grant_type=refresh_token
  &refresh_token=<token>
  &client_id=<id>
```

Returns a new `access_token` and `refresh_token`. The old refresh token is revoked immediately.

## Token revocation

```
POST /oauth/revoke
  token=<access-or-refresh-token>
  &client_id=<id>
```

Immediately marks the token as revoked in DynamoDB. Subsequent requests using it receive 401.

## Dynamic Client Registration (RFC 7591)

Clients self-register without any admin interaction:

```bash
POST /oauth/register
{
  "client_name": "My Agent",
  "redirect_uris": ["http://localhost/cb"],
  "grant_types": ["authorization_code"],          # optional, defaults shown
  "token_endpoint_auth_method": "none",            # public client
  "scope": "memories:read memories:write"          # optional
}
```

**Public clients** (`token_endpoint_auth_method: "none"`) rely solely on PKCE — no client secret is issued. This is the recommended option for agents and CLI tools.

**Confidential clients** (`client_secret_post` or `client_secret_basic`) receive a `client_secret` in the registration response. **It is shown only once** and cannot be retrieved later.

## Discovery

MCP clients auto-discover the authorization server via:

```
GET /.well-known/oauth-authorization-server
```

This returns all endpoint URLs, supported grant types, scopes, and PKCE methods per the OAuth 2.0 Authorization Server Metadata spec (RFC 8414).

## Token structure

Tokens are compact JWTs. The payload:

```json
{
  "iss": "https://hive.<account>.<region>.on.aws",
  "sub": "<client-id>",
  "jti": "<unique-token-id>",
  "scope": "memories:read memories:write",
  "iat": 1743500000,
  "exp": 1743503600,
  "token_type": "access"
}
```

The `jti` is checked against DynamoDB on every request so revoked tokens are rejected even within their validity window.

## Security notes

- PKCE (S256) is **required** on all authorization code flows — plain challenges are rejected
- The JWT signing secret is stored in AWS SSM (`/hive/jwt-secret`) and read at Lambda startup — never baked into the deployment artifact
- Authorization codes are stored hashed in DynamoDB — the plain code is only ever in the redirect URL
- Token TTL is enforced at the DynamoDB level independently of JWT expiry
