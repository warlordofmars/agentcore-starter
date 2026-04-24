# Hive — System Architecture

Internal/contributor reference. Not part of the customer-facing docs site.

---

## Table of contents

1. [High-level overview](#high-level-overview)
2. [AWS infrastructure](#aws-infrastructure)
3. [Request flows](#request-flows)
4. [OAuth 2.1 / PKCE flow](#oauth-21--pkce-flow)
5. [DynamoDB single-table design](#dynamodb-single-table-design)
6. [Semantic search (S3 Vectors)](#semantic-search-s3-vectors)
7. [Multi-tenancy model](#multi-tenancy-model)
8. [Security layers](#security-layers)

---

## High-level overview

Hive exposes two Lambda-backed surfaces behind a single CloudFront distribution:

| Surface | Path prefix | Lambda handler |
| --- | --- | --- |
| MCP server (FastMCP) | `/mcp*` | `hive.server.lambda_handler` |
| Management API (FastAPI) + OAuth | `/api/*`, `/auth/*`, `/oauth/*`, `/.well-known/*` | `hive.api.main.lambda_handler` |
| Management UI (React SPA) | everything else | S3 → CloudFront (static) |

```mermaid
graph LR
    subgraph Clients
        A[MCP client<br/>Claude / Cursor / Continue]
        B[Browser<br/>Management UI]
    end

    subgraph AWS
        CF[CloudFront<br/>+ WAF]
        S3UI[S3<br/>UI assets]
        LM[Lambda<br/>MCP server]
        LA[Lambda<br/>API + OAuth]
        DDB[(DynamoDB<br/>single table)]
        SV[(S3 Vectors<br/>vector indexes)]
        BR[Bedrock<br/>Titan V2]
        SSM[SSM Parameter Store<br/>secrets]
    end

    A -->|Bearer token| CF
    B --> CF
    CF -->|/mcp*| LM
    CF -->|/api/* /auth/* /oauth/*| LA
    CF --> S3UI
    LM --> DDB
    LM --> SV
    LM --> BR
    LM --> SSM
    LA --> DDB
    LA --> SSM
```

---

## AWS infrastructure

### CloudFront + WAF

- Single distribution fronts both Lambdas and the S3 UI bucket
- **Cache behaviours** (evaluated in order):
  - `/api/*`, `/auth/*`, `/oauth/*`, `/.well-known/*`, `/mcp*`, `/health` → `CachingDisabled` (no-cache), forwarded to respective Lambda Function URL
  - `default` → `CachingOptimized` (UI assets from S3)
- **WAF** (prod only): OWASP Top 10 + known bad inputs managed rule groups; rate limiting — 100 req/5 min per IP on `/oauth/*`, 1000 req/5 min globally
- **Origin verify**: Lambda rejects requests missing `X-Origin-Verify` header (value stored in SSM), preventing direct Lambda URL access

### Lambda functions

Both functions:
- Python 3.12, 512 MB, 30 s timeout
- Function URL with `auth=NONE` (CloudFront handles auth at the edge)
- X-Ray active tracing
- Environment variables injected by CDK: table name, SSM param paths, bucket names, issuer URL, app version

### DynamoDB

- Single table, `PAY_PER_REQUEST` billing
- 4 Global Secondary Indexes (see [DynamoDB design](#dynamodb-single-table-design))
- TTL on `ttl` attribute (auth codes, tokens, pending state)
- Point-in-time recovery enabled in prod

### S3 Vectors

- One bucket per environment (`hive-vectors` / `hive-vectors-{env}`)
- One index per OAuth client (`client-{client_id}`), lazy-created on first `remember()` call
- Bedrock Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`): 1024 dims, cosine distance, normalised vectors

### KMS, SSM, CloudWatch

- Customer-managed KMS keys for DynamoDB, S3, and CloudWatch Logs (prod)
- Secrets in SSM Parameter Store: JWT secret, Google OAuth credentials, email allowlist, origin-verify secret
- CloudWatch dashboard + alarms (error rate, P99 latency, DynamoDB throttles, CloudFront 5xx)

---

## Request flows

### MCP tool call (e.g. `remember`)

```mermaid
sequenceDiagram
    participant C as MCP Client
    participant CF as CloudFront + WAF
    participant LM as Lambda (MCP)
    participant DDB as DynamoDB
    participant SV as S3 Vectors
    participant BR as Bedrock

    C->>CF: POST /mcp (Bearer token)
    CF->>LM: forward (X-Origin-Verify added)
    LM->>LM: validate JWT + DDB token lookup
    LM->>DDB: PutItem (memory)
    LM->>DDB: PutItem (activity log)
    LM->>BR: InvokeModel (embed key+value)
    BR-->>LM: 1024-dim vector
    LM->>SV: PutVectors (memory_id → vector)
    LM-->>CF: "Stored memory 'key'."
    CF-->>C: tool result
```

### Management UI request

```mermaid
sequenceDiagram
    participant B as Browser
    participant CF as CloudFront
    participant LA as Lambda (API)
    participant DDB as DynamoDB

    B->>CF: GET /api/memories (mgmt JWT)
    CF->>LA: forward
    LA->>LA: decode + validate mgmt JWT
    LA->>DDB: Query (GSI or scan)
    DDB-->>LA: items
    LA-->>CF: JSON response
    CF-->>B: response
```

### Semantic search

```mermaid
sequenceDiagram
    participant C as MCP Client / Browser
    participant LM as Lambda (MCP or API)
    participant BR as Bedrock
    participant SV as S3 Vectors
    participant DDB as DynamoDB

    C->>LM: search_memories(query) / GET /api/memories?search=
    LM->>BR: InvokeModel (embed query)
    BR-->>LM: query vector
    LM->>SV: QueryVectors (topK, returnDistance)
    SV-->>LM: [(memory_id, distance), ...]
    LM->>DDB: BatchGetItem (hydrate memory objects)
    DDB-->>LM: Memory items
    LM-->>C: [{key, value, tags, score}, ...]
```

---

## OAuth 2.1 / PKCE flow

Hive implements a full OAuth 2.1 authorization server. MCP clients use the standard authorization code + PKCE flow; the management UI uses a parallel Google-backed flow.

### MCP client authorization (authorization code + PKCE)

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant C as MCP Client
    participant H as Hive OAuth (/oauth/*)
    participant G as Google OAuth

    C->>H: POST /oauth/register (DCR, RFC 7591)
    H-->>C: client_id (+ client_secret if confidential)

    C->>H: GET /oauth/authorize?response_type=code&client_id=...&code_challenge=...
    H->>H: validate client + PKCE params
    H->>G: redirect (state, nonce)
    G->>U: login page
    U->>G: credentials
    G->>H: GET /oauth/google/callback?code=...&state=...
    H->>G: exchange code → ID token
    H->>H: verify email allowlist
    H->>H: store AuthorizationCode (5 min TTL)
    H-->>C: redirect with code

    C->>H: POST /oauth/token (code + code_verifier)
    H->>H: verify PKCE (SHA-256 of verifier == challenge)
    H->>H: issue Token pair (access 1h + refresh 30d)
    H-->>C: {access_token, refresh_token, expires_in, scope}

    Note over C,H: Token refresh
    C->>H: POST /oauth/token (refresh_token)
    H->>H: validate + rotate refresh token
    H-->>C: new {access_token, refresh_token}
```

### Management UI login (Google → mgmt JWT)

```mermaid
sequenceDiagram
    participant B as Browser
    participant LA as Lambda (API)
    participant G as Google OAuth

    B->>LA: GET /auth/login
    LA->>LA: store MgmtPendingState (10 min TTL)
    LA-->>B: redirect to Google

    G->>B: login page
    B->>G: credentials
    G->>LA: GET /auth/callback?code=...&state=...
    LA->>G: exchange code → ID token
    LA->>LA: verify state (replay protection)
    LA->>LA: upsert User record (create or last_login update)
    LA->>LA: issue mgmt JWT (8h TTL, typ=mgmt)
    LA-->>B: Set-Cookie: hive_mgmt_token (or redirect with token)
```

---

## DynamoDB single-table design

All entities share one table. The entity type is encoded in the PK prefix.

### Access patterns and key schema

| Entity | PK | SK | GSI | TTL |
| --- | --- | --- | --- | --- |
| Memory (meta) | `MEMORY#{memory_id}` | `META` | GSI1: `KEY#{key}` / `KEY#{key}` | — |
| Memory (tag) | `MEMORY#{memory_id}` | `TAG#{tag}` | GSI2: `TAG#{tag}` / `MEMORY#{memory_id}` | — |
| OAuth Client | `CLIENT#{client_id}` | `META` | GSI3: `CLIENT#{client_id}` | — |
| Token | `TOKEN#{jti}` | `META` | — | ✓ (1h access / 30d refresh) |
| Authorization Code | `AUTHCODE#{code}` | `META` | — | ✓ (5 min) |
| Pending Auth (PKCE) | `PENDING#{state}` | `META` | — | ✓ (10 min) |
| User | `USER#{user_id}` | `META` | GSI4: `EMAIL#{email}` | — |
| Mgmt Pending State | `MGMT_STATE#{state}` | `META` | — | ✓ (10 min) |
| Activity Log | `LOG#{date}#{hour}` | `{timestamp}#{event_id}` | — | — |

Activity log is hour-sharded (24 partitions per day) to avoid hot partitions on high-write workloads.

### Global Secondary Indexes

```mermaid
graph TD
    T[(DynamoDB Table<br/>PK / SK)]

    T --> G1[GSI1: KeyIndex<br/>GSI1PK = KEY#key<br/>GSI1SK = KEY#key<br/>→ get_memory_by_key]
    T --> G2[GSI2: TagIndex<br/>GSI2PK = TAG#tag<br/>GSI2SK = MEMORY#id<br/>→ list_memories_by_tag]
    T --> G3[GSI3: ClientIndex<br/>GSI3PK = CLIENT#id<br/>→ get_client]
    T --> G4[GSI4: UserEmailIndex<br/>GSI4PK = EMAIL#email<br/>→ get_user_by_email]
```

### Entity relationships

```mermaid
erDiagram
    User {
        string user_id PK
        string email
        string display_name
        string role
        datetime created_at
        datetime last_login_at
    }
    OAuthClient {
        string client_id PK
        string client_secret
        string client_name
        string client_type
        string scope
        string owner_user_id FK
        datetime created_at
    }
    Memory {
        string memory_id PK
        string key
        string value
        list tags
        string owner_client_id FK
        string owner_user_id FK
        datetime created_at
        datetime updated_at
    }
    Token {
        string jti PK
        string token_type
        string client_id FK
        string scope
        datetime issued_at
        datetime expires_at
        bool revoked
    }
    AuthorizationCode {
        string code PK
        string client_id FK
        string redirect_uri
        string scope
        string code_challenge
        datetime expires_at
        bool used
    }
    ActivityEvent {
        string event_id PK
        string event_type
        string client_id FK
        datetime timestamp
        object metadata
    }

    User ||--o{ OAuthClient : "owns"
    OAuthClient ||--o{ Memory : "owns"
    OAuthClient ||--o{ Token : "holds"
    OAuthClient ||--o{ AuthorizationCode : "exchanges"
    OAuthClient ||--o{ ActivityEvent : "generates"
```

---

## Semantic search (S3 Vectors)

### Architecture

- **Dual-write**: every `remember()` write goes to DynamoDB first (authoritative), then vectors are written to S3 Vectors best-effort (failure logged, never propagated to caller)
- **One index per client**: index name `client-{client_id}`, lazy-created on first write via `CreateIndex` (swallows `ConflictException` if already exists)
- **Embedding model**: Bedrock Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`), 1024 dimensions, cosine distance, normalised
- **Indexed text**: `"{key}: {value}"` — including the key gives richer semantic coverage

### Score calculation

```
score = 1.0 - cosine_distance   (range 0.0–1.0, higher = more relevant)
```

### Resilience

| Operation | Failure behaviour |
| --- | --- |
| `upsert_memory` | Exception caught + logged; DynamoDB write already succeeded |
| `delete_memory` | Exception caught + logged; DynamoDB delete already succeeded |
| `search` | `VectorIndexNotFoundError` if client has no index yet → caller returns empty results |

---

## Multi-tenancy model

```mermaid
graph TD
    U1[User A<br/>role=admin]
    U2[User B<br/>role=user]

    C1[OAuthClient 1<br/>owned by User A]
    C2[OAuthClient 2<br/>owned by User A]
    C3[OAuthClient 3<br/>owned by User B]

    M1[Memory<br/>owner_client=C1<br/>owner_user=A]
    M2[Memory<br/>owner_client=C2<br/>owner_user=A]
    M3[Memory<br/>owner_client=C3<br/>owner_user=B]

    U1 --> C1 & C2
    U2 --> C3
    C1 --> M1
    C2 --> M2
    C3 --> M3
```

### Access rules

| Actor | Scope | Can see |
| --- | --- | --- |
| MCP client token | `memories:read` / `memories:write` | Only memories created by that `client_id` |
| Mgmt UI (role=user) | — | Only memories where `owner_user_id == sub` |
| Mgmt UI (role=admin) | — | All memories across all users |

Memories written by an MCP client set `owner_client_id` to the token's `client_id`. If the same user authorises multiple clients, memories are isolated per client unless the user queries via the management UI (which aggregates by `owner_user_id`).

---

## Security layers

| Layer | Mechanism |
| --- | --- |
| Network edge | WAF (OWASP, rate limiting) on CloudFront (prod) |
| Origin protection | `X-Origin-Verify` header — Lambda rejects requests not from CloudFront |
| MCP authentication | OAuth 2.1 Bearer JWT, validated per request against DynamoDB (revocation check) |
| Management UI authentication | Google OAuth → mgmt JWT (`typ=mgmt`, 8h TTL) |
| PKCE | Required on all authorization code flows; SHA-256 challenge/verifier |
| Least-privilege IAM | Lambda roles scoped to specific DynamoDB table, SSM params, S3 Vectors bucket |
| Secrets management | JWT secret + Google credentials in SSM Parameter Store; never in env vars for prod |
| Token lifecycle | Access: 1h, Refresh: 30d, Auth Code: 5m — all with DDB revocation support |
