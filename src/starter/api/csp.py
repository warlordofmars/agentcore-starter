# Copyright (c) 2026 John Carter. All rights reserved.
"""
CSP violation reporting endpoint.

Browsers POST CSP violation reports here when a resource is blocked (or would
be blocked, under Report-Only). We log each report structured for CloudWatch
Logs Insights and emit a ``CSPViolation`` EMF metric with dimensions that
surface *which* directive and *which* blocked-URI domain fired, so an admin
can see trends on the dashboard and alarm on unexpected spikes.

Unauthenticated on purpose — browsers don't send credentials with CSP POSTs.
Instead we rate-limit per source IP so an attacker can't amplify log volume.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from starter.logging_config import get_logger
from starter.metrics import emit_metric
from starter.storage import HiveStorage

router = APIRouter(tags=["csp"])
logger = get_logger("hive.api.csp")


# Keep a small cap so a runaway browser (or an attacker spoofing reports) can't
# flood the log; 60 per minute per IP is far above any legitimate page load.
_RATE_LIMIT_PER_MINUTE = 60

# Truncate overly-long report fields so one bogus payload can't blow up a log line.
_FIELD_MAX_LEN = 2048


def _storage() -> HiveStorage:
    return HiveStorage()


def _client_ip(request: Request) -> str:
    """Return the best-effort source IP for rate-limit keying.

    Behind CloudFront the viewer address is in ``cloudfront-viewer-address``
    as ``ip:port``; fall back to ``x-forwarded-for`` (first hop) and finally
    the socket peer.
    """
    cf = request.headers.get("cloudfront-viewer-address", "").split(":", 1)[0]
    if cf:
        return cf
    xff = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if xff:
        return xff
    return request.client.host if request.client else "unknown"


def _check_ip_rate_limit(ip: str, storage: HiveStorage) -> None:
    """Per-IP per-minute rate limit for unauthenticated CSP reports."""
    minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    bucket = f"csp#{ip}#{minute}"
    # Share the rate-limit counter table with the authenticated path; we use
    # a distinct prefix so it can't collide with a real client_id.
    count = storage.increment_rate_limit_counter("__csp__", bucket, ttl_seconds=120)
    if count > _RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many CSP reports"
        )


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _FIELD_MAX_LEN:
        return value[:_FIELD_MAX_LEN] + "…"
    return value


def _extract_legacy(body: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a Report-Only legacy ``application/csp-report`` body.

    Shape: ``{"csp-report": {"violated-directive": ..., "blocked-uri": ...}}``.
    """
    report = body.get("csp-report")
    if not isinstance(report, dict):
        return None
    return {
        "violated_directive": _truncate(report.get("violated-directive", "")),
        "effective_directive": _truncate(
            report.get("effective-directive", report.get("violated-directive", ""))
        ),
        "blocked_uri": _truncate(report.get("blocked-uri", "")),
        "document_uri": _truncate(report.get("document-uri", "")),
        "source_file": _truncate(report.get("source-file", "")),
        "line_number": report.get("line-number"),
        "column_number": report.get("column-number"),
        "disposition": report.get("disposition", "report"),
    }


def _extract_modern(report: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a modern ``application/reports+json`` entry.

    Shape: ``{"type": "csp-violation", "body": {...}, "url": ...}``.
    """
    if report.get("type") != "csp-violation":
        return None
    body = report.get("body") or {}
    return {
        "violated_directive": _truncate(body.get("effectiveDirective", "")),
        "effective_directive": _truncate(body.get("effectiveDirective", "")),
        "blocked_uri": _truncate(body.get("blockedURL", "")),
        "document_uri": _truncate(body.get("documentURL", report.get("url", ""))),
        "source_file": _truncate(body.get("sourceFile", "")),
        "line_number": body.get("lineNumber"),
        "column_number": body.get("columnNumber"),
        "disposition": body.get("disposition", "report"),
    }


def _blocked_domain(blocked_uri: str) -> str:
    """Return the blocked-URI's domain (or a safe placeholder) for EMF dimensions."""
    if not blocked_uri:
        return "none"
    if blocked_uri in {"inline", "eval", "self", "data"}:
        return blocked_uri
    parsed = urlparse(blocked_uri)
    return parsed.hostname or blocked_uri[:_FIELD_MAX_LEN]


async def _record_violation(violation: dict[str, Any]) -> None:
    """Log + emit metric for a single parsed violation.

    Two EMF emissions per report: an Environment-only aggregate (so the
    admin dashboard can pull a single count) and a fully-dimensioned
    record with ``directive`` + ``blocked_domain`` (for drill-down).
    """
    logger.warning(
        "CSP violation: %s blocked %s",
        violation["violated_directive"] or "unknown",
        violation["blocked_uri"] or "unknown",
        extra={"csp": violation},
    )
    await emit_metric("CSPViolations")
    await emit_metric(
        "CSPViolations",
        directive=violation["violated_directive"] or "unknown",
        blocked_domain=_blocked_domain(violation["blocked_uri"]),
    )


@router.post(
    "/csp-report",
    summary="Receive a browser CSP violation report",
    description=(
        "Endpoint for CSP `report-uri` and `report-to` directives. Accepts both the "
        "legacy `application/csp-report` and modern `application/reports+json` "
        "content types. Unauthenticated; rate-limited per source IP. Always "
        "returns 204 — clients ignore the body."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def receive_csp_report(
    request: Request,
    storage: Annotated[HiveStorage, Depends(_storage)],
) -> Response:
    ip = _client_ip(request)
    _check_ip_rate_limit(ip, storage)

    raw = await request.body()
    if not raw:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Malformed CSP report from %s", ip, extra={"source_ip": ip})
        # Don't 400 — a browser can't retry and we don't want to encourage probing.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    violations: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        legacy = _extract_legacy(payload)
        if legacy:
            violations.append(legacy)
    elif isinstance(payload, list):
        for report in payload:
            if isinstance(report, dict):
                modern = _extract_modern(report)
                if modern:
                    violations.append(modern)

    for v in violations:
        await _record_violation(v)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
