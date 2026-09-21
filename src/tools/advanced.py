from __future__ import annotations

import logging
import re
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import PaginationInput, ResourceGroupInput, to_validation_error_payload
from . import monitoring

logger = logging.getLogger(__name__)
FUNCTION_APP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$")


def _service_not_configured(service: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "SERVICE_NOT_CONFIGURED",
            "message": f"The {service} adapter is not configured.",
        },
    }


def _resolve_limit(limit: int | None) -> int:
    settings = load_settings()
    try:
        validated = PaginationInput(limit=limit)
    except ValidationError:
        return settings.max_results
    return min(validated.limit or settings.max_results, settings.max_results)


def _inventory(
    *,
    tool_name: str,
    resource_group: str | None,
    limit: int | None,
    client_attribute: str,
    collection_attribute: str,
    output_key: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = ResourceGroupInput(resource_group=resource_group) if resource_group else None
            PaginationInput(limit=limit)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        settings = load_settings()
        max_results = _resolve_limit(limit)
        collection = getattr(getattr(azure_cloud_clients, client_attribute), collection_attribute)
        if validated_rg and hasattr(collection, "list_by_resource_group"):
            list_call = lambda: list(collection.list_by_resource_group(validated_rg.resource_group))
        else:
            list_call = lambda: list(collection.list())
        items = run_with_timeout(callback=list_call, timeout_seconds=settings.request_timeout_seconds)
        normalized = [
            {
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "location": getattr(item, "location", None),
                "provisioning_state": getattr(item, "provisioning_state", None),
                "resource_group": resource_group,
                "tags": getattr(item, "tags", None) or {},
            }
            for item in items[:max_results]
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
            "resource_group": resource_group,
            "count": len(normalized),
            "truncated": len(normalized) == max_results,
            output_key: normalized,
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


def list_aks_clusters(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """List bounded AKS cluster metadata without pod or secret access."""
    return _inventory(
        tool_name="list_aks_clusters",
        resource_group=resource_group,
        limit=limit,
        client_attribute="aks",
        collection_attribute="managed_clusters",
        output_key="clusters",
    )


def list_function_apps(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """List bounded Azure Function App metadata without invoking application code."""
    return _inventory(
        tool_name="list_function_apps",
        resource_group=resource_group,
        limit=limit,
        client_attribute="appservice",
        collection_attribute="web_apps",
        output_key="function_apps",
    )


def query_function_app_logs(
    workspace_id: str,
    function_app_name: str,
    timespan_hours: int = 24,
    limit: int = 100,
) -> dict[str, Any]:
    """Query bounded Function App logs without accepting arbitrary KQL."""
    if not FUNCTION_APP_NAME_PATTERN.match(function_app_name.strip()):
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "function_app_name contains unsupported characters."}}
    query = (
        "AppServiceConsoleLogs "
        f"| where _ResourceId has '{function_app_name.strip()}' "
        "| project TimeGenerated, Level, ResultDescription "
        f"| order by TimeGenerated desc | take {min(max(limit, 1), 500)}"
    )
    result = monitoring.query_log_analytics(
        workspace_id=workspace_id,
        query=query,
        timespan_hours=timespan_hours,
        limit=limit,
    )
    if result.get("ok"):
        result["function_app_name"] = function_app_name.strip()
        result["data_classification"] = "sensitive_operational_logs"
    return result


def list_sql_databases(resource_group: str, server_name: str, limit: int | None = None) -> dict[str, Any]:
    """List bounded Azure SQL database metadata through the SQL adapter."""
    started = time.perf_counter()
    tool_name = "list_sql_databases"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = ResourceGroupInput(resource_group=resource_group)
            PaginationInput(limit=limit)
            if not server_name.strip():
                raise ValueError("server_name must be non-empty.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        if clients.sql is None:
            return _service_not_configured("Azure SQL")
        settings = load_settings()
        max_results = _resolve_limit(limit)
        databases = run_with_timeout(
            callback=lambda: list(clients.sql.databases.list_by_server(validated_rg.resource_group, server_name.strip())),
            timeout_seconds=settings.request_timeout_seconds,
        )
        normalized = [
            {
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "status": getattr(item, "status", None),
                "collation": getattr(item, "collation", None),
                "sku": getattr(getattr(item, "sku", None), "name", None),
            }
            for item in databases[:max_results]
        ]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": validated_rg.resource_group, "server_name": server_name, "limit": limit},
        )
        return {"ok": True, "resource_group": validated_rg.resource_group, "server_name": server_name.strip(), "count": len(normalized), "truncated": len(normalized) == max_results, "databases": normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_group": resource_group, "server_name": server_name}, error_code=error_payload["error"]["code"])
        return error_payload


def list_cosmos_accounts(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """List bounded Cosmos DB account metadata through the management adapter."""
    return _inventory(tool_name="list_cosmos_accounts", resource_group=resource_group, limit=limit, client_attribute="cosmos", collection_attribute="database_accounts", output_key="accounts")


def query_cosmos_items(
    account_name: str,
    database_name: str,
    container_name: str,
    query: str,
    limit: int = 100,
) -> dict[str, Any]:
    """Run a bounded read-only Cosmos query through an explicit data-plane adapter."""
    started = time.perf_counter()
    tool_name = "query_cosmos_items"
    metadata = get_tool_metadata(tool_name)
    try:
        normalized = query.strip()
        if not account_name.strip() or not database_name.strip() or not container_name.strip() or not normalized:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Cosmos target and query are required."}}
        if len(normalized) > 2000 or ";" in normalized or not normalized.lower().startswith("select"):
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Only one bounded SELECT query is allowed."}}
        if limit < 1 or limit > 500:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "limit must be between 1 and 500."}}
        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        if clients.cosmos is None:
            return _service_not_configured("Cosmos DB")
        settings = load_settings()
        items = run_with_timeout(
            callback=lambda: list(clients.cosmos.query_items(account_name.strip(), database_name.strip(), container_name.strip(), normalized, limit)),
            timeout_seconds=settings.request_timeout_seconds,
        )
        rows = items[:limit]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"account_name": account_name, "database_name": database_name, "container_name": container_name, "limit": limit})
        return {"ok": True, "account_name": account_name.strip(), "database_name": database_name.strip(), "container_name": container_name.strip(), "count": len(rows), "truncated": len(rows) == limit, "items": rows}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"account_name": account_name, "database_name": database_name, "container_name": container_name, "limit": limit}, error_code=error_payload["error"]["code"])
        return error_payload


def list_ml_workspaces(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """List bounded Azure ML workspace metadata through the ML adapter."""
    return _inventory(tool_name="list_ml_workspaces", resource_group=resource_group, limit=limit, client_attribute="ml", collection_attribute="workspaces", output_key="workspaces")


def list_ml_models(workspace_name: str, limit: int | None = None) -> dict[str, Any]:
    """List bounded Azure ML model metadata through the ML adapter."""
    return _ml_inventory("list_ml_models", "models", "models", workspace_name, limit)


def list_ml_jobs(workspace_name: str, limit: int | None = None) -> dict[str, Any]:
    """List bounded Azure ML job/pipeline metadata through the ML adapter."""
    return _ml_inventory("list_ml_jobs", "jobs", "jobs", workspace_name, limit)


def _ml_inventory(tool_name: str, collection_attribute: str, output_key: str, workspace_name: str, limit: int | None) -> dict[str, Any]:
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        if not workspace_name.strip():
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "workspace_name is required."}}
        clients = azure_clients.get_azure_clients()
        if clients.ml is None:
            return _service_not_configured("Azure ML")
        settings = load_settings()
        max_results = _resolve_limit(limit)
        collection = getattr(clients.ml, collection_attribute)
        items = run_with_timeout(callback=lambda: list(collection.list(workspace_name.strip())), timeout_seconds=settings.request_timeout_seconds)
        normalized = [{"id": getattr(item, "id", None), "name": getattr(item, "name", None), "status": getattr(item, "status", None), "type": getattr(item, "type", None)} for item in items[:max_results]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"workspace_name": workspace_name, "limit": limit})
        return {"ok": True, "workspace_name": workspace_name.strip(), "count": len(normalized), "truncated": len(normalized) == max_results, output_key: normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"workspace_name": workspace_name, "limit": limit}, error_code=error_payload["error"]["code"])
        return error_payload
