# Activity log

The Activity log shows a chronological record of every action taken against your Hive account.

## Accessing the activity log

Sign in at [hive.warlordofmars.net](https://hive.warlordofmars.net) and click the **Activity** tab.

## What's logged

| Event | When it appears |
| --- | --- |
| Memory created | A new memory was stored |
| Memory updated | An existing memory's value or tags changed |
| Memory deleted | A memory was deleted |
| Memory recalled | A memory was retrieved by key |
| Memory listed | A tag-based list was requested |
| Memory searched | A semantic search was performed |
| Context summarised | `summarize_context` was called |
| Token issued | A new OAuth token was issued |
| Token revoked | A token was revoked |
| Client registered | A new OAuth client registered |
| Client deleted | An OAuth client was removed |

## Using the log

The activity log is useful for:

- **Auditing** — understanding which client did what and when
- **Debugging** — verifying that your agent is storing and recalling memories as expected
- **Monitoring** — spotting unexpected activity (e.g. a client you didn't authorise)

## Log retention

Activity log entries are retained indefinitely.
