from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import LogQueryInput, MetricsQueryInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def _query_fingerprint(query: str) -> str:
    """Return a short SHA-256 fingerprint of a KQL query string.

    Hashes the UTF-8 encoded query and returns the first 12 hex characters.
    Used in audit log ``target_context`` so that query content is never logged
    in plain text while still allowing correlation of repeated identical queries.

    Args:
        query: Raw KQL query string.

    Returns:
        12-character lowercase hex string.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


def _time_window(hours: int) -> tuple[datetime, datetime]:
    """Compute a UTC time window ending at the current moment.

    Args:
        hours: Width of the window in hours.

    Returns:
        A ``(start, end)`` tuple of timezone-aware ``datetime`` objects where
        ``end`` is ``datetime.now(UTC)`` and ``start`` is ``end - hours``.
    """
    end = datetime.now(timezone.utc)
    return end - timedelta(hours=hours), end


def query_log_analytics(
    workspace_id: str,
    query: str,
    timespan_hours: int = 24,
    limit: int = 100,
) -> dict[str, Any]:
    """Run one bounded read-only Log Analytics query against a workspace.

    Validates inputs through ``LogQueryInput`` (which rejects multi-statement
    queries and prohibited mutation keywords), computes a UTC time window via
    ``_time_window``, and submits the query to the Azure Monitor Logs client.
    The result row set is sliced to ``limit`` before being returned.  A
    SHA-256 fingerprint of the query is included in the audit log instead of
    the raw query text to avoid logging potentially sensitive KQL.

    Args:
        workspace_id: Azure resource ID of the Log Analytics workspace.
        query: KQL query string (single statement, no mutation operations).
        timespan_hours: Look-back window in hours (1–168, default 24).
        limit: Maximum number of rows to return (1–500, default 100).

    Returns:
        On success::

            {
                "ok": True,
                "workspace_id": str,
                "count": int,
                "truncated": bool,
                "rows": [...],
                "timespan_hours": int
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "query_log_analytics"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = LogQueryInput(
                workspace_id=workspace_id,
                query=query,
                timespan_hours=timespan_hours,
                limit=limit,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        settings = load_settings()
        start, end = _time_window(validated.timespan_hours)
        response = run_with_timeout(
            callback=lambda: azure_cloud_clients.monitor["logs"].query_workspace(
                workspace_id=validated.workspace_id,
                query=validated.query,
                timespan=(start, end),
            ),
            timeout_seconds=settings.request_timeout_seconds,
        )
        if isinstance(response, dict):
            rows = list(response.get("rows", []))
        else:
            rows = list(getattr(response, "rows", None) or [])
        rows = rows[: validated.limit]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={
                "workspace_id": validated.workspace_id,
                "timespan_hours": validated.timespan_hours,
                "limit": validated.limit,
                "query_fingerprint": _query_fingerprint(validated.query),
            },
        )
        return {
            "ok": True,
            "workspace_id": validated.workspace_id,
            "count": len(rows),
            "truncated": len(rows) == validated.limit,
            "rows": rows,
            "timespan_hours": validated.timespan_hours,
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={
                "workspace_id": workspace_id,
                "timespan_hours": timespan_hours,
                "limit": limit,
                "query_fingerprint": _query_fingerprint(query),
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def get_resource_metrics(
    resource_id: str,
    metric_names: list[str],
    timespan_hours: int = 1,
    interval_minutes: int = 5,
    limit: int = 200,
) -> dict[str, Any]:
    """Read bounded time-series metrics for one Azure resource.

    Validates inputs through ``MetricsQueryInput``, computes a UTC time window
    via ``_time_window``, and queries the Azure Monitor Metrics client using
    an ISO 8601 interval string (e.g. ``"PT5M"``).  The metric list is sliced
    to ``limit`` before being returned.  Both outcomes are recorded via
    ``audit_tool_call``.

    Args:
        resource_id: Full Azure resource ID of the target resource.
        metric_names: List of metric names to retrieve (1–10 items).
        timespan_hours: Look-back window in hours (1–168, default 1).
        interval_minutes: Aggregation granularity in minutes (1–60, default 5).
        limit: Maximum number of metric series to return (1–500, default 200).

    Returns:
        On success::

            {
                "ok": True,
                "resource_id": str,
                "metric_names": [str, ...],
                "count": int,
                "truncated": bool,
                "metrics": [...]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "get_resource_metrics"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = MetricsQueryInput(
                resource_id=resource_id,
                metric_names=metric_names,
                timespan_hours=timespan_hours,
                interval_minutes=interval_minutes,
                limit=limit,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        start, end = _time_window(validated.timespan_hours)
        response = run_with_timeout(
            callback=lambda: clients.monitor["metrics"].query_resource(
                resource_uri=validated.resource_id,
                metric_names=validated.metric_names,
                timespan=(start, end),
                interval=f"PT{validated.interval_minutes}M",
            ),
            timeout_seconds=settings.request_timeout_seconds,
        )
        if isinstance(response, dict):
            metrics = list(response.get("metrics", []))
        else:
            metrics = list(getattr(response, "metrics", None) or [])
        metrics = metrics[: validated.limit]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_id": validated.resource_id,
                "metric_count": len(validated.metric_names),
                "timespan_hours": validated.timespan_hours,
                "limit": validated.limit,
            },
        )
        return {
            "ok": True,
            "resource_id": validated.resource_id,
            "metric_names": validated.metric_names,
            "count": len(metrics),
            "truncated": len(metrics) == validated.limit,
            "metrics": metrics,
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_id": resource_id, "metric_count": len(metric_names), "limit": limit},
            error_code=error_payload["error"]["code"],
        )
        return error_payload
