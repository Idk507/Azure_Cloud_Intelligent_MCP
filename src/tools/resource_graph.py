"""Bounded, inventory-only Azure Resource Graph tools."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout

logger = logging.getLogger(__name__)
_SUBSCRIPTION_ID = re.compile(r"^[0-9a-fA-F-]{36}$|^[A-Za-z0-9-]{1,64}$")
_FORBIDDEN_KQL = re.compile(r"\b(join|union|summarize|mv-expand|externaldata)\b|;", re.IGNORECASE)


def _validate_inventory_query(query: str, subscriptions: list[str], limit: int) -> tuple[str, list[str]]:
    normalized_query = query.strip()
    if not normalized_query or len(normalized_query) > 2_000:
        raise ValueError("query must be between 1 and 2000 characters.")
    if not re.match(r"^(Resources|ResourceContainers)\b", normalized_query, re.IGNORECASE):
        raise ValueError("query must start with Resources or ResourceContainers.")
    if _FORBIDDEN_KQL.search(normalized_query):
        raise ValueError("query contains an unsupported Azure Resource Graph operation.")
    if not subscriptions or len(subscriptions) > 20:
        raise ValueError("subscriptions must contain between 1 and 20 explicit subscription IDs.")
    cleaned_subscriptions = [subscription.strip() for subscription in subscriptions]
    if any(not _SUBSCRIPTION_ID.fullmatch(subscription) for subscription in cleaned_subscriptions):
        raise ValueError("subscriptions contains an invalid subscription ID.")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500.")
    return normalized_query, cleaned_subscriptions


def query_azure_resource_graph(query: str, subscriptions: list[str], limit: int = 100) -> dict[str, Any]:
    """Run a bounded Resource Graph inventory query across explicit subscriptions.

    Resource Graph is eventually consistent; callers must re-read an
    authoritative resource provider before relying on results for a mutation.
    """
    started = time.perf_counter()
    tool_name = "query_azure_resource_graph"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_query, validated_subscriptions = _validate_inventory_query(query, subscriptions, limit)
        except ValueError as exc:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
        settings = load_settings()
        max_results = min(limit, settings.max_results, 500)
        client = azure_clients.get_azure_clients().resource_graph
        results = run_with_timeout(
            lambda: client.query(validated_query, validated_subscriptions, max_results),
            settings.request_timeout_seconds,
        )
        resources = [dict(item) if hasattr(item, "items") else item for item in results[:max_results]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"subscriptions": validated_subscriptions, "limit": max_results})
        return {"ok": True, "subscriptions": validated_subscriptions, "count": len(resources), "truncated": len(results) > max_results, "eventual_consistency": True, "consistency_notice": "Resource Graph is eventually consistent; re-read the resource provider before mutation.", "resources": resources}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"subscriptions": subscriptions, "limit": limit}, error_code=error_payload["error"]["code"])
        return error_payload
