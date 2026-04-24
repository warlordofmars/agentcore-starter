# Hive UI

React 18 + Vite management SPA. Runs at `http://localhost:5173` in development and is served from CloudFront in production.

## Features

- **Memories** — browse, filter by tag, create, edit, and delete memories
- **OAuth Clients** — register new clients (RFC 7591), view existing ones, delete/revoke
- **Activity Log** — event timeline with stats (memories, clients, events today/7-day)

## Development setup

```bash
cd ui
npm install
npm run dev        # http://localhost:5173
```

The UI talks to the management API at `VITE_API_BASE` (empty by default, so it uses relative paths). When running locally against the deployed API:

```bash
VITE_API_BASE=https://<api-lambda-url> npm run dev
```

Or run the API locally:

```bash
# In another terminal
cd ..
HIVE_JWT_SECRET=dev-secret uv run uvicorn hive.api.main:app --port 8001 --reload

# Then
VITE_API_BASE=http://localhost:8001 npm run dev
```

## Authentication

The UI stores the Bearer token in `localStorage` under the key `hive_token`. Paste a valid token into the header input field — it persists across page reloads.

To get a token, see [docs/mcp-setup.md](../docs/mcp-setup.md#cli-token-issuance).

## Project structure

```
ui/src/
├── main.jsx                      # React entry point
├── App.jsx                       # Root component, tab navigation, token input
├── api.js                        # Thin fetch wrapper (reads token from localStorage)
├── setupTests.js                 # vitest + @testing-library setup
└── components/
    ├── MemoryBrowser.jsx          # Memory list + filter + create/edit form
    ├── MemoryBrowser.test.jsx     # Component tests
    ├── ClientManager.jsx          # OAuth client table + registration form
    └── ActivityLog.jsx            # Event timeline + stats cards
```

## Available scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build locally |
| `npm test` | Run vitest (single pass) |
| `npm run test:watch` | Run vitest in watch mode |
| `npm run lint` | ESLint |

## Building for production

```bash
npm run build
```

Output goes to `ui/dist/`. The CDK stack's `BucketDeployment` construct picks up this directory and uploads it to S3 as part of `cdk deploy`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE` | `""` (relative) | Base URL for the management API |

In production, the API is served from the same CloudFront domain under `/api/*` and `/oauth/*`, so `VITE_API_BASE` stays empty and all requests use relative paths.
