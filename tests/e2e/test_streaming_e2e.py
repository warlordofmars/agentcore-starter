# Copyright (c) 2026 John Carter. All rights reserved.
"""
E2e regression test: SSE streaming endpoints emit chunks in real time.

This test guards against silent buffering regressions on the deployed
edge — most notably CloudFront response compression on `/api/*`. With
compression enabled on a streaming behaviour, gzip can coalesce many
deltas into a single multi-second flush, breaking the real-time UX
that streaming endpoints are designed for. By recording the monotonic
arrival time of each transport-level chunk and asserting an
inter-arrival upper bound, this test fails fast if a CloudFront
config change silently re-introduces buffering.

Test target: the deployed CloudFront URL (`STARTER_UI_URL`), not
the Lambda Function URL (`STARTER_API_URL` resolves to
`ApiFunctionUrl` in `tasks.e2e()`, which bypasses CloudFront
entirely). CloudFront serves the React SPA at the apex and proxies
`/api/*` to the same Lambda — so `${STARTER_UI_URL}/api/agents/...`
is the actual edge path real browsers traverse, and is the only
path that exercises CloudFront's compression decision. Hitting the
Lambda Function URL directly would skip CloudFront and silently
mask the very buffering regression this test is meant to catch.

Why transport-level timing: `aiter_lines()` yields lines from an
in-memory text buffer, so a single TCP flush carrying ten SSE events
back-to-back would yield those ten events with near-zero gaps
between them — the multi-second buffering delay would show up only
as a single large pre-amble, easy to miss with a naive max-gap
assertion. We instead use `aiter_raw()` to record arrivals at the
network-flush level and additionally assert time-to-first-byte, so
both end-of-response coalescing and start-of-response stalls are
caught.

Currently `xfail` (`strict=False`) until issue #34 lands
(`compress=False` on the `/api/*` / `/auth/*` / `/oauth/*` CloudFront
behaviours). With compression still enabled on the dev environment,
gzip buffers SSE deltas into multi-second flushes, so the assertion
would fail on every run. Once #34 ships, flip the marker off and the
strict assertion takes over. `strict=False` keeps the suite green
through the transition; if the timing somehow already passes (e.g.
infra fix lands ahead of this test), the run is reported as XPASS,
not a hard failure — the next contributor flips the marker.

Cost note: both `/agents/echo/stream` and `/agents/invoke/stream`
call Bedrock on every request. Echo wraps `converse_stream` directly,
which is cheaper per-call than the inline-agent overhead in
`invoke_stream` but still incurs token charges. The echo test runs
unconditionally because deployed e2e is only triggered on dev/main
deploys (not on every PR). The invoke-stream variant is additionally
gated behind `STARTER_E2E_RUN_INVOKE_STREAM=1` because inline-agent
spend per call is meaningfully higher.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import httpx
import pytest

# STARTER_UI_URL is the CloudFront URL (UiUrl CloudFormation output);
# CloudFront proxies /api/* to the same Lambda the Function URL serves.
# We deliberately do NOT use STARTER_API_URL — that's the Lambda
# Function URL, which bypasses CloudFront entirely and would defeat
# the purpose of this test. The live_admin_token fixture issues the
# JWT via STARTER_API_URL on its own; the JWT is host-agnostic and
# is accepted at the CloudFront edge as well.
EDGE_URL = os.environ.get("STARTER_UI_URL", "")

# Maximum allowed monotonic gap between consecutive transport-level
# chunks. Generous enough to absorb network jitter and TLS handshake
# variability, tight enough to catch gzip-induced multi-second
# coalescing (which typically delays the first flush by 5-10s when
# buffer thresholds aren't hit).
_MAX_INTERCHUNK_GAP_SECONDS = 1.5

# Maximum acceptable time-to-first-byte. Catches the case where
# CloudFront swallows every chunk and only releases the response when
# the origin closes the connection. Set generously to absorb cold-
# start latency on the Lambda + Bedrock model invocation.
_MAX_TIME_TO_FIRST_BYTE_SECONDS = 8.0

# Total streaming response timeout — well above the longest
# legitimate generation duration for the short prompt below.
_STREAM_TIMEOUT_SECONDS = 30.0


@dataclass
class _StreamObservation:
    """Network-level timing data for one SSE response.

    `chunk_arrival_times` are monotonic timestamps, one per TCP-flush
    chunk yielded by `aiter_raw()`. `delta_count` is the number of
    `{"type": "delta"}` SSE events parsed from the assembled body —
    used to fail loudly if the response had too few deltas to give
    the timing assertion any signal at all.
    """

    request_start: float
    chunk_arrival_times: list[float]
    delta_count: int


async def _observe_sse_stream(
    edge_url: str,
    token: str,
    path: str,
    body: dict[str, object],
) -> _StreamObservation:
    """POST to an SSE endpoint and record transport-level chunk arrival timing.

    Records the monotonic arrival time of each raw network chunk
    (using `aiter_raw()` so each yield corresponds to a TCP flush from
    the origin via CloudFront, not to a line of in-memory text).
    Separately parses the assembled body for SSE `delta` events so we
    can assert the response actually exercised the streaming path.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # Advertise gzip so CloudFront actually exercises its
        # compression decision for this request. Sending
        # `Accept-Encoding: identity` would let CloudFront skip
        # compression entirely, masking exactly the buffering
        # regression this test is designed to catch. We deliberately
        # omit `br` because brotli is an optional httpx extra; gzip
        # alone is sufficient to trigger the compression path on
        # CloudFront and is supported by Python's stdlib for
        # post-stream decoding below.
        "Accept-Encoding": "gzip",
        "Accept": "text/event-stream",
    }

    chunk_arrival_times: list[float] = []
    raw_body = bytearray()
    content_encoding = ""

    timeout = httpx.Timeout(_STREAM_TIMEOUT_SECONDS, connect=10.0)
    request_start = time.monotonic()
    async with (
        httpx.AsyncClient(base_url=edge_url, timeout=timeout) as client,
        client.stream("POST", path, headers=headers, json=body) as resp,
    ):
        resp.raise_for_status()
        content_encoding = resp.headers.get("content-encoding", "").lower()
        # aiter_raw yields raw network bytes as they arrive — each
        # yield reflects a TCP flush, not an in-memory line iteration.
        # That's the timing signal we need; aiter_lines() would mask
        # buffering by emitting many lines back-to-back from a single
        # flush. The trade-off: aiter_raw bytes are *not* decompressed
        # by httpx, so if the server applied gzip/br we have to undo
        # that ourselves before parsing SSE.
        async for raw_chunk in resp.aiter_raw():
            chunk_arrival_times.append(time.monotonic())
            raw_body.extend(raw_chunk)

    decoded_body = _decompress_body(bytes(raw_body), content_encoding)
    delta_count = _count_sse_deltas(decoded_body)
    return _StreamObservation(
        request_start=request_start,
        chunk_arrival_times=chunk_arrival_times,
        delta_count=delta_count,
    )


def _decompress_body(body: bytes, content_encoding: str) -> bytes:
    """Decompress a response body if Content-Encoding indicates gzip.

    `aiter_raw()` returns network bytes without applying content
    decoding, so we have to handle gzip ourselves before parsing SSE.
    Identity / unset encoding falls through unchanged. We don't
    advertise `br` upstream (see the request-header comment), so we
    don't need to handle it here.
    """
    if content_encoding == "gzip":
        import gzip

        return gzip.decompress(body)
    return body


def _count_sse_deltas(body: bytes) -> int:
    """Return the number of ``{"type": "delta"}`` SSE events in a response body.

    Decodes the body once after the stream completes; the timing
    signal we care about lives in `chunk_arrival_times`, not here.
    Robust to non-object JSON (`[]`, `"x"`, `1`, `true`, `null`)
    showing up on `data:` lines — those decode successfully but have
    no `.get()`, so we guard with `isinstance(..., dict)`.
    """
    count = 0
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        payload_text = line[len("data:") :].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("type") == "delta":
            count += 1
    return count


def _assert_streaming_timing_is_real_time(observation: _StreamObservation) -> None:
    """Fail the test if the stream looks like it was buffered, not streamed.

    Three orthogonal signals, each catching a different buffering
    failure mode:

    * `delta_count >= 2` — sanity check; if the response had only one
      delta there's no inter-chunk timing to assert against.
    * `time-to-first-byte` — catches "buffer everything, flush at end"
      where the response body arrives in one giant chunk after the
      origin closes the connection.
    * `max inter-chunk gap` — catches periodic flushes; even one
      multi-second stall between flushes is enough to break the
      real-time UX.
    """
    assert observation.delta_count >= 2, (
        f"Expected at least 2 SSE delta events to give the timing "
        f"assertion signal, got {observation.delta_count}. If the "
        "model produced a single-delta reply, broaden the prompt."
    )
    assert observation.chunk_arrival_times, (
        "No transport-level chunks were observed — the response may have been empty."
    )

    time_to_first_byte = observation.chunk_arrival_times[0] - observation.request_start
    assert time_to_first_byte < _MAX_TIME_TO_FIRST_BYTE_SECONDS, (
        f"Time-to-first-byte {time_to_first_byte:.2f}s exceeds "
        f"{_MAX_TIME_TO_FIRST_BYTE_SECONDS}s threshold. Likely cause: "
        "CloudFront buffered the entire response and only released it "
        "when the origin closed the connection (issue #34: verify the "
        "/api/* behaviour has compress=False)."
    )

    arrivals = observation.chunk_arrival_times
    if len(arrivals) >= 2:
        gaps = [arrivals[i] - arrivals[i - 1] for i in range(1, len(arrivals))]
        max_gap = max(gaps)
        assert max_gap < _MAX_INTERCHUNK_GAP_SECONDS, (
            f"Max inter-chunk gap {max_gap:.2f}s exceeds "
            f"{_MAX_INTERCHUNK_GAP_SECONDS}s threshold "
            f"(gaps={[round(g, 3) for g in gaps]}). Likely cause: "
            "CloudFront response compression buffering SSE chunks; "
            "verify the /api/* behaviour has compress=False (issue "
            "#34)."
        )


@pytest.mark.xfail(
    reason=(
        "Issue #34 (CloudFront compress=False on /api/*) has not shipped — "
        "gzip on the streaming behaviour buffers SSE deltas. Flip this "
        "marker off once #34 lands."
    ),
    strict=False,
)
async def test_echo_stream_inter_chunk_timing(live_admin_token: str) -> None:
    """Echo-stream SSE chunks arrive in real time at the CloudFront edge."""
    if not EDGE_URL:
        pytest.skip("STARTER_UI_URL not set (CloudFront edge URL is required for this test)")

    # A short multi-token prompt so the model emits multiple deltas
    # without racking up wall-time. Echo wraps `converse_stream`, so
    # this still hits Bedrock and incurs token charges — see the
    # cost note in the module docstring.
    body = {"message": "Count to five, one number per line.", "system": None}

    observation = await _observe_sse_stream(
        EDGE_URL, live_admin_token, "/api/agents/echo/stream", body
    )
    _assert_streaming_timing_is_real_time(observation)


@pytest.mark.xfail(
    reason=(
        "Issue #34 (CloudFront compress=False on /api/*) has not shipped — "
        "gzip on the streaming behaviour buffers SSE deltas. Flip this "
        "marker off once #34 lands."
    ),
    strict=False,
)
async def test_invoke_stream_inter_chunk_timing(live_admin_token: str) -> None:
    """Inline-agent streaming SSE chunks arrive in real time at the CloudFront edge.

    Gated on ``STARTER_E2E_RUN_INVOKE_STREAM=1`` because inline-agent
    spend per call is meaningfully higher than echo-stream. Routine
    CI runs only exercise the cheaper echo path; this test runs on
    demand to catch buffering regressions specific to the inline-
    agent streaming surface.
    """
    if not EDGE_URL:
        pytest.skip("STARTER_UI_URL not set (CloudFront edge URL is required for this test)")
    if os.environ.get("STARTER_E2E_RUN_INVOKE_STREAM") != "1":
        pytest.skip(
            "Set STARTER_E2E_RUN_INVOKE_STREAM=1 to exercise the inline-agent "
            "streaming endpoint (incurs higher Bedrock cost than echo)."
        )

    body = {"message": "Count to five, one number per line.", "session_id": None}

    observation = await _observe_sse_stream(
        EDGE_URL, live_admin_token, "/api/agents/invoke/stream", body
    )
    _assert_streaming_timing_is_real_time(observation)
