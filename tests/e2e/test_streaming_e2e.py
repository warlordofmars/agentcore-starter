# Copyright (c) 2026 John Carter. All rights reserved.
"""
E2e regression test: SSE streaming endpoints emit chunks in real time.

This test guards against silent buffering regressions on the deployed
edge — most notably CloudFront response compression on `/api/*`. With
compression enabled on a streaming behaviour, gzip can coalesce many
deltas into a single multi-second flush, breaking the real-time UX
that streaming endpoints are designed for. By recording the wall-
clock timestamp of each SSE chunk and asserting an inter-arrival
upper bound, this test fails fast if a CloudFront config change
silently re-introduces buffering.

Test target: the deployed CloudFront URL (`STARTER_API_URL`), not
the Lambda Function URL directly. The whole point is to exercise the
edge path that real browsers traverse.

Currently `xfail` (`strict=False`) until issue #34 lands
(`compress=False` on the `/api/*` / `/auth/*` / `/oauth/*` CloudFront
behaviours). With compression still enabled on the dev environment,
gzip buffers SSE deltas into multi-second flushes, so the assertion
would fail on every run. Once #34 ships, flip the marker off and the
strict assertion takes over. `strict=False` keeps the suite green
through the transition; if the timing somehow already passes (e.g.
infra fix lands ahead of this test), the run is reported as XPASS,
not a hard failure — the next contributor flips the marker.

Echo stream is the primary fixture (no Bedrock cost). The
invoke-stream variant is a separate smoke test gated on
`STARTER_E2E_RUN_INVOKE_STREAM=1` to avoid charging on every CI run.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator

import httpx
import pytest

API_URL = os.environ.get("STARTER_API_URL", "")

# Maximum allowed wall-clock gap between consecutive SSE chunks. Generous
# enough to absorb network jitter and TLS/handshake variability, tight
# enough to catch gzip-induced multi-second coalescing (which typically
# delays the first flush by 5-10s when buffer thresholds aren't hit).
_MAX_INTERCHUNK_GAP_SECONDS = 1.5

# Total streaming response timeout — well above the longest legitimate
# generation duration for the short echo prompt below.
_STREAM_TIMEOUT_SECONDS = 30.0


async def _record_chunk_arrival_times(
    api_url: str,
    token: str,
    path: str,
    body: dict[str, object],
) -> list[float]:
    """POST to an SSE endpoint and return monotonic timestamps of each delta.

    Returns the wall-clock arrival time of each ``data: {"type": "delta", ...}``
    SSE event. The terminating ``done`` event is excluded — it doesn't
    represent a streamed token and its timing isn't load-bearing.
    """
    timestamps: list[float] = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # Advertise gzip/br so CloudFront actually exercises its
        # compression decision for this request. Sending
        # `Accept-Encoding: identity` would let CloudFront skip
        # compression entirely, masking exactly the buffering
        # regression this test is designed to catch.
        "Accept-Encoding": "gzip, br",
        "Accept": "text/event-stream",
    }

    timeout = httpx.Timeout(_STREAM_TIMEOUT_SECONDS, connect=10.0)
    async with (
        httpx.AsyncClient(base_url=api_url, timeout=timeout) as client,
        client.stream("POST", path, headers=headers, json=body) as resp,
    ):
        resp.raise_for_status()
        async for line in _iter_sse_data_lines(resp.aiter_lines()):
            # Ignore non-delta events; only deltas reflect token-by-token streaming.
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Valid non-object JSON ([], "x", 1, true, null) decodes successfully but
            # has no .get(); guard explicitly so unexpected payloads are skipped, not
            # raised as AttributeError.
            if not isinstance(payload, dict) or payload.get("type") != "delta":
                continue
            timestamps.append(time.monotonic())
    return timestamps


async def _iter_sse_data_lines(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield the JSON payload of each ``data:`` line from an SSE stream."""
    async for raw in lines:
        if raw.startswith("data:"):
            yield raw[len("data:") :].strip()


@pytest.mark.xfail(
    reason=(
        "Issue #34 (CloudFront compress=False on /api/*) has not shipped — "
        "gzip on the streaming behaviour buffers SSE deltas. Flip this "
        "marker off once #34 lands."
    ),
    strict=False,
)
async def test_echo_stream_inter_chunk_timing(live_admin_token: str) -> None:
    """Consecutive echo-stream SSE chunks must arrive within 1.5s of each other."""
    if not API_URL:
        pytest.skip("STARTER_API_URL not set")

    # A short multi-token prompt so the model emits multiple deltas without
    # racking up cost or wall time. Echo stream is a thin wrapper over
    # Bedrock Converse, but the prompt itself is intentionally trivial.
    body = {"message": "Count to five, one number per line.", "system": None}

    timestamps = await _record_chunk_arrival_times(
        API_URL, live_admin_token, "/api/agents/echo/stream", body
    )

    assert len(timestamps) >= 2, (
        f"Expected at least 2 SSE delta chunks for timing assertion, got {len(timestamps)}. "
        "If the model produced a single-chunk reply, broaden the prompt."
    )

    gaps = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
    max_gap = max(gaps)
    assert max_gap < _MAX_INTERCHUNK_GAP_SECONDS, (
        f"Max inter-chunk gap {max_gap:.2f}s exceeds {_MAX_INTERCHUNK_GAP_SECONDS}s "
        f"threshold (gaps={[round(g, 3) for g in gaps]}). "
        "Likely cause: CloudFront response compression buffering SSE chunks; "
        "verify the /api/* behaviour has compress=False (issue #34)."
    )


@pytest.mark.xfail(
    reason=(
        "Issue #34 (CloudFront compress=False on /api/*) has not shipped — "
        "gzip on the streaming behaviour buffers SSE deltas. Flip this "
        "marker off once #34 lands."
    ),
    strict=False,
)
async def test_invoke_stream_inter_chunk_timing(live_admin_token: str) -> None:
    """Consecutive invoke-stream SSE chunks must arrive within 1.5s of each other.

    This test invokes a Bedrock inline agent on every run, which incurs
    real model cost. Gated on ``STARTER_E2E_RUN_INVOKE_STREAM=1`` so
    routine CI runs only exercise the cheap echo-stream variant.
    """
    if not API_URL:
        pytest.skip("STARTER_API_URL not set")
    if os.environ.get("STARTER_E2E_RUN_INVOKE_STREAM") != "1":
        pytest.skip(
            "Set STARTER_E2E_RUN_INVOKE_STREAM=1 to exercise the inline-agent "
            "streaming endpoint (incurs Bedrock cost)."
        )

    body = {"message": "Count to five, one number per line.", "session_id": None}

    timestamps = await _record_chunk_arrival_times(
        API_URL, live_admin_token, "/api/agents/invoke/stream", body
    )

    assert len(timestamps) >= 2, (
        f"Expected at least 2 SSE delta chunks for timing assertion, got {len(timestamps)}."
    )

    gaps = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
    max_gap = max(gaps)
    assert max_gap < _MAX_INTERCHUNK_GAP_SECONDS, (
        f"Max inter-chunk gap {max_gap:.2f}s exceeds {_MAX_INTERCHUNK_GAP_SECONDS}s "
        f"threshold (gaps={[round(g, 3) for g in gaps]}). "
        "Likely cause: CloudFront response compression buffering SSE chunks; "
        "verify the /api/* behaviour has compress=False (issue #34)."
    )
