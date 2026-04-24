# Your first memory

Once your client is connected, here are some practical examples to get you started.

## Storing a memory

Ask your agent to remember anything you'd want to recall later:

```
Remember that the production database URL is postgres://prod.example.com/myapp
and tag it with "project" and "database".
```

Or be more explicit:

```
Use the remember tool to store key="project/db-url",
value="postgres://prod.example.com/myapp", tags=["project", "database"].
```

## Retrieving a memory

```
What's the production database URL?
```

Your agent will search its memory and call `recall("project/db-url")` automatically.

## Practical things to store

Here are patterns that work well:

| What to store | Example key | Example tags |
| --- | --- | --- |
| Project conventions | `project/myapp/conventions` | `project`, `myapp` |
| Recurring decisions | `decision/auth-approach` | `decision`, `architecture` |
| Personal preferences | `preferences/code-style` | `preferences` |
| Team context | `team/sprint-goal` | `team`, `sprint` |
| Reference information | `ref/api-endpoints` | `ref`, `api` |
| Work in progress | `wip/feature-name` | `wip` |

## Listing memories by topic

Ask your agent to list everything related to a topic:

```
List all memories tagged "project".
```

## Searching by meaning

You can search for memories even if you don't remember the exact key:

```
Search my memories for anything about database configuration.
```

## Deleting a memory

When something is no longer relevant:

```
Forget the memory with key "wip/old-feature".
```

## Tips

- **Use consistent key naming** — a hierarchy like `project/topic/subtopic` makes memories easy to recall and browse
- **Tag liberally** — tags are how you list related memories; a memory can have multiple tags
- **Update rather than accumulate** — when something changes, ask your agent to update the existing memory rather than create a new one
