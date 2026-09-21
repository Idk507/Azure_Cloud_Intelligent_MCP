from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import CostQueryInput, PaginationInput, ResourceGroupInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def get_cost_summary(scope: str, days: int = 30) -> dict[str, Any]:
    """Return a bounded cost summary for a subscription or resource scope.

    Queries the Azure Cost Management API for daily pre-tax cost aggregated by
    service name over the requested number of days.  The date window is
    computed at call time (``today - days`` → ``today``) so results are always
    current.  The call is wrapped in ``run_with_timeout`` and both outcomes
    are recorded via ``audit_tool_call``.

    Args:
        scope: Azure resource scope string, e.g.
               ``"/subscriptions/<id>"`` or a resource-group scope.
        days:  Number of calendar days to include in the query window
               (1–90, default 30).

    Returns:
        On success::

            {
                "ok": True,
                "scope": str,
                "days": int,
                "count": int,
                "rows": [...]   # raw row data from the Cost Management API
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "get_cost_summary"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = CostQueryInput(scope=scope, days=days)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        settings = load_settings()
        end_date = date.today()
        start_date = end_date - timedelta(days=validated.days)
        response = run_with_timeout(
            callback=lambda: azure_cloud_clients.cost.query.usage(
                scope=validated.scope,
                parameters={
                    "type": "Usage",
                    "timeframe": "Custom",
                    "time_period": {
                        "from": start_date.isoformat(),
                        "to": end_date.isoformat(),
                    },
                    "dataset": {
                        "granularity": "Daily",
                        "aggregation": {"total_cost": {"name": "PreTaxCost", "function": "Sum"}},
                        "grouping": [{"type": "Dimension", "name": "ServiceName"}],
                    },
                },
            ),
            timeout_seconds=settings.request_timeout_seconds,
        )
        rows = list(getattr(response, "rows", None) or response.get("rows", []) if isinstance(response, dict) else [])
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"scope": validated.scope, "days": validated.days},
        )
        return {
            "ok": True,
            "scope": validated.scope,
            "days": validated.days,
            "count": len(rows),
            "rows": rows,
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"scope": scope, "days": days},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def list_advisor_recommendations(
    resource_group: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List bounded Azure Advisor recommendations at subscription or resource-group scope.

    When ``resource_group`` is provided the query is scoped to that group;
    otherwise all recommendations visible at subscription level are returned.
    Results are capped at ``limit`` items.  The Azure SDK iterator is
    materialised inside ``run_with_timeout`` and both outcomes are audited.

    Args:
        resource_group: Optional resource group name to narrow the scope.
                        ``None`` queries the entire subscription.
        limit: Maximum number of recommendations to return (default 50).

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str | None,
                "count": int,
                "truncated": bool,
                "recommendations": [
                    {"id", "category", "impact", "short_description", "resource_id"},
                    ...
                ]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "list_advisor_recommendations"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            PaginationInput(limit=limit)
            validated_rg = ResourceGroupInput(resource_group=resource_group) if resource_group else None
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        collection = clients.advisor.recommendations
        if validated_rg:
            list_call = lambda: list(collection.list(validated_rg.resource_group))
        else:
            list_call = lambda: list(collection.list())
        recommendations = run_with_timeout(
            callback=list_call,
            timeout_seconds=settings.request_timeout_seconds,
        )
        normalized = [
            {
                "id": getattr(item, "id", None),
                "category": getattr(item, "category", None),
                "impact": getattr(item, "impact", None),
                "short_description": getattr(item, "short_description", None),
                "resource_id": getattr(item, "resource_id", None),
            }
            for item in recommendations[:limit]
        ]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "limit": limit},
        )
        return {
            "ok": True,
            "resource_group": validated_rg.resource_group if validated_rg else None,
            "count": len(normalized),
            "truncated": len(normalized) == limit,
            "recommendations": normalized,
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "limit": limit},
            error_code=error_payload["error"]["code"],
        )
        return error_payload
