# FAQ

## Privacy and data

### Is my data private?

Yes. Your memories are stored in your account and are only accessible to:

- Your own OAuth clients (MCP agents you've authorised)
- You, when signed into the management UI
- Hive administrators (for service operation and support purposes only)

Memories are never shared between accounts, and Hive does not use your data to train any model.

### Where is my data stored?

Data is stored on AWS infrastructure (DynamoDB, S3 Vectors) in the US East region. Data is encrypted at rest and in transit. A full list of third parties that process data on our behalf — AWS, Google OAuth, and Google Analytics — is maintained on the [Subprocessors page](https://hive.warlordofmars.net/subprocessors).

### Can Anthropic or other AI providers see my memories?

No. Hive is independent infrastructure. Memories are stored on Hive's servers, not with any AI provider. When your AI agent calls the `recall` tool and gets back a value, that value is passed to the AI as part of the conversation context — just like any other text — but it's not stored or retained by the AI provider beyond normal conversation handling.

### What happens to my data if I delete my account?

All memories, OAuth clients, tokens, and activity log entries associated with your account are permanently deleted.

---

## Limits

### How many memories can I store?

Free accounts can store up to 500 memories. Once you reach the limit, new `remember` calls are rejected until you delete existing memories. Large memory stores may also affect search and retrieval performance.

### How large can a memory value be?

Up to approximately 380 KB of text per memory. This is enough for several pages of documentation, a large code file, or a detailed notes dump.

### How long are tokens valid?

Access tokens are valid for **1 hour** and refresh automatically in supported clients (Claude Code, Claude Desktop, ChatGPT, claude.ai). Refresh tokens are valid for **30 days**.

---

## Account and access

### How do I revoke access from a specific client?

Go to the **Clients** tab in the management UI and click **Delete** on the client you want to revoke. The token is immediately invalidated. See [OAuth clients](/ui-guide/oauth-clients) for details.

### How do I delete my account?

Sign into the management UI and go to **Settings → Delete account**. This permanently deletes all your data.

If you can't access your account, contact support.

### How do I export my data?

Sign into the management UI and click **Settings → Export my data**. You'll download a JSON file with your profile, all memories, OAuth clients, and the last 90 days of activity. The same data is available programmatically via `GET /api/account/export` (Bearer auth required). Rate-limited to one export per 5 minutes.

### Can I use Hive with multiple devices?

Yes. Each device or client registers its own OAuth connection. They all share the same underlying memory store under your account.

### Can I share memories with a teammate?

Not directly between accounts today. If you're on a shared team deployment, an admin can see all memories. Per-memory sharing between accounts is planned for a future release.

---

## Technical

### What is MCP?

MCP (Model Context Protocol) is an open standard for connecting AI agents to tools and data sources. It lets your AI assistant call external services — like Hive — as naturally as it calls any other capability. Learn more at [modelcontextprotocol.io](https://modelcontextprotocol.io).

### Does Hive work offline?

No. Hive requires a network connection to store and retrieve memories, since data is stored on Hive's servers.

### Can I self-host Hive?

Yes — Hive is open source. See the [GitHub repository](https://github.com/warlordofmars/hive) for deployment instructions using AWS CDK.
