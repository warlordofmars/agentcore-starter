# Copyright (c) 2026 John Carter. All rights reserved.
"""
Shared integration test fixtures.

Integration tests run against DynamoDB Local (docker).
Start it before running: docker run -p 8000:8000 amazon/dynamodb-local:latest
"""

from __future__ import annotations

import os

import pytest

# Override AWS creds for DynamoDB Local
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8000")
os.environ.setdefault("STARTER_JWT_SECRET", "integration-test-secret")
os.environ.setdefault("STARTER_TABLE_NAME", "agentcore-starter-test")


@pytest.fixture(scope="session")
def table_name() -> str:
    return os.environ["STARTER_TABLE_NAME"]
