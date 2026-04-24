# How memory scoping works

Understanding how memories are scoped helps you predict what your agent can and can't see.

## The ownership model

Every memory belongs to the **OAuth client** that created it. When your Claude Code instance stores a memory, that memory is owned by the Claude Code OAuth client.

```
Your account
├── OAuth client: "Claude Code (laptop)"
│   ├── memory: project/deadline
│   ├── memory: preferences/code-style
│   └── memory: ref/api-docs
├── OAuth client: "Cursor (laptop)"
│   ├── memory: project/current-task
│   └── memory: ref/db-schema
└── OAuth client: "Claude Desktop (home)"
    └── memory: personal/reading-list
```

## What each client sees

When an MCP client calls `recall`, `list_memories`, or `search_memories`, it only sees **memories owned by that client**. Claude Code can't read memories created by Cursor, and vice versa.

This isolation is intentional — it prevents one client from accidentally reading or overwriting another client's context.

## The management UI sees everything

When you browse memories in the management UI at [hive.warlordofmars.net](https://hive.warlordofmars.net), you see **all memories across all your clients**. You can browse, edit, and delete any of them regardless of which client created them.

## Sharing memories across clients

If you want multiple clients to share memory, the simplest approach is to have each client use a common key convention and have the appropriate client write to it. Alternatively, you can create memories directly in the management UI — those will also be visible to all your clients that have read access.

## Team sharing

If multiple people use the same Hive instance (e.g. a shared team deployment), each person's account is isolated from others. Admin users can see all memories across all accounts via the management UI, but standard users only see their own.
