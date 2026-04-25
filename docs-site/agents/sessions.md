# Sessions & memory

## How sessions work

Every call to `POST /api/agents/invoke` (or `/invoke/stream`) can carry a
`session_id`. Bedrock Agents uses this to maintain conversational context
— the model sees the full message history for the session without the client
re-sending it.

```
Turn 1 — no session_id (start fresh)
  → response includes session_id: "abc-123"

Turn 2 — session_id: "abc-123"
  → model remembers turn 1

Turn 3 — session_id: "abc-123"
  → model remembers turns 1 and 2
```

Omit `session_id` to start a brand-new conversation. The response always
echoes back the `session_id` — either the one you passed in, or a
freshly-generated UUID if you omitted it.

## Session scoping

Sessions are automatically namespaced to the authenticated user. The
`session_id` you pass is an opaque string from your perspective; internally
the wrapper prefixes it with the user's identity from the JWT so two users
with the same `session_id` string never share history.

This means:

- You don't need to include a `user_id` in your requests — scope comes from
  the Bearer token.
- You can use simple, human-readable session IDs (`"default"`,
  `"conversation-1"`) without worrying about collision across users.

## Session lifetime

Bedrock Agents retains session state for **1 hour of idle time** by default.
After that, the session expires and the next call with the same `session_id`
starts fresh.

You can adjust this at the boto3 call site in `agentcore.py`
(`idleSessionTTLinSeconds` on the `invoke_inline_agent` call).

## Long-term memory

By default there is no memory that persists across sessions. If a user starts
a new session, the model has no recollection of previous conversations.

To add cross-session memory, populate `inlineSessionState.promptSessionAttributes`
before calling Bedrock — for example, fetch a summary from DynamoDB and inject
it as a system-level attribute:

```python
# In agentcore.py _stream_chunks(), extend kwargs:
kwargs["inlineSessionState"] = {
    "promptSessionAttributes": {
        "user_summary": load_user_summary(user_id),  # your DynamoDB lookup
    },
}
```

The model receives `promptSessionAttributes` as additional context before
the conversation history. Keep entries short — this counts against the
model's context window.

## Action groups (tool-calling)

The starter ships with an empty action group list. To give the agent tools,
add entries to the `actionGroups` key in `agentcore.py`:

```python
kwargs["actionGroups"] = [
    {
        "actionGroupName": "SearchKnowledgeBase",
        "actionGroupExecutor": {"customControl": "RETURN_CONTROL"},
        "functionSchema": {
            "functions": [
                {
                    "name": "search",
                    "description": "Search the knowledge base for relevant documents.",
                    "parameters": {
                        "query": {
                            "type": "string",
                            "description": "The search query.",
                            "required": True,
                        }
                    },
                }
            ]
        },
    }
]
```

With `RETURN_CONTROL`, when the agent decides to call a tool, the API returns
a `returnControl` event instead of a text chunk. Your code handles the tool
call and passes the result back in the next `invoke_inline_agent` call via
`inlineSessionState.returnControlInvocationResults`.
