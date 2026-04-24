# API Reference

The Hive management API is a FastAPI application mounted at the API Lambda Function URL. All `/api/*` endpoints require a valid Bearer token. OAuth endpoints (`/oauth/*`, `/.well-known/*`) are public.

**Base URL:** `https://<api-lambda-url>/`

---

## Authentication

All `/api/*` requests must include:

```
Authorization: Bearer <access-token>
```

A 401 is returned for missing, invalid, or expired tokens. See [oauth.md](oauth.md) for how tokens are issued.

---

## Memories

### `GET /api/memories`

List or search memories.

**Query parameters:**
| Param | Type | Description |
| --- | --- | --- |
| `tag` | string | Filter to memories that have this tag (mutually exclusive with `search`) |
| `search` | string | Semantic search query — returns memories ranked by relevance (mutually exclusive with `tag`) |
| `limit` | int | Max results to return (default 50, max 200) |
| `cursor` | string | Pagination cursor from a previous response (not used with `search`) |

When `search` is provided, results include a `score` field (0.0–1.0, higher = more relevant) and are not paginated.

**Response `200`:**
```json
{
  "items": [
    {
      "memory_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "key": "project/deadline",
      "value": "March 31, 2026",
      "tags": ["project", "deadline"],
      "created_at": "2026-03-01T10:00:00Z",
      "updated_at": "2026-03-01T10:00:00Z",
      "score": 0.91
    }
  ],
  "count": 1,
  "has_more": false,
  "next_cursor": null
}
```

The `score` field is only present when `search` is used.

---

### `POST /api/memories`

Create a new memory. Returns 409 if a memory with the same key already exists.

**Request body:**
```json
{
  "key": "project/deadline",
  "value": "March 31, 2026",
  "tags": ["project", "deadline"]
}
```

**Response `201`:** Memory object (same schema as list item above)

---

### `GET /api/memories/{memory_id}`

Retrieve a memory by its UUID.

**Response `200`:** Memory object
**Response `404`:** Memory not found

---

### `PATCH /api/memories/{memory_id}`

Update a memory's value and/or tags. Key cannot be changed.

**Request body (all fields optional):**
```json
{
  "value": "Updated content",
  "tags": ["updated", "tag"]
}
```

**Response `200`:** Updated memory object
**Response `404`:** Memory not found

---

### `DELETE /api/memories/{memory_id}`

Delete a memory permanently.

**Response `204`:** Deleted
**Response `404`:** Memory not found

---

## OAuth Clients

### `GET /api/clients`

List all registered OAuth clients.

**Response `200`:**
```json
[
  {
    "client_id": "2a4507ae-a1f8-42df-8062-958f89c57153",
    "client_name": "Alice's Agent",
    "redirect_uris": ["http://localhost/cb"],
    "grant_types": ["authorization_code", "refresh_token"],
    "token_endpoint_auth_method": "none",
    "scope": "memories:read memories:write",
    "client_id_issued_at": 1743500000
  }
]
```

---

### `POST /api/clients`

Register a new OAuth client (same as the public `/oauth/register` endpoint but requires auth).

**Request body:**
```json
{
  "client_name": "My Agent",
  "redirect_uris": ["http://localhost:3000/callback"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none",
  "scope": "memories:read memories:write"
}
```

**Response `201`:** Client object. If `token_endpoint_auth_method` is not `none`, the response also includes a `client_secret` — **save it immediately, it is not stored and cannot be retrieved again**.

---

### `GET /api/clients/{client_id}`

Get a single client by ID.

**Response `200`:** Client object
**Response `404`:** Client not found

---

### `DELETE /api/clients/{client_id}`

Delete a client and immediately invalidate all of its tokens.

**Response `204`:** Deleted
**Response `404`:** Client not found

---

## Stats & Activity

### `GET /api/stats`

Current usage summary.

**Response `200`:**
```json
{
  "total_memories": 42,
  "total_clients": 3,
  "events_today": 17,
  "events_last_7_days": 94
}
```

---

### `GET /api/activity`

Activity log, newest first.

**Query parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `days` | integer | 7 | Number of days of history (1–90) |

**Response `200`:**
```json
[
  {
    "event_id": "7c3e4b2a-...",
    "event_type": "memory_created",
    "client_id": "2a4507ae-...",
    "timestamp": "2026-03-30T18:00:00Z",
    "metadata": {"key": "project/deadline", "tags": ["project"]}
  }
]
```

**Event types:** `memory_created`, `memory_updated`, `memory_deleted`, `memory_recalled`, `memory_listed`, `context_summarized`, `token_issued`, `token_revoked`, `client_registered`, `client_deleted`

---

## OAuth endpoints

### `GET /.well-known/oauth-authorization-server`

OAuth 2.1 discovery document. Used by MCP clients to auto-discover endpoints.

### `POST /oauth/register`

Dynamic Client Registration (RFC 7591). Public — no auth required.

### `GET /oauth/authorize`

Authorization endpoint. Redirects to `redirect_uri` with `code` parameter on success.

### `POST /oauth/token`

Token endpoint. Supports `authorization_code` and `refresh_token` grant types.

### `POST /oauth/revoke`

Revoke an access or refresh token.

### `GET /health`

Returns `{"status": "ok"}`. No auth required. Used for health checks.
