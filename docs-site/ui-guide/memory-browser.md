# Memory Browser

The Memory Browser is the main section of the management UI. It lets you view, search, create, edit, and delete your memories directly — without going through an AI agent.

## Accessing the Memory Browser

Sign in at [hive.warlordofmars.net](https://hive.warlordofmars.net) and click the **Memories** tab.

## Browsing memories

Your memories are listed in the main panel. Each card shows:
- The memory **key**
- A **type badge** for non-inline or binary memories (`Large text`, `Image`, or `Blob`)
- A preview of the **value** (first 160 characters for inline text memories; a placeholder or thumbnail for large text or binary memories)
- Any **tags** attached to the memory
- A **by {client name}** badge attributing the memory to the OAuth client that created it (falls back to the client id when the name has been deleted)

### Large text memories

When a text value exceeds 100 KB it is stored in S3 and shown with a **Large text** badge. Clicking the memory opens the full content in the edit panel (fetched from S3 on demand). You can edit and save large text memories the same way as ordinary ones.

### Image memories

Images stored via `remember_blob` show a thumbnail preview in both the list and the detail panel. Clicking a card opens a full-size preview. Images are read-only — to replace an image, use the MCP tool `remember_blob` with the same key.

### Blob memories

Non-image binary memories (PDFs, audio, etc.) show a **Blob** badge with the MIME type and file size. The detail panel has a **Download** button to save the file locally. Blobs are read-only in the UI.

## Searching memories

There are two ways to find memories:

**Semantic search** — type a phrase in the *"Search by meaning…"* box. Results are ranked by relevance and show a match score badge (e.g. "87% match"). Use this when you're not sure of the exact key or tag.

**Tag filter** — type a tag name in the *"Filter by tag"* box to show only memories with that tag. The two search modes are mutually exclusive — using one clears the other.

## Creating a memory

Click **+ New**, fill in the key, value, and optional tags (comma-separated), then click **Save**.

## Editing a memory

Click anywhere on a memory card to open the edit panel. You can update the value and tags. The key is fixed after creation.

## Deleting a memory

Click **Delete** on a memory card and confirm. Deletion is permanent.

## Pagination

If you have many memories, a **Load more** button appears at the bottom of the list. Semantic search results are not paginated — the top 50 most relevant results are returned directly.
