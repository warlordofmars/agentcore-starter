# OAuth clients

Each MCP client connection (Claude Code, Cursor, Claude Desktop, etc.) creates an **OAuth client** — a named credential that holds its own access token.

## Viewing your clients

Sign in at [hive.warlordofmars.net](https://hive.warlordofmars.net) and click the **Clients** tab. You'll see all active OAuth clients with their name and creation date.

## How clients are created

Clients are created automatically when you connect an MCP client for the first time. The client application registers itself via [Dynamic Client Registration (RFC 7591)](https://tools.ietf.org/html/rfc7591) and then walks you through the OAuth authorisation flow.

You don't need to create clients manually.

## Memory isolation

Each client has its own memory space. A memory stored by your Claude Code client is not automatically visible to your Cursor client — they each have separate scoped views.

You can see all your memories across all clients in the [Memory Browser](/ui-guide/memory-browser) when signed into the management UI.

## Revoking access

To revoke a client's access, click **Delete** on its card. The client's token is immediately invalidated and any future requests using that token will be rejected. The memories created by that client are not deleted — they remain accessible via the management UI and other clients.

To reconnect after deletion, simply use a Hive tool from that client again — it will re-register and prompt for re-authorisation.
