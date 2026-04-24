# Copyright (c) 2026 John Carter. All rights reserved.
"""
Admin-only endpoints for CloudWatch metrics and AWS Cost Explorer data.
"""

from __future__ import annotations

import datetime as _dt
import os
import time
from typing import Annotated, Any

import boto3
from fastapi import APIRouter, Depends, HTTPException, Query

from hive.api._auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

NAMESPACE = "Hive"
ENVIRONMENT = os.environ.get("HIVE_ENV", os.environ.get("ENV", "local"))

# Seconds of CloudWatch data to fetch per period label
_PERIOD_SECONDS = {
    "1h": 3600,
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
}
# CloudWatch resolution per period (stat window size in seconds)
_STAT_PERIOD = {
    "1h": 300,  # 5-min buckets
    "24h": 3600,  # 1-hour buckets
    "7d": 86400,  # 1-day buckets
    "30d": 86400,  # 1-day buckets
}

# Cost cache: store results in a module-level dict keyed by env to avoid
# hammering the Cost Explorer API ($0.01/request). TTL = 24 h.
_cost_cache: dict[str, tuple[float, Any]] = {}
_COST_CACHE_TTL = 86400  # 24 hours

# Alarm cache: alarm state changes infrequently; cache for 5 min.
_alarm_cache: dict[str, tuple[float, Any]] = {}
_ALARM_CACHE_TTL = 300  # 5 minutes


def _cloudwatch_client():  # pragma: no cover
    return boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _ce_client():  # pragma: no cover
    return boto3.client("ce", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


def _build_metric_queries(period_label: str) -> list[dict[str, Any]]:
    """Return GetMetricData queries for all tracked metrics."""
    stat_period = _STAT_PERIOD[period_label]
    tools = ["remember", "recall", "forget", "list_memories", "summarize_context"]
    queries: list[dict[str, Any]] = []

    for tool in tools:
        safe_id = tool.replace("_", "")
        queries.append(
            {
                "Id": f"inv_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": "ToolInvocations",
                        "Dimensions": [
                            {"Name": "Environment", "Value": ENVIRONMENT},
                            {"Name": "operation", "Value": tool},
                        ],
                    },
                    "Period": stat_period,
                    "Stat": "Sum",
                },
            }
        )
        queries.append(
            {
                "Id": f"err_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": "ToolErrors",
                        "Dimensions": [
                            {"Name": "Environment", "Value": ENVIRONMENT},
                            {"Name": "operation", "Value": tool},
                        ],
                    },
                    "Period": stat_period,
                    "Stat": "Sum",
                },
            }
        )
        queries.append(
            {
                "Id": f"p99_{safe_id}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": "StorageLatencyMs",
                        "Dimensions": [
                            {"Name": "Environment", "Value": ENVIRONMENT},
                            {"Name": "operation", "Value": tool},
                        ],
                    },
                    "Period": stat_period,
                    "Stat": "p99",
                },
            }
        )

    queries.append(
        {
            "Id": "tokens_issued",
            "MetricStat": {
                "Metric": {
                    "Namespace": NAMESPACE,
                    "MetricName": "TokensIssued",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                "Period": stat_period,
                "Stat": "Sum",
            },
        }
    )
    queries.append(
        {
            "Id": "token_failures",
            "MetricStat": {
                "Metric": {
                    "Namespace": NAMESPACE,
                    "MetricName": "TokenValidationFailures",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                "Period": stat_period,
                "Stat": "Sum",
            },
        }
    )
    # CSPViolations is emitted with `directive` + `blocked_domain` dimensions;
    # the Environment-only aggregate is fetched here for the dashboard count.
    queries.append(
        {
            "Id": "csp_violations",
            "MetricStat": {
                "Metric": {
                    "Namespace": NAMESPACE,
                    "MetricName": "CSPViolations",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                "Period": stat_period,
                "Stat": "Sum",
            },
        }
    )
    # RateLimitedRequests (#367) — count of 429-equivalent responses from the
    # MCP server, the management-API auth path, and /api/memories quota checks.
    # Same twin-emit pattern as CSP: aggregate here, drill-down by endpoint
    # available via CloudWatch directly.
    queries.append(
        {
            "Id": "rate_limited_requests",
            "MetricStat": {
                "Metric": {
                    "Namespace": NAMESPACE,
                    "MetricName": "RateLimitedRequests",
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                },
                "Period": stat_period,
                "Stat": "Sum",
            },
        }
    )

    return queries


def _get_cloudwatch_metrics(period_label: str) -> dict[str, Any]:
    """Fetch metric data from CloudWatch and return structured results."""
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(seconds=_PERIOD_SECONDS[period_label])
    queries = _build_metric_queries(period_label)
    cw = _cloudwatch_client()

    try:
        resp = cw.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=now,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"CloudWatch error: {exc}") from exc

    results: dict[str, Any] = {}
    for r in resp.get("MetricDataResults", []):
        results[r["Id"]] = {
            "timestamps": [t.isoformat() for t in r.get("Timestamps", [])],
            "values": r.get("Values", []),
        }
    return results


def _get_cost_data() -> dict[str, Any]:
    """Fetch cost data from Cost Explorer, cached for 24 h."""
    import datetime

    cached = _cost_cache.get(ENVIRONMENT)
    if cached and time.time() - cached[0] < _COST_CACHE_TTL:
        return cached[1]

    ce = _ce_client()
    today = datetime.date.today()
    # Last 6 full months + current month
    start_date = (today.replace(day=1) - datetime.timedelta(days=6 * 30)).replace(day=1)

    _tag_filter = {"Tags": {"Key": "project", "Values": ["hive"], "MatchOptions": ["EQUALS"]}}

    try:
        monthly_resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date.isoformat(), "End": today.isoformat()},
            Granularity="MONTHLY",
            Filter=_tag_filter,
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            Metrics=["UnblendedCost"],
        )
        daily_start = (today - datetime.timedelta(days=30)).isoformat()
        daily_resp = ce.get_cost_and_usage(
            TimePeriod={"Start": daily_start, "End": today.isoformat()},
            Granularity="DAILY",
            Filter=_tag_filter,
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            Metrics=["UnblendedCost"],
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Cost Explorer error: {exc}") from exc

    monthly: list[dict[str, Any]] = []
    for result in monthly_resp.get("ResultsByTime", []):
        period = result["TimePeriod"]["Start"]
        by_service = {
            g["Keys"][0]: float(g["Metrics"]["UnblendedCost"]["Amount"])
            for g in result.get("Groups", [])
        }
        total = sum(by_service.values())
        monthly.append({"period": period, "total": round(total, 4), "by_service": by_service})

    daily: list[dict[str, Any]] = []
    for result in daily_resp.get("ResultsByTime", []):
        day = result["TimePeriod"]["Start"]
        total = sum(
            float(g["Metrics"]["UnblendedCost"]["Amount"]) for g in result.get("Groups", [])
        )
        if total > 0:
            daily.append({"date": day, "total": round(total, 6)})

    data: dict[str, Any] = {
        "environment": ENVIRONMENT,
        "monthly": monthly,
        "daily": daily,
        "currency": "USD",
        "note": "Cost data lags ~24 h. Cached for 24 h.",
    }
    _cost_cache[ENVIRONMENT] = (time.time(), data)
    return data


@router.get(
    "/metrics",
    summary="Get CloudWatch metrics",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Admin role required"},
        502: {"description": "CloudWatch error"},
    },
)
async def get_metrics(
    _claims: Annotated[dict[str, Any], Depends(require_admin)],
    period: Annotated[str, Query(pattern="^(1h|24h|7d|30d)$")] = "24h",
) -> dict[str, Any]:
    """Return CloudWatch metric time-series for the current environment.

    Admin-only. Period: 1h | 24h | 7d | 30d.
    """
    return {
        "period": period,
        "environment": ENVIRONMENT,
        "metrics": _get_cloudwatch_metrics(period),
    }


@router.get(
    "/costs",
    summary="Get AWS cost data",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Admin role required"},
        502: {"description": "Cost Explorer error"},
    },
)
async def get_costs(
    _claims: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Return AWS Cost Explorer monthly spend breakdown.

    Admin-only. Results cached for 24 h.
    """
    return _get_cost_data()


def _get_alarm_data() -> dict[str, Any]:
    """Fetch CloudWatch alarm states for all Hive alarms, cached for 5 min."""
    cached = _alarm_cache.get(ENVIRONMENT)
    if cached and time.time() - cached[0] < _ALARM_CACHE_TTL:
        return cached[1]

    cw = _cloudwatch_client()
    try:
        resp = cw.describe_alarms(
            AlarmNamePrefix=f"Hive-{ENVIRONMENT}-",
            AlarmTypes=["MetricAlarm"],
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"CloudWatch error: {exc}") from exc

    alarms = []
    for a in resp.get("MetricAlarms", []):
        alarms.append(
            {
                "name": a["AlarmName"],
                "description": a.get("AlarmDescription", ""),
                "state": a["StateValue"],
                "state_updated_at": a["StateUpdatedTimestamp"].isoformat(),
                "threshold": a.get("Threshold"),
                "comparison_operator": a.get("ComparisonOperator", ""),
                "metric_name": a.get("MetricName", ""),
                "namespace": a.get("Namespace", ""),
            }
        )

    data: dict[str, Any] = {"environment": ENVIRONMENT, "alarms": alarms}
    _alarm_cache[ENVIRONMENT] = (time.time(), data)
    return data


@router.get(
    "/alarms",
    summary="Get CloudWatch alarm states",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Admin role required"},
        502: {"description": "CloudWatch error"},
    },
)
async def get_alarms(
    _claims: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Return CloudWatch alarm states for all Hive-prefixed alarms.

    Admin-only. Results cached for 5 min.
    """
    return _get_alarm_data()


def _storage() -> Any:
    from hive.storage import HiveStorage

    return HiveStorage()


_AUDIT_LIMIT_DEFAULT = 100
_AUDIT_LIMIT_MAX = 500


@router.get(
    "/audit-log",
    summary="Query the compliance audit log",
    description=(
        "Immutable audit trail of every memory read/write/delete (#395). "
        "Admin-only. Use ``days`` to widen the window (capped at 90). "
        "Optional ``client_id`` / ``event_type`` filters narrow the result."
    ),
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Admin role required"},
    },
)
async def get_audit_log(
    _claims: Annotated[dict[str, Any], Depends(require_admin)],
    storage: Annotated[Any, Depends(_storage)],
    days: Annotated[int, Query(ge=1, le=90, description="Days of history to return")] = 7,
    limit: Annotated[
        int, Query(ge=1, le=_AUDIT_LIMIT_MAX, description="Max events to return")
    ] = _AUDIT_LIMIT_DEFAULT,
    client_id: Annotated[str | None, Query(description="Filter by client_id")] = None,
    event_type: Annotated[str | None, Query(description="Filter by event_type")] = None,
) -> dict[str, Any]:
    # Anchor on UTC "today" — audit shards are keyed by the event's UTC
    # date (see storage.log_audit_event) so any local-time anchor drifts
    # away from the partition keys whenever the host TZ isn't UTC.
    # Query ``days + 1`` shards so a request made just after midnight UTC
    # still sees events that landed on yesterday's shard a few seconds
    # earlier — otherwise the endpoint silently drops near-boundary
    # audit events (observed failure: tests/unit/test_admin_api.py
    # ::TestAdminAuditLog at 2026-04-20T00:00:01Z).
    today = _dt.datetime.now(_dt.timezone.utc).date()
    dates = [
        (today - _dt.timedelta(days=i)).isoformat()
        for i in range(days + 1)  # NOSONAR — days bounded by FastAPI Query(ge=1, le=90)
    ]
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    events = storage.get_audit_events_for_dates(
        dates,
        client_id=client_id,
        event_type=event_type,
        limit=limit + 1,
    )
    # Trim events older than the rolling window — the extra shard
    # captures anything that tipped over midnight, but we shouldn't
    # include events from beyond `days * 24h` ago.
    events = [e for e in events if e.timestamp >= cutoff]
    has_more = len(events) > limit
    events = events[:limit]
    return {
        "items": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "client_id": e.client_id,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata,
            }
            for e in events
        ],
        "count": len(events),
        "has_more": has_more,
    }
