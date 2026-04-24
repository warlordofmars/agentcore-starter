# Connecting to Hive via MCP

Hive exposes a standard MCP server over Streamable HTTP at `https://hive.warlordofmars.net/mcp`.

Authentication uses OAuth 2.1 with Dynamic Client Registration (DCR) — supported MCP clients handle the full auth flow automatically. You never need to manually register a client or obtain a token.

---

## Claude Code

Claude Code supports HTTP MCP servers natively with built-in OAuth 2.1 + DCR.

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "hive": {
      "type": "http",
      "url": "https://hive.warlordofmars.net/mcp"
    }
  }
}
```

On first use Claude Code will open a browser window to complete the OAuth flow. After authorising, the token is stored and refreshed automatically.

---

## Claude Desktop

Recent Claude Desktop builds support remote MCP servers as **Custom Connectors** — no config file or local proxy required.

1. Open Claude Desktop → **Settings → Connectors**.
2. Click **Add custom connector**.
3. Paste `https://hive.warlordofmars.net/mcp` and save.
4. Approve the OAuth flow in the browser pop-up.

### Older builds (pre-Connectors UI)

Use [`mcp-remote`](https://github.com/geelen/mcp-remote) as a local proxy — it handles DCR and the OAuth flow automatically.

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hive": {
      "command": "npx",
      "args": ["mcp-remote", "https://hive.warlordofmars.net/mcp"]
    }
  }
}
```

Restart Claude Desktop. On first use `mcp-remote` will open a browser window to complete the OAuth flow.

---

## ChatGPT

ChatGPT supports remote MCP servers as **Apps** under Developer mode (eligibility varies by plan).

1. Open ChatGPT → **Settings → Connectors**.
2. Click **Add → MCP server**.
3. Paste `https://hive.warlordofmars.net/mcp` and save.
4. Approve the OAuth pop-up that follows.

---

## Cursor

Cursor supports HTTP MCP servers natively with built-in OAuth 2.1 + DCR — the same config format as Claude Code.

Add to `~/.cursor/mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "hive": {
      "type": "http",
      "url": "https://hive.warlordofmars.net/mcp"
    }
  }
}
```

Restart Cursor. On first use it will open a browser window to complete the OAuth flow.

---

## Continue

Continue supports MCP servers via `mcp-remote`. Add to `.continue/config.yaml` in your project or home directory:

```yaml
mcpServers:
  - name: hive
    command: npx
    args:
      - mcp-remote
      - https://hive.warlordofmars.net/mcp
```

On first use `mcp-remote` will open a browser window to complete the OAuth flow.

---

## claude.ai (web)

In your claude.ai account settings, navigate to **Integrations → Add MCP server**:

- **Name:** Hive
- **URL:** `https://hive.warlordofmars.net/mcp`

claude.ai will prompt you to authorise via OAuth on first use.

---

## Claude SDK / custom agents

The Claude SDK does not perform DCR or OAuth automatically — you need a pre-issued Bearer token.

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    mcp_servers=[
        {
            "type": "url",
            "url": "https://hive.warlordofmars.net/mcp",
            "name": "hive",
            "authorization_token": "<your-access-token>",
        }
    ],
    messages=[{"role": "user", "content": "Remember that the project deadline is March 31."}],
    betas=["mcp-client-2025-04-04"],
)
```

To obtain a token manually, use the [CLI flow](#manual-token-issuance) below or the management UI.

---

## Manual token issuance

Only needed for the Claude SDK or custom agents — Desktop, Code, and claude.ai handle this automatically.

```bash
# 1. Register a client
curl -s -X POST https://hive.warlordofmars.net/oauth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name": "My Agent", "redirect_uris": ["http://localhost/cb"]}' \
  | jq .

# Save client_id from the response

# 2. Generate PKCE verifier + challenge
VERIFIER=$(python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode())")
CHALLENGE=$(python3 -c "import base64,hashlib,sys; v=sys.argv[1].encode(); print(base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode())" "$VERIFIER")

# 3. Get authorization code
curl -s -G https://hive.warlordofmars.net/oauth/authorize \
  --data-urlencode "response_type=code" \
  --data-urlencode "client_id=<client-id>" \
  --data-urlencode "redirect_uri=http://localhost/cb" \
  --data-urlencode "code_challenge=$CHALLENGE" \
  --data-urlencode "code_challenge_method=S256" \
  -D - | grep location

# Extract `code` from the redirect URL

# 4. Exchange code for token
curl -s -X POST https://hive.warlordofmars.net/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=<code>" \
  -d "redirect_uri=http://localhost/cb" \
  -d "client_id=<client-id>" \
  -d "code_verifier=$VERIFIER"
```

Tokens are valid for **1 hour**. Use the `refresh_token` to get a new access token without re-authenticating.

---

## Available MCP tools

| Tool | Description | Parameters |
| --- | --- | --- |
| `remember` | Store or update a memory | `key` (str), `value` (str), `tags` (list[str]) |
| `recall` | Retrieve a memory by key | `key` (str) |
| `forget` | Delete a memory | `key` (str) |
| `list_memories` | List all memories with a given tag | `tag` (str), `limit` (int), `cursor` (str) |
| `summarize_context` | Synthesize memories on a topic into a summary | `topic` (str) |
| `search_memories` | Search memories by semantic similarity | `query` (str), `top_k` (int, default 10) |

---

## Shared memory across agents

Because all agents connect to the same Hive instance, memories stored by one agent are immediately available to others. Use tags to namespace memories by team, project, or topic:

```
remember(key="team/alice/current-task", value="...", tags=["team", "alice"])
remember(key="project/hive/status", value="...", tags=["project", "hive"])
list_memories(tag="project")  # → all project memories across all agents
```

---

## Token management

- Tokens expire after **1 hour** — Desktop, Code, and claude.ai refresh automatically
- Each OAuth client gets its own tokens — revoke one client without affecting others
- To refresh manually: `POST /oauth/token` with `grant_type=refresh_token&refresh_token=<token>`
- To revoke: `POST /oauth/revoke` with `token=<token>`
- Manage clients via the [management UI](admin-ui.md) or the [API](api-reference.md#clients)
