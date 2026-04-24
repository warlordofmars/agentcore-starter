# Tags and organisation

Tags are a lightweight way to group related memories. A memory can have any number of tags, and you can list all memories sharing a tag with a single tool call.

## How tags work

Tags are plain strings attached to a memory at creation time (or updated later). There's no predefined list — you choose whatever makes sense for your use case.

```
remember(
  key="project/myapp/auth-approach",
  value="Using JWT with 1-hour expiry and refresh tokens stored in httpOnly cookies.",
  tags=["project", "myapp", "auth", "decision"]
)
```

You can then retrieve all memories in a group:

```
List all memories tagged "decision".
```

## Suggested tag conventions

### By topic

Tag memories with the domain they belong to:

```
project, auth, database, api, frontend, infra, security
```

### By type

Tag memories with what kind of information they contain:

```
decision, convention, reference, todo, context, preference
```

### By project or team

Tag memories with the project or person they relate to:

```
myapp, client-acme, team-alice, sprint-5
```

### Combining approaches

Most useful memories have multiple tags — one for topic, one for type:

```
tags=["myapp", "auth", "decision"]
tags=["preferences", "code-style"]
tags=["project", "deadline", "reference"]
```

## Searching vs. listing by tag

| Approach | Best for |
| --- | --- |
| `list_memories(tag="auth")` | You know the exact tag and want all memories in that group |
| `search_memories("authentication")` | You want memories semantically related to auth, regardless of how they were tagged |

## Tips

- **Tag at write time** — it's easier to be consistent if you tag memories when you create them
- **Use the plural for groups** — `decisions`, `references`, `preferences` reads naturally when listing
- **Don't over-tag** — 2–4 tags per memory is usually enough
- **Combine with a key hierarchy** — tags describe *what category* a memory is in; the key describes *which specific thing* it is
