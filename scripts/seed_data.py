# Copyright (c) 2026 John Carter. All rights reserved.
"""
Seed data definitions and helpers for Hive local development and personal environments.

Usage (via invoke):
  inv seed                    # seed local DynamoDB (default)
  inv seed --reset            # wipe and re-seed local DynamoDB
  inv seed --env jc           # seed deployed jc environment via management API
  inv seed --env jc --reset   # wipe and re-seed deployed jc environment

Direct usage:
  uv run python scripts/seed_data.py [--local|--env <env>] [--reset]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------

SEED_CLIENTS = [
    {
        "client_name": "Claude Desktop",
        "redirect_uris": [],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "scope": "memories:read memories:write",
        "token_endpoint_auth_method": "none",
    },
    {
        "client_name": "Automation Bot",
        "redirect_uris": [],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "scope": "memories:read memories:write",
        "token_endpoint_auth_method": "none",
    },
    {
        "client_name": "Read-Only Agent",
        "redirect_uris": [],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "scope": "memories:read",
        "token_endpoint_auth_method": "none",
    },
]

SEED_MEMORIES = [
    {
        "key": "project/hive/overview",
        "value": (
            "Hive is a shared persistent memory MCP server for Claude agents and teams. "
            "Built with FastMCP (Python), DynamoDB, and a React management UI."
        ),
        "tags": ["project", "hive", "overview"],
    },
    {
        "key": "project/hive/stack",
        "value": (
            "FastMCP (MCP server), FastAPI (management API), React/Vite (UI), "
            "DynamoDB (storage), AWS Lambda + Function URLs, CDK (IaC)."
        ),
        "tags": ["project", "hive", "stack"],
    },
    {
        "key": "project/hive/tools",
        "value": (
            "MCP tools: remember(key, value, tags), recall(key), forget(key), "
            "list_memories(tag), summarize_context(topic)."
        ),
        "tags": ["project", "hive", "tools"],
    },
    {
        "key": "project/hive/auth",
        "value": (
            "OAuth 2.1 with PKCE. Self-contained authorization server. "
            "Dynamic Client Registration (RFC 7591). Tokens stored in DynamoDB with TTL."
        ),
        "tags": ["project", "hive", "auth", "oauth"],
    },
    {
        "key": "team/standup/2026-04-01",
        "value": (
            "Discussed v0.1.0 release, activity log hot partition fix, and dynamic versioning. "
            "Next: seed data task and structured logging."
        ),
        "tags": ["team", "standup"],
    },
    {
        "key": "team/standup/2026-04-02",
        "value": (
            "Reviewed PR #45 (local MCP dev task). Identified need for seed data to demo "
            "the admin UI. Planning pagination and bulk ops for Tier 2."
        ),
        "tags": ["team", "standup"],
    },
    {
        "key": "team/standup/2026-04-03",
        "value": (
            "Implemented seed data task (#23). All pre-PR checks pass. "
            "Next up: structured logging (#17) and pagination (#19)."
        ),
        "tags": ["team", "standup"],
    },
    {
        "key": "user/preferences/code-style",
        "value": (
            "Python: ruff + mypy, line length 100, target py310. "
            "JavaScript: ESLint. Always run lint + tests before opening a PR."
        ),
        "tags": ["user", "preferences"],
    },
    {
        "key": "user/preferences/git-workflow",
        "value": (
            "Feature branches off development. Squash merge to development. "
            "Merge commit for development → main releases. "
            "Personal env 'jc' used for pre-PR deploy validation."
        ),
        "tags": ["user", "preferences", "git"],
    },
    {
        "key": "decision/storage/single-table",
        "value": (
            "Single-table DynamoDB design chosen for simplicity and cost. "
            "PK/SK pattern with GSIs for tag, key, and client lookups."
        ),
        "tags": ["decision", "storage", "dynamodb"],
    },
    {
        "key": "decision/auth/oauth21",
        "value": (
            "OAuth 2.1 with PKCE required by MCP spec. "
            "Self-contained auth server chosen to avoid external IdP dependency."
        ),
        "tags": ["decision", "auth", "oauth"],
    },
    {
        "key": "decision/activity-log/hour-sharding",
        "value": (
            "Activity log PK changed from LOG#{date} to LOG#{date}#{hour} "
            "to distribute writes across 24 DynamoDB partitions and avoid hot-partition throttling."
        ),
        "tags": ["decision", "activity-log", "dynamodb"],
    },
    {
        "key": "note/deployment/cost-tags",
        "value": (
            "AWS cost allocation tags: project=hive, env={env}, version={version}. "
            "Activate in Billing → Cost Allocation Tags (24h propagation delay)."
        ),
        "tags": ["note", "deployment", "aws"],
    },
    {
        "key": "note/deployment/environments",
        "value": (
            "Three environments: prod (HiveStack), dev (HiveStack-dev), jc (HiveStack-jc). "
            "Personal env 'jc' used for pre-PR testing before opening PRs."
        ),
        "tags": ["note", "deployment", "environments"],
    },
    {
        "key": "reference/fastmcp/lambda-constraint",
        "value": (
            "FastMCP StreamableHTTPSessionManager.run() can only be called once per instance. "
            "Lambda handler must create a fresh mcp.http_app() per invocation (not module-level)."
        ),
        "tags": ["reference", "fastmcp", "lambda"],
    },
    {
        "key": "reference/uv/commands",
        "value": (
            "Always use uv for Python deps: uv add <pkg>, uv run <cmd>, uv sync --group dev. "
            "Never use pip directly."
        ),
        "tags": ["reference", "uv", "python"],
    },
    {
        "key": "idea/cost-dashboard",
        "value": (
            "Future: display AWS cost data in the Hive admin UI via the Cost Explorer API. "
            "Requires billing:GetCostAndUsage IAM permission on the API Lambda role."
        ),
        "tags": ["idea", "ui", "aws"],
    },
    {
        "key": "idea/slack-integration",
        "value": (
            "Future: Slack alerts for PR opened/merged, pipeline pass/fail, and releases. "
            "Track in GitHub issue for full Slack + CI/CD integration."
        ),
        "tags": ["idea", "ci", "slack"],
    },
]

# Activity event types to rotate through when generating seed events
_EVENT_TYPES = [
    "memory_created",
    "memory_recalled",
    "memory_updated",
    "memory_listed",
    "memory_recalled",
    "context_summarized",
    "token_issued",
]


def _seed_events(client_id: str) -> list[dict]:
    """Generate ~50 activity events spread across the last 7 days."""
    now = datetime.now(timezone.utc)
    events = []
    total = 50
    for i in range(total):
        # Spread evenly over 7 days, newest first
        offset_seconds = int((7 * 24 * 3600) * i / total)
        ts = now - timedelta(seconds=offset_seconds)
        event_type = _EVENT_TYPES[i % len(_EVENT_TYPES)]
        metadata: dict = {}
        if "memory" in event_type:
            metadata["key"] = SEED_MEMORIES[i % len(SEED_MEMORIES)]["key"]
        if event_type == "memory_listed":
            metadata["tag"] = "project"
            metadata["count"] = 3
        if event_type == "context_summarized":
            metadata["topic"] = "project"
            metadata["memory_count"] = 3
        if event_type == "token_issued":
            metadata["client_id"] = client_id
        events.append(
            {
                "event_type": event_type,
                "client_id": client_id,
                "timestamp": ts,
                "metadata": metadata,
            }
        )
    return events


# ---------------------------------------------------------------------------
# DynamoDB table creation helper (local only)
# ---------------------------------------------------------------------------


def _ensure_table(ddb_client, table_name: str) -> None:
    """Create the Hive DynamoDB table if it doesn't already exist."""
    import contextlib

    with contextlib.suppress(Exception):
        ddb_client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
                {"AttributeName": "GSI3PK", "AttributeType": "S"},
                {"AttributeName": "GSI4PK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "KeyIndex",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "TagIndex",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "ClientIndex",
                    "KeySchema": [
                        {"AttributeName": "GSI3PK", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "UserEmailIndex",
                    "KeySchema": [
                        {"AttributeName": "GSI4PK", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )


# ---------------------------------------------------------------------------
# Local seeding (direct DynamoDB access via HiveStorage)
# ---------------------------------------------------------------------------


def seed_local(reset: bool = False) -> None:
    """Seed local DynamoDB (DynamoDB Local must be running on port 8000).

    Writes directly via HiveStorage — no HTTP round-trip required.
    """
    import boto3

    endpoint = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
    table_name = os.environ.get("HIVE_TABLE_NAME", "hive")

    ddb_client = boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )

    if reset:
        print(f"  Dropping table '{table_name}'...")
        import contextlib

        with contextlib.suppress(Exception):
            ddb_client.delete_table(TableName=table_name)
            # Wait for deletion
            waiter = ddb_client.get_waiter("table_not_exists")
            waiter.wait(TableName=table_name)

    print(f"  Ensuring table '{table_name}' exists...")
    _ensure_table(ddb_client, table_name)

    # Wait for table to become ACTIVE
    waiter = ddb_client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)

    from hive.auth.tokens import issue_jwt
    from hive.models import ActivityEvent, EventType, Memory, OAuthClient, Token
    from hive.storage import HiveStorage

    storage = HiveStorage(
        table_name=table_name,
        region="us-east-1",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )

    # Seed OAuth clients
    print(f"  Seeding {len(SEED_CLIENTS)} OAuth clients...")
    seeded_client = None
    for c in SEED_CLIENTS:
        client = OAuthClient(**c)
        storage.put_client(client)
        if seeded_client is None:
            seeded_client = client

    # Issue a long-lived token for the first seed client (useful for manual testing)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    token = Token(
        client_id=seeded_client.client_id,
        scope="memories:read memories:write",
        issued_at=now,
        expires_at=now + timedelta(days=365),
    )
    storage.put_token(token)
    bearer_jwt = issue_jwt(token)

    # Seed memories
    print(f"  Seeding {len(SEED_MEMORIES)} memories...")
    for m in SEED_MEMORIES:
        memory = Memory(
            key=m["key"],
            value=m["value"],
            tags=m["tags"],
            owner_client_id=seeded_client.client_id,
        )
        storage.put_memory(memory)

    # Seed activity events
    events = _seed_events(seeded_client.client_id)
    print(f"  Seeding {len(events)} activity events...")
    for ev in events:
        event = ActivityEvent(
            event_type=EventType(ev["event_type"]),
            client_id=ev["client_id"],
            timestamp=ev["timestamp"],
            metadata=ev["metadata"],
        )
        storage.log_event(event)

    print()
    print("  Seed complete.")
    print(f"  Bearer token (1 year TTL, client: {seeded_client.client_name}):")
    print(f"    {bearer_jwt}")


# ---------------------------------------------------------------------------
# Deployed seeding (via management API)
# ---------------------------------------------------------------------------


def seed_deployed(api_url: str, token: str, reset: bool = False) -> None:
    """Seed a deployed Hive environment via the management API.

    Args:
        api_url:  Base URL of the management API (e.g. https://xxx.on.aws).
        token:    Valid Bearer token for the management API.
        reset:    If True, delete all existing memories and clients first.
    """
    import httpx

    api_url = api_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}

    if reset:
        print("  Resetting: deleting existing memories...")
        resp = httpx.get(f"{api_url}/api/memories", headers=headers, timeout=30)
        resp.raise_for_status()
        for m in resp.json():
            httpx.delete(f"{api_url}/api/memories/{m['memory_id']}", headers=headers, timeout=30)

        print("  Resetting: deleting existing clients...")
        resp = httpx.get(f"{api_url}/api/clients", headers=headers, timeout=30)
        resp.raise_for_status()
        for c in resp.json():
            httpx.delete(f"{api_url}/api/clients/{c['client_id']}", headers=headers, timeout=30)

    # Seed clients
    print(f"  Seeding {len(SEED_CLIENTS)} OAuth clients...")
    first_client_id = None
    for c in SEED_CLIENTS:
        resp = httpx.post(f"{api_url}/api/clients", headers=headers, json=c, timeout=30)
        resp.raise_for_status()
        if first_client_id is None:
            first_client_id = resp.json()["client_id"]

    # Seed memories
    print(f"  Seeding {len(SEED_MEMORIES)} memories...")
    for m in SEED_MEMORIES:
        resp = httpx.post(
            f"{api_url}/api/memories",
            headers=headers,
            json={"key": m["key"], "value": m["value"], "tags": m["tags"]},
            timeout=30,
        )
        resp.raise_for_status()

    print()
    print("  Seed complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Hive with demo data")
    parser.add_argument(
        "--local",
        action="store_true",
        default=True,
        help="Seed local DynamoDB (default)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Deployed environment name (e.g. jc, dev). Overrides --local.",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Management API URL (deployed mode). Reads from CloudFormation if not set.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HIVE_SEED_TOKEN"),
        help="Bearer token for deployed seeding (or set HIVE_SEED_TOKEN env var).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe existing data before seeding.",
    )
    args = parser.parse_args()

    if args.env:
        api_url = args.api_url
        if not api_url:
            # Try to read from CloudFormation
            import subprocess

            stack = "HiveStack" if args.env == "prod" else f"HiveStack-{args.env}"
            result = subprocess.run(
                [
                    "aws",
                    "cloudformation",
                    "describe-stacks",
                    "--stack-name",
                    stack,
                    "--region",
                    "us-east-1",
                    "--query",
                    "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue",
                    "--output",
                    "text",
                ],
                capture_output=True,
                text=True,
            )
            api_url = result.stdout.strip()

        if not api_url:
            print(f"Error: could not determine API URL for env '{args.env}'.", file=sys.stderr)
            print("Pass --api-url or ensure the stack is deployed.", file=sys.stderr)
            sys.exit(1)

        if not args.token:
            print(
                "Error: --token or HIVE_SEED_TOKEN is required for deployed seeding.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Seeding deployed env '{args.env}' at {api_url} ...")
        seed_deployed(api_url, args.token, reset=args.reset)
    else:
        print("Seeding local DynamoDB...")
        seed_local(reset=args.reset)


if __name__ == "__main__":
    main()
