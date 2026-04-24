# Admin UI

The Hive management UI is a React SPA served from CloudFront. It lets you browse and manage memories, register and revoke OAuth clients, and view usage stats and activity history.

**URL:** `https://ducip68m8dmi7.cloudfront.net` (your deployed instance)

---

## Getting a token

The UI authenticates using a Bearer token stored in your browser's `localStorage`. You need a valid token before any data will load.

### Option 1: Paste a token directly

In the header bar, paste your Bearer token into the password field. The UI stores it in `localStorage` automatically.

To get a token via the CLI, see [mcp-setup.md — CLI token issuance](mcp-setup.md#cli-token-issuance).

### Option 2: Register a client and get a token

1. Open the **OAuth Clients** tab
2. Click **+ Register Client**
3. Fill in the form and click **Register**
4. Use the returned `client_id` to complete the OAuth flow and get a token (see [mcp-setup.md](mcp-setup.md))

---

## Memories tab

The default view. Shows all stored memories with controls to create, edit, and delete.

### Browsing memories

- All memories are listed by default, newest first
- **Filter by tag** — type a tag name in the filter box to narrow the list
- Click any memory card to open it in the edit panel

### Creating a memory

1. Click **+ New** (top right of the memory list)
2. Fill in:
   - **Key** — unique identifier (e.g. `project/deadline`, `team/standup-time`)
   - **Value** — the memory content (supports multi-line text)
   - **Tags** — comma-separated list (e.g. `project, deadline, q1`)
3. Click **Save**

### Editing a memory

Click any memory card to open it in the side panel. You can update the value and tags. The key cannot be changed after creation — delete and recreate if needed.

### Deleting a memory

Click **Delete** on any memory card, or use the Delete button in the edit panel. Deletion is immediate and permanent.

---

## OAuth Clients tab

Manage the OAuth 2.1 clients that have access to Hive. Each Claude agent or integration should have its own client.

### Client table

Shows all registered clients with:
- **Name** — the human-readable client name
- **Client ID** — the UUID used in OAuth flows
- **Type** — `public` (no secret) or `confidential` (has a secret)
- **Scope** — the permissions granted (`memories:read memories:write`)
- **Registered** — date the client was created

### Registering a new client

1. Click **+ Register Client**
2. Fill in:
   - **Client Name** — a descriptive name (e.g. "Alice's Agent", "CI Pipeline")
   - **Redirect URIs** — comma-separated list of allowed callback URLs
   - **Scope** — defaults to `memories:read memories:write`
   - **Auth Method** — `none` for public clients (PKCE only), `client_secret_post` or `client_secret_basic` for confidential clients
3. Click **Register**
4. **Save the client secret immediately** — it is only shown once

### Deleting a client

Click **Delete** in the client table. This immediately revokes all tokens issued to that client. Any agents using those tokens will receive 401 errors.

---

## Activity Log tab

Shows a timeline of all operations performed against Hive, plus summary stats.

### Stats bar

Four counters at the top:
- **Total Memories** — current count of stored memories
- **Total Clients** — current count of registered OAuth clients
- **Events Today** — number of operations performed today
- **Events (7 days)** — total operations in the last 7 days

### Event log

A scrollable table of all events. Use the **Show last N days** selector to control the time window (1, 7, 14, 30, or 90 days).

Each row shows:
- **Time** — local timestamp
- **Event** — color-coded event type (see below)
- **Client** — first 8 chars of the client ID that triggered the event
- **Details** — event-specific metadata (key, tags, count, etc.)

| Event type | Color | Meaning |
|---|---|---|
| `memory_created` | Green | New memory stored |
| `memory_updated` | Yellow | Existing memory modified |
| `memory_deleted` | Red | Memory deleted |
| `memory_recalled` | Blue | Memory retrieved by key |
| `memory_listed` | Blue | Memories listed by tag |
| `context_summarized` | Purple | `summarize_context` called |
| `token_issued` | Teal | New access token issued |
| `token_revoked` | Orange | Token revoked |
| `client_registered` | Light blue | New OAuth client registered |
| `client_deleted` | Dark red | OAuth client deleted |

Click **Refresh** to reload without changing the time window.
