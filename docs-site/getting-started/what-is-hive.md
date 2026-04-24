# What is Hive?

Hive is a **shared persistent memory server** for AI agents. It gives your AI assistant a long-term memory that survives across conversations, devices, and agent runs.

## The problem it solves

AI assistants are stateless by default. Every new conversation starts from scratch — the agent has no memory of what you worked on yesterday, what decisions you made last week, or what context it built up over months of use.

Hive fixes this by giving your agent a place to store and retrieve information that persists indefinitely.

## How it works

Hive implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), which means it works as a tool your AI agent can call directly during a conversation:

```
You: Remember that the API deadline is March 31st.
Agent: [calls remember("project/deadline", "API deadline is March 31st", tags=["project"])]
       Done — I'll remember that.

[new conversation, days later]

You: When is the API deadline?
Agent: [calls recall("project/deadline")]
       The API deadline is March 31st.
```

No copy-pasting context. No re-explaining your project each session. Your agent simply knows.

## Key capabilities

| Capability | Description |
| --- | --- |
| **Persistent storage** | Memories survive indefinitely across conversations |
| **Semantic search** | Find memories by meaning using natural language |
| **Tag-based organisation** | Group related memories with tags for easy retrieval |
| **Multi-client** | Use Hive from Claude Code, Claude Desktop, ChatGPT, Cursor, and more simultaneously |
| **Team sharing** | Multiple agents or team members can share a Hive instance |

## Who is it for?

- **Developers** who want their coding assistant to remember project structure, decisions, and conventions
- **Researchers** who build up context over long-running investigations
- **Teams** who want shared context across multiple AI-assisted workflows
- **Power users** who are tired of re-explaining their preferences every session

## Next steps

Ready to get started? Head to the [Quick start →](/getting-started/quick-start)
