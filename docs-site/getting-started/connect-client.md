# Connect your MCP client

Hive works with any MCP-compatible client. OAuth is handled automatically on first use — you don't need to generate or manage tokens manually.

## Claude Code

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

The next time you use a Hive memory tool in Claude Code, it will prompt you to authorise access via your browser. Complete the flow and you're connected.

## Cursor

Add to `~/.cursor/mcp.json` (create it if it doesn't exist):

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

## Claude Desktop

Recent Claude Desktop versions support remote MCP servers as **Custom Connectors** — no config file or local proxy needed.

1. Open Claude Desktop → **Settings → Connectors**.
2. Click **Add custom connector**.
3. Paste:

   ```
   https://hive.warlordofmars.net/mcp
   ```

4. Save. Claude Desktop opens your browser to complete OAuth — approve and you're connected.

### Older Claude Desktop (pre-Connectors UI)

If your build doesn't have the Connectors menu yet, fall back to the [mcp-remote](https://github.com/geelen/mcp-remote) helper.

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

Restart Claude Desktop. On first use it will open a browser window to complete the OAuth flow.

## ChatGPT

ChatGPT supports remote MCP servers as **Apps** under Developer mode (eligibility varies by plan and may require enabling Developer mode in account settings).

1. Open ChatGPT → **Settings → Connectors**.
2. Click **Add → MCP server**.
3. Paste:

   ```
   https://hive.warlordofmars.net/mcp
   ```

4. Save. ChatGPT opens an OAuth pop-up — approve and the connector stays available across sessions.

## Continue (VS Code / JetBrains)

Add to your Continue config (`~/.continue/config.yaml`):

```yaml
mcpServers:
  - name: hive
    command: npx
    args:
      - mcp-remote
      - https://hive.warlordofmars.net/mcp
```

## claude.ai (web)

Go to **Settings → Integrations → Add MCP server** and enter:

```
https://hive.warlordofmars.net/mcp
```

## Multiple clients

You can connect multiple clients (Claude Code on your laptop, Cursor on another machine, claude.ai in the browser) simultaneously. Each client gets its own OAuth token, but they all share the same memory space under your account.

To manage or revoke individual clients, use the [OAuth clients](/ui-guide/oauth-clients) section of the management UI.

## Token refresh

Tokens expire after 1 hour and refresh automatically in Claude Code, Claude Desktop, and claude.ai. If a token expires in a client that doesn't auto-refresh, simply re-authorise by using a Hive tool — it will prompt you to complete the OAuth flow again.
