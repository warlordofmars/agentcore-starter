# Quick start

Get Hive connected and store your first memory in under 5 minutes.

## Step 1 — Sign in

Go to [hive.warlordofmars.net](https://hive.warlordofmars.net) and sign in with your Google account.

## Step 2 — Connect your MCP client

Connect Hive to your MCP client. The exact path depends on the client:

::: code-group

```text [Claude Desktop / ChatGPT]
Settings → Connectors → Add custom connector
(or Add → MCP server in ChatGPT)

URL: https://hive.warlordofmars.net/mcp
```

```json [Claude Code / Cursor]
// ~/.claude/settings.json  (Claude Code)
// ~/.cursor/mcp.json        (Cursor)
{
  "mcpServers": {
    "hive": {
      "type": "http",
      "url": "https://hive.warlordofmars.net/mcp"
    }
  }
}
```

```json [Claude Desktop (legacy mcp-remote)]
// ~/Library/Application Support/Claude/claude_desktop_config.json
// Use this only if your Claude Desktop build pre-dates the Connectors UI.
{
  "mcpServers": {
    "hive": {
      "command": "npx",
      "args": ["mcp-remote", "https://hive.warlordofmars.net/mcp"]
    }
  }
}
```

:::

The first time your agent uses a Hive tool, it will open a browser window to complete the OAuth authorisation flow. After you approve, the connection is maintained automatically.

## Step 3 — Store your first memory

Open a conversation with your AI agent and ask it to remember something:

```
Remember that my preferred Python formatter is ruff with a line length of 100.
```

Your agent will call the `remember` tool. You'll see something like:

```
Stored memory 'preferences/python-formatter'.
```

## Step 4 — Retrieve it in a new conversation

Start a fresh conversation and ask:

```
What Python formatter do I prefer?
```

Your agent will call `recall` and answer correctly — even though it's a brand new conversation with no shared context.

## What's next?

- [Full client setup instructions →](/getting-started/connect-client) for all supported clients
- [MCP tools reference →](/tools/overview) to see everything your agent can do
- [Tags and organisation →](/concepts/tags) to keep your memories tidy
