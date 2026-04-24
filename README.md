# Hive

<!-- CI/CD & quality -->
[![CI (main)](https://github.com/warlordofmars/hive/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/warlordofmars/hive/actions/workflows/ci.yml?query=branch%3Amain)
[![CI (dev)](https://github.com/warlordofmars/hive/actions/workflows/ci.yml/badge.svg?branch=development)](https://github.com/warlordofmars/hive/actions/workflows/ci.yml?query=branch%3Adevelopment)
[![codecov](https://codecov.io/gh/warlordofmars/hive/branch/main/graph/badge.svg)](https://codecov.io/gh/warlordofmars/hive)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type--checked-mypy-blue)](https://mypy-lang.org/)

<!-- Project & versioning -->
[![GitHub release](https://img.shields.io/github/v/release/warlordofmars/hive)](https://github.com/warlordofmars/hive/releases)
[![GitHub issues](https://img.shields.io/github/issues/warlordofmars/hive)](https://github.com/warlordofmars/hive/issues)
[![GitHub stars](https://img.shields.io/github/stars/warlordofmars/hive)](https://github.com/warlordofmars/hive/stargazers)

<!-- Backend stack -->
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.x-7B2FBE?logo=python&logoColor=white)](https://github.com/jlowin/fastmcp)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![AWS Lambda](https://img.shields.io/badge/AWS_Lambda-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![DynamoDB](https://img.shields.io/badge/DynamoDB-4053D6?logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![AWS CDK](https://img.shields.io/badge/CDK-Python-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/cdk/)

<!-- Frontend stack -->
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.x-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Node](https://img.shields.io/badge/Node-20-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org/)

<!-- MCP -->
[![MCP](https://img.shields.io/badge/MCP-compatible-blueviolet)](https://modelcontextprotocol.io/)

Shared persistent memory for AI agents — works with any MCP-compatible client. Free hosted service, no AWS account required.

Hive is an MCP server that gives AI agents durable, shared memory across conversations. Connect any MCP-compatible client — Claude Code, Claude Desktop, ChatGPT, Cursor, Continue, or custom agents — store and retrieve memories by key or tag, and manage everything through a web UI.

**Hosted at [hive.warlordofmars.net](https://hive.warlordofmars.net) — sign in with Google, no setup required.**

## Getting started

1. **Sign in** at [hive.warlordofmars.net](https://hive.warlordofmars.net) with your Google account
2. **Connect your MCP client** using the config for your client below — OAuth is handled automatically on first use

**Claude Code** (`~/.claude/settings.json`) / **Cursor** (`~/.cursor/mcp.json`):

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

**Claude Desktop** / **ChatGPT** — open *Settings → Connectors* and add a custom MCP connector pointing at:

```
https://hive.warlordofmars.net/mcp
```

The browser handles OAuth on first use; no config file or local proxy required.

**Older Claude Desktop builds (no Connectors UI)** or any other stdio-based client — fall back to [`mcp-remote`](https://github.com/geelen/mcp-remote) as a local proxy:

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

OAuth is handled automatically on first use for all of the above. For detailed setup instructions see [docs/mcp-setup.md](docs/mcp-setup.md).

## What it does

AI agents are stateless — every new conversation starts blank. Hive gives them a persistent, shared memory store:

| Tool | Description |
|---|---|
| `remember(key, value, tags[])` | Store a memory |
| `recall(key)` | Retrieve a memory by key |
| `forget(key)` | Delete a memory |
| `list_memories(tag)` | List memories by tag |
| `summarize_context(topic)` | Synthesize memories on a topic into a summary |

Multiple agents or team members connect with their own OAuth clients, so you can track who stored what and revoke access individually.

Keys are opaque to the server, but a structured convention like `{domain}:{entity-type}/{entity-id}:{attribute}` (e.g. `project:task/42:summary`) keeps memory stores organised and collision-free as they grow. See the [key naming conventions](https://hive.warlordofmars.net/docs/concepts/key-conventions) docs page for details.

## Architecture

Hive is a serverless, AWS-native stack deployed on Lambda + DynamoDB behind CloudFront:

```
MCP client (Claude Code, Cursor, …)
      │  MCP / Streamable HTTP
      ▼
┌──────────────────────────────────────────────┐
│                  CloudFront                   │
│  hive.warlordofmars.net                       │
│                                               │
│  /mcp            → MCP Lambda (FastMCP)       │
│  /api/* /oauth/* → API Lambda (FastAPI)       │
│  /               → S3 (React SPA)             │
└──────────────────────────────────────────────┘
         │                       │
         └──────────┬────────────┘
                    ▼
             ┌─────────────┐
             │  DynamoDB   │
             │  (hive)     │
             └─────────────┘
```

| Layer | Technology |
|---|---|
| MCP server | FastMCP 3.x (Python) |
| Auth server | OAuth 2.1 + PKCE (self-contained, built into API Lambda) |
| Management API | FastAPI (Python) |
| Management UI | React 18 + Vite |
| Storage | DynamoDB (single-table design) |
| Hosting | AWS Lambda Function URLs + CloudFront + S3 |
| IaC | AWS CDK (Python) |
| CI/CD | GitHub Actions + OIDC |

## Documentation

| Doc | Description |
|---|---|
| [docs/mcp-setup.md](docs/mcp-setup.md) | Connecting MCP clients (Claude Code, Claude Desktop, Cursor, and more) to Hive |
| [docs/admin-ui.md](docs/admin-ui.md) | Using the management UI |
| [Hive management API reference](https://hive.warlordofmars.net/docs/api-reference) | Auto-generated OpenAPI reference (Scalar) for every REST endpoint |
| [docs/api-reference.md](docs/api-reference.md) | REST API reference (handwritten, older) |
| [docs/oauth.md](docs/oauth.md) | OAuth 2.1 implementation details |

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for local dev setup, the test workflow, and how to submit a PR.

```bash
git clone https://github.com/warlordofmars/hive
cd hive
uv sync --all-extras    # install Python deps (requires uv)
cd ui && npm install    # install JS deps
uv run inv pre-push     # lint + type check + unit tests + frontend tests
```

## Security

To report a vulnerability, use [GitHub's private vulnerability reporting](https://github.com/warlordofmars/hive/security/advisories/new) rather than opening a public issue. See [SECURITY.md](SECURITY.md) for the full disclosure policy.
