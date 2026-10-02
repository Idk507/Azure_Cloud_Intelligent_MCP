from __future__ import annotations

import logging
import os
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..approvals import get_approval_store
from ..config import load_settings
from ..monitor import audit_tool_call, emit_tool_lifecycle_event, get_correlation_id
from ..policies import build_approval_plan, execute_with_policy
from .approval_workflow import consume_plan, issue_plan, subscription_scope
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.redaction import redact_sensitive_data
from ..utils.runtime import run_with_timeout
from ..validation import (
    FoundryAgentCreateInput,
    FoundryAgentTargetInput,
    FoundryAgentUpdateInput,
    FoundryProjectInput,
    OpenAIDeploymentCreateInput,
    OpenAIDeploymentInput,
    to_validation_error_payload,
)
from ..validation import ResourceGroupInput

logger = logging.getLogger(__name__)


def plan_openai_deployment(resource_group: str, account_name: str, deployment_name: str, model_name: str, model_version: str, sku_name: str = "GlobalStandard", capacity: int = 1) -> dict[str, Any]:
    """Issue a receipt bound to every material Azure OpenAI deployment field."""
    try:
        value = OpenAIDeploymentCreateInput(resource_group=resource_group, account_name=account_name, deployment_name=deployment_name, model_name=model_name, model_version=model_version, sku_name=sku_name, capacity=capacity)
    except ValidationError as exc:
        return to_validation_error_payload(exc)
    target = {"resource_group": value.resource_group, "account_name": value.account_name, "deployment_name": value.deployment_name, "model_name": value.model_name}
    payload = {"model_version": value.model_version, "sku_name": value.sku_name, "capacity": value.capacity}
    return issue_plan("deploy_openai_model", subscription_scope(load_settings().subscription_id, value.resource_group), target, payload)


def _approval_required_payload(tool_name: str, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "APPROVAL_REQUIRED",
            "message": "Explicit approval is required for this controlled action.",
            "details": {"tool": tool_name, "reason": reason},
        },
    }


def _foundry_not_configured_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "AI_FOUNDRY_NOT_CONFIGURED",
            "message": "No verified Microsoft Foundry project adapter is configured.",
        },
    }


def _foundry_inventory(project_endpoint: str, limit: int, tool_name: str, method_name: str, output_key: str, cursor: str | None = None) -> dict[str, Any]:
    """Run one bounded Foundry inventory read and return safe metadata only."""
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        validated = FoundryProjectInput(project_endpoint=project_endpoint)
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        if cursor is not None and (not cursor.strip() or len(cursor) > 4096):
            raise ValueError("cursor must be a non-empty opaque token up to 4096 characters.")
        clients = azure_clients.get_azure_clients()
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        page_method = getattr(clients.ai_foundry, f"{method_name}_page", None)
        if callable(page_method):
            page = run_with_timeout(lambda: page_method(validated.project_endpoint, cursor), load_settings().request_timeout_seconds)
            values = list(page.get("items", []))
            next_cursor = page.get("next_cursor")
        else:
            values = list(run_with_timeout(lambda: getattr(clients.ai_foundry, method_name)(validated.project_endpoint), load_settings().request_timeout_seconds))
            next_cursor = None
        normalized = [{"id": value.get("id") if isinstance(value, dict) else getattr(value, "id", None), "name": value.get("name") if isinstance(value, dict) else getattr(value, "name", None), "type": value.get("type") if isinstance(value, dict) else getattr(value, "type", None), "status": value.get("status") if isinstance(value, dict) else getattr(value, "status", None)} for value in values[:limit]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": validated.project_endpoint, "limit": limit})
        return {"ok": True, "project_endpoint": validated.project_endpoint, "count": len(normalized), "truncated": len(values) > limit, "next_cursor": next_cursor, output_key: normalized}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
    except Exception as exc:  # pragma: no cover
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint, "limit": limit}, error_code=error["error"]["code"])
        return error


def list_ai_foundry_models(project_endpoint: str, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    """List bounded Foundry model metadata for one validated project endpoint."""
    return _foundry_inventory(project_endpoint, limit, "list_ai_foundry_models", "list_models", "models", cursor)


def list_ai_foundry_connections(project_endpoint: str, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    """List bounded Foundry connection metadata without returning credentials."""
    return _foundry_inventory(project_endpoint, limit, "list_ai_foundry_connections", "list_connections", "connections", cursor)


def _foundry_evaluation_inventory(project_endpoint: str, identifier: str | None, limit: int, tool_name: str, method_name: str, output_key: str) -> dict[str, Any]:
    """Return bounded evaluation/run metadata, never configuration or sample content."""
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        if identifier is not None and not identifier.strip():
            raise ValueError("evaluation_id must be non-empty.")
        adapter = azure_clients.get_azure_clients().ai_foundry
        if adapter is None:
            return _foundry_not_configured_payload()
        arguments = (endpoint, limit) if identifier is None else (endpoint, identifier.strip(), limit)
        values = list(run_with_timeout(lambda: getattr(adapter, method_name)(*arguments), load_settings().request_timeout_seconds))
        safe = [
            {
                "id": item.get("id") if isinstance(item, dict) else getattr(item, "id", None),
                "name": item.get("name") if isinstance(item, dict) else getattr(item, "name", None),
                "status": item.get("status") if isinstance(item, dict) else getattr(item, "status", None),
                "created_at": item.get("created_at") if isinstance(item, dict) else str(getattr(item, "created_at", "")) or None,
                "updated_at": item.get("updated_at") if isinstance(item, dict) else str(getattr(item, "updated_at", "")) or None,
            }
            for item in values[:limit]
        ]
        target = {"project_endpoint": endpoint, "limit": limit}
        if identifier is not None:
            target["evaluation_id"] = identifier.strip()
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        response = {"ok": True, "project_endpoint": endpoint, "count": len(safe), "truncated": len(values) > limit, output_key: safe}
        if identifier is not None:
            response["evaluation_id"] = identifier.strip()
        return response
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
    except Exception as exc:  # pragma: no cover - SDK/network failures are normalized
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint, "limit": limit}, error_code=error["error"]["code"])
        return error


def list_ai_foundry_evaluations(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    """List bounded Foundry evaluation definitions without criteria or dataset details."""
    return _foundry_evaluation_inventory(project_endpoint, None, limit, "list_ai_foundry_evaluations", "list_evaluations", "evaluations")


def list_ai_foundry_evaluation_runs(project_endpoint: str, evaluation_id: str, limit: int = 50) -> dict[str, Any]:
    """List bounded evaluation-run metadata without scores, samples, or inputs."""
    return _foundry_evaluation_inventory(project_endpoint, evaluation_id, limit, "list_ai_foundry_evaluation_runs", "list_evaluation_runs", "evaluation_runs")


def _evaluation_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Validate a small, secret-free evaluation creation contract."""
    if not isinstance(definition, dict):
        raise ValueError("evaluation definition must be an object.")
    allowed = {"name", "data_source_config", "testing_criteria", "metadata"}
    if set(definition) - allowed:
        raise ValueError("evaluation definition contains unsupported fields.")
    name = definition.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 128:
        raise ValueError("evaluation name must be a non-empty string up to 128 characters.")
    if not isinstance(definition.get("data_source_config"), dict):
        raise ValueError("data_source_config must be an object.")
    if not isinstance(definition.get("testing_criteria"), list) or not definition["testing_criteria"]:
        raise ValueError("testing_criteria must be a non-empty list.")
    if "metadata" in definition and not isinstance(definition["metadata"], dict):
        raise ValueError("metadata must be an object when provided.")
    if redact_sensitive_data(definition) != definition:
        raise ValueError("evaluation definition must not contain credentials or secret-bearing fields.")
    return {**definition, "name": name.strip()}


def _evaluation_scope(project_endpoint: str) -> str:
    return f"foundry-project:{project_endpoint}"


def plan_ai_foundry_evaluation_creation(project_endpoint: str, definition: dict[str, Any]) -> dict[str, Any]:
    """Issue a single-use approval receipt bound to one evaluation definition."""
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        payload = _evaluation_definition(definition)
        return issue_plan("create_ai_foundry_evaluation", _evaluation_scope(endpoint), {"project_endpoint": endpoint, "name": payload["name"]}, payload)
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def create_ai_foundry_evaluation(project_endpoint: str, definition: dict[str, Any], approval_id: str | None = None) -> dict[str, Any]:
    """Create a Foundry evaluation only after a matching single-use approval."""
    started = time.perf_counter()
    tool_name = "create_ai_foundry_evaluation"
    metadata = get_tool_metadata(tool_name)
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        payload = _evaluation_definition(definition)
        target = {"project_endpoint": endpoint, "name": payload["name"]}
        blocked = consume_plan(approval_id, tool_name, _evaluation_scope(endpoint), target, payload)
        if blocked:
            return blocked
        adapter = azure_clients.get_azure_clients().ai_foundry
        if adapter is None:
            return _foundry_not_configured_payload()
        created = run_with_timeout(lambda: adapter.create_evaluation(endpoint, payload), load_settings().request_timeout_seconds)
        safe = {"id": created.get("id") if isinstance(created, dict) else getattr(created, "id", None), "name": created.get("name") if isinstance(created, dict) else getattr(created, "name", None), "status": created.get("status") if isinstance(created, dict) else getattr(created, "status", None), "created_at": created.get("created_at") if isinstance(created, dict) else str(getattr(created, "created_at", "")) or None}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, "project_endpoint": endpoint, "evaluation": safe}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
    except Exception as exc:  # pragma: no cover - SDK/network failures are normalized
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint}, error_code=error["error"]["code"])
        return error


def list_ai_foundry_thread_messages(project_endpoint: str, thread_id: str, limit: int = 50) -> dict[str, Any]:
    """List message metadata only; content is intentionally never returned."""
    if not thread_id.strip():
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "thread_id must be non-empty."}}
    started = time.perf_counter()
    tool_name = "list_ai_foundry_thread_messages"
    metadata = get_tool_metadata(tool_name)
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        if limit < 1 or limit > 500: raise ValueError("limit must be between 1 and 500.")
        adapter = azure_clients.get_azure_clients().ai_foundry
        if adapter is None: return _foundry_not_configured_payload()
        messages = list(run_with_timeout(lambda: adapter.list_agent_messages(endpoint, thread_id.strip()), load_settings().request_timeout_seconds))
        safe = [{"id": getattr(item, "id", None) if not isinstance(item, dict) else item.get("id"), "role": getattr(item, "role", None) if not isinstance(item, dict) else item.get("role"), "created_at": str(getattr(item, "created_at", "")) if not isinstance(item, dict) else item.get("created_at")} for item in messages[:limit]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000,2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": endpoint, "thread_id": thread_id, "limit": limit})
        return {"ok": True, "project_endpoint": endpoint, "thread_id": thread_id.strip(), "count": len(safe), "messages": safe, "content_included": False}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def list_ai_foundry_thread_runs(project_endpoint: str, thread_id: str, limit: int = 50) -> dict[str, Any]:
    """List bounded Foundry run metadata for a thread without input/output content."""
    if not thread_id.strip(): return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "thread_id must be non-empty."}}
    started = time.perf_counter(); tool_name = "list_ai_foundry_thread_runs"; metadata = get_tool_metadata(tool_name)
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        if limit < 1 or limit > 500: raise ValueError("limit must be between 1 and 500.")
        adapter = azure_clients.get_azure_clients().ai_foundry
        if adapter is None: return _foundry_not_configured_payload()
        runs = list(run_with_timeout(lambda: adapter.list_agent_runs(endpoint, thread_id.strip()), load_settings().request_timeout_seconds))
        safe = [{"id": value.get("id") if isinstance(value, dict) else getattr(value, "id", None), "agent_id": value.get("agent_id") if isinstance(value, dict) else getattr(value, "agent_id", None), "status": value.get("status") if isinstance(value, dict) else getattr(value, "status", None), "created_at": value.get("created_at") if isinstance(value, dict) else str(getattr(value, "created_at", "")) or None, "completed_at": value.get("completed_at") if isinstance(value, dict) else str(getattr(value, "completed_at", "")) or None} for value in runs[:limit]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000,2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": endpoint, "thread_id": thread_id, "limit": limit})
        return {"ok": True, "project_endpoint": endpoint, "thread_id": thread_id.strip(), "count": len(safe), "runs": safe}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def list_ai_foundry_agent_threads(project_endpoint: str, agent_id: str, limit: int = 50) -> dict[str, Any]:
    """List bounded thread IDs and timestamps for an agent, excluding metadata."""
    if not agent_id.strip(): return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "agent_id must be non-empty."}}
    started = time.perf_counter(); tool_name = "list_ai_foundry_agent_threads"; metadata = get_tool_metadata(tool_name)
    try:
        endpoint = FoundryProjectInput(project_endpoint=project_endpoint).project_endpoint
        if limit < 1 or limit > 500: raise ValueError("limit must be between 1 and 500.")
        adapter = azure_clients.get_azure_clients().ai_foundry
        if adapter is None: return _foundry_not_configured_payload()
        threads = list(run_with_timeout(lambda: adapter.list_agent_threads(endpoint, agent_id.strip()), load_settings().request_timeout_seconds))
        safe = [{"id": value.get("id") if isinstance(value, dict) else getattr(value, "id", None), "created_at": value.get("created_at") if isinstance(value, dict) else str(getattr(value, "created_at", "")) or None} for value in threads[:limit]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000,2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": endpoint, "agent_id": agent_id, "limit": limit})
        return {"ok": True, "project_endpoint": endpoint, "agent_id": agent_id.strip(), "count": len(safe), "threads": safe}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def get_ai_foundry_trace_status(project_endpoint: str) -> dict[str, Any]:
    """Report local Foundry tracing readiness without exposing secret values."""
    started = time.perf_counter()
    tool_name = "get_ai_foundry_trace_status"
    metadata = get_tool_metadata(tool_name)
    try:
        validated = FoundryProjectInput(project_endpoint=project_endpoint)
        # Presence is enough for readiness. Raw connection strings, endpoints,
        # and headers must not cross the MCP or audit boundary.
        app_insights = bool(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip())
        otel_endpoint = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())
        otel_headers = bool(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "").strip())
        status = {"ok": True, "project_endpoint": validated.project_endpoint,
                  "application_insights_configured": app_insights,
                  "otlp_endpoint_configured": otel_endpoint,
                  "otlp_headers_configured": otel_headers,
                  "tracing_ready": app_insights or otel_endpoint,
                  "note": "Configuration presence is reported without revealing telemetry connection values."}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": validated.project_endpoint})
        return status
    except ValidationError as exc:
        return to_validation_error_payload(exc)


def _connection_target(resource_group: str, account_name: str, project_name: str, connection_name: str) -> tuple[dict[str, str], dict[str, Any] | None]:
    try:
        group = ResourceGroupInput(resource_group=resource_group).resource_group
        values = {"account_name": account_name.strip(), "project_name": project_name.strip(), "connection_name": connection_name.strip()}
        if any(not value or len(value) > 64 for value in values.values()):
            raise ValueError("account_name, project_name, and connection_name must be non-empty and at most 64 characters.")
        return {"resource_group": group, **values}, None
    except (ValidationError, ValueError) as exc:
        return {}, to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def plan_ai_foundry_connection_deletion(resource_group: str, account_name: str, project_name: str, connection_name: str) -> dict[str, Any]:
    """Create a bound approval receipt before deleting a Foundry connection."""
    target, error = _connection_target(resource_group, account_name, project_name, connection_name)
    if error:
        return error
    return issue_plan("delete_ai_foundry_project_connection", subscription_scope(load_settings().subscription_id, target["resource_group"]), target, {})


def delete_ai_foundry_project_connection(resource_group: str, account_name: str, project_name: str, connection_name: str, approval_id: str | None = None) -> dict[str, Any]:
    """Delete one Foundry project connection through the documented ARM API."""
    target, error = _connection_target(resource_group, account_name, project_name, connection_name)
    if error:
        return error
    tool_name = "delete_ai_foundry_project_connection"
    approval_error = consume_plan(approval_id, tool_name, subscription_scope(load_settings().subscription_id, target["resource_group"]), target, {})
    if approval_error:
        return approval_error
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        run_with_timeout(lambda: azure_clients.get_azure_clients().cognitive.project_connections.delete(target["resource_group"], target["account_name"], target["project_name"], target["connection_name"]), load_settings().request_timeout_seconds)
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, "operation": tool_name, **target, "deleted": True}
    except Exception as exc:  # pragma: no cover
        failure = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context=target, error_code=failure["error"]["code"])
        return failure


def get_ai_foundry_project_connection(resource_group: str, account_name: str, project_name: str, connection_name: str) -> dict[str, Any]:
    """Read one Foundry project connection through ARM without credentials."""
    target, error = _connection_target(resource_group, account_name, project_name, connection_name)
    if error:
        return error
    started = time.perf_counter()
    tool_name = "get_ai_foundry_project_connection"
    metadata = get_tool_metadata(tool_name)
    try:
        value = run_with_timeout(lambda: azure_clients.get_azure_clients().cognitive.project_connections.get(target["resource_group"], target["account_name"], target["project_name"], target["connection_name"]), load_settings().request_timeout_seconds)
        safe = {"id": getattr(value, "id", None), "name": getattr(value, "name", None), "type": getattr(value, "type", None), "target": getattr(getattr(value, "properties", value), "target", None), "category": getattr(getattr(value, "properties", value), "category", None), "auth_type": getattr(getattr(value, "properties", value), "auth_type", None)}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, **target, "connection": safe}
    except Exception as exc:  # pragma: no cover
        failure = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context=target, error_code=failure["error"]["code"])
        return failure


def plan_ai_foundry_connection_upsert(resource_group: str, account_name: str, project_name: str, connection_name: str, connection: dict[str, Any]) -> dict[str, Any]:
    """Bind one Foundry connection create/update payload to a HITL receipt."""
    target, error = _connection_target(resource_group, account_name, project_name, connection_name)
    if error:
        return error
    if not isinstance(connection, dict) or not connection:
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "connection must be a non-empty object."}}
    return issue_plan("upsert_ai_foundry_project_connection", subscription_scope(load_settings().subscription_id, target["resource_group"]), target, {"connection": connection})


def upsert_ai_foundry_project_connection(resource_group: str, account_name: str, project_name: str, connection_name: str, connection: dict[str, Any], approval_id: str | None = None) -> dict[str, Any]:
    """Create or update a Foundry project connection through ARM after approval."""
    target, error = _connection_target(resource_group, account_name, project_name, connection_name)
    if error:
        return error
    if not isinstance(connection, dict) or not connection:
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "connection must be a non-empty object."}}
    tool_name = "upsert_ai_foundry_project_connection"
    approval_error = consume_plan(approval_id, tool_name, subscription_scope(load_settings().subscription_id, target["resource_group"]), target, {"connection": connection})
    if approval_error:
        return approval_error
    started = time.perf_counter(); metadata = get_tool_metadata(tool_name)
    try:
        value = run_with_timeout(lambda: azure_clients.get_azure_clients().cognitive.project_connections.create(target["resource_group"], target["account_name"], target["project_name"], target["connection_name"], connection), load_settings().request_timeout_seconds)
        safe = {"id": getattr(value, "id", None), "name": getattr(value, "name", None), "type": getattr(value, "type", None)}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000,2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, "operation": tool_name, **target, "connection": safe}
    except Exception as exc:  # pragma: no cover
        failure = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000,2), safety_class=metadata.safety_class.value, target_context=target, error_code=failure["error"]["code"])
        return failure


def _approval_record(tool_name: str, target: dict[str, Any]) -> dict[str, Any]:
    """Return a correlation-safe receipt proving the caller approved a mutation."""
    return {"approved": True, "tool": tool_name, "correlation_id": get_correlation_id(), "target": target}


def _approval_id_required_payload() -> dict[str, Any]:
    return {"ok": False, "error": {"code": "APPROVAL_ID_REQUIRED", "message": "Create an approval plan and provide its approval_id before executing this action."}}


def _approval_invalid_payload(tool_name: str, reason: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "APPROVAL_INVALID", "message": "Approval ID is invalid for this request.", "details": {"tool": tool_name, "reason": reason}}}


def plan_ai_foundry_agent_mutation(operation: str, project_endpoint: str, agent_id: str | None = None, agent_name: str | None = None, instructions: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Create and store a short-lived approval plan for a Foundry agent mutation."""
    try:
        if operation == "create":
            validated = FoundryAgentCreateInput(project_endpoint=project_endpoint, agent_name=agent_name, instructions=instructions, model=model)
            tool_name = "create_ai_foundry_agent"
            target, payload = {"project_endpoint": validated.project_endpoint, "agent_name": validated.agent_name, "model": validated.model}, {"instructions": validated.instructions}
        elif operation == "delete":
            validated = FoundryAgentTargetInput(project_endpoint=project_endpoint, agent_id=agent_id)
            tool_name = "delete_ai_foundry_agent"
            target, payload = {"project_endpoint": validated.project_endpoint, "agent_id": validated.agent_id}, {}
        elif operation == "update":
            validated = FoundryAgentUpdateInput(project_endpoint=project_endpoint, agent_id=agent_id, instructions=instructions, model=model)
            if validated.instructions is None and validated.model is None:
                raise ValueError("At least one mutable field is required.")
            tool_name = "update_ai_foundry_agent"
            target = {"project_endpoint": validated.project_endpoint, "agent_id": validated.agent_id}
            payload = {key: value for key, value in {"instructions": validated.instructions, "model": validated.model}.items() if value is not None}
        else:
            raise ValueError("operation must be create, update, or delete.")
        plan = build_approval_plan(tool_name, validated.project_endpoint, target, payload)
        get_approval_store().issue(plan)
        return {"ok": True, "operation": operation, "approval": {"approval_id": plan.approval_id, "request_hash": plan.request_hash, "expires_at": plan.expires_at.isoformat(), "target": target}}
    except ValidationError as exc:
        return to_validation_error_payload(exc)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def list_openai_deployments(
    resource_group: str,
    account_name: str,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List bounded Azure OpenAI deployment metadata."""
    started = time.perf_counter()
    tool_name = "list_openai_deployments"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = OpenAIDeploymentInput(
                resource_group=resource_group,
                account_name=account_name,
                deployment_name="inventory",
            )
            if limit < 1 or limit > 500:
                raise ValueError("limit must be between 1 and 500.")
            if cursor is not None and (not cursor.strip() or len(cursor) > 4096):
                raise ValueError("cursor must be a non-empty opaque token up to 4096 characters.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        pager = run_with_timeout(
            callback=lambda: clients.cognitive.deployments.list(validated.resource_group, validated.account_name),
            timeout_seconds=settings.request_timeout_seconds,
        )
        if hasattr(pager, "by_page"):
            pages = pager.by_page(continuation_token=cursor) if cursor else pager.by_page()
            try:
                deployments = list(next(pages))
            except StopIteration:
                deployments = []
            next_cursor = getattr(pager, "continuation_token", None)
        else:
            if cursor:
                raise ValueError("The configured SDK does not support continuation cursors for deployment inventory.")
            deployments = list(pager)
            next_cursor = None
        normalized = [
            {
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "model_name": getattr(getattr(item, "model", None), "name", None),
                "model_version": getattr(getattr(item, "model", None), "version", None),
                "sku_name": getattr(getattr(item, "sku", None), "name", None),
                "capacity": getattr(getattr(item, "sku", None), "capacity", None),
                "provisioning_state": getattr(item, "provisioning_state", None),
            }
            for item in deployments[:limit]
        ]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "account_name": account_name, "limit": limit},
        )
        return {
            "ok": True,
            "resource_group": resource_group,
            "account_name": account_name,
            "count": len(normalized),
            "truncated": len(normalized) == limit,
            "next_cursor": next_cursor,
            "deployments": normalized,
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "account_name": account_name, "limit": limit},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def deploy_openai_model(
    resource_group: str,
    account_name: str,
    deployment_name: str,
    model_name: str,
    model_version: str,
    sku_name: str = "GlobalStandard",
    capacity: int = 1,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Create or update an Azure OpenAI deployment as a controlled action."""
    started = time.perf_counter()
    tool_name = "deploy_openai_model"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = OpenAIDeploymentCreateInput(
                resource_group=resource_group,
                account_name=account_name,
                deployment_name=deployment_name,
                model_name=model_name,
                model_version=model_version,
                sku_name=sku_name,
                capacity=capacity,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        settings = load_settings()
        target = {
            "resource_group": validated.resource_group,
            "account_name": validated.account_name,
            "deployment_name": validated.deployment_name,
            "model_name": validated.model_name,
        }
        approval_error = consume_plan(approval_id, tool_name, subscription_scope(settings.subscription_id, validated.resource_group), target, {"model_version": validated.model_version, "sku_name": validated.sku_name, "capacity": validated.capacity})
        if approval_error:
            return approval_error

        def callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            operation = run_with_timeout(
                callback=lambda: clients.cognitive.deployments.begin_create_or_update(
                    validated.resource_group,
                    validated.account_name,
                    validated.deployment_name,
                    {
                        "model": {"name": validated.model_name, "version": validated.model_version, "format": "OpenAI"},
                        "sku": {"name": validated.sku_name, "capacity": validated.capacity},
                    },
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            return {"accepted": operation is not None}

        policy_result, operation_result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=True,
            callback=callback,
        )
        if not policy_result.allowed:
            audit_tool_call(
                logger,
                tool_name=tool_name,
                status="error",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                safety_class=metadata.safety_class.value,
                target_context=target,
                error_code="APPROVAL_REQUIRED",
            )
            return _approval_required_payload(tool_name, policy_result.reason)

        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context=target,
        )
        return {"ok": True, "operation": tool_name, **target, "accepted": bool(operation_result and operation_result["accepted"]), "status": "accepted"}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "account_name": account_name, "deployment_name": deployment_name},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def list_ai_foundry_agents(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    """List agents through an explicitly configured, verified Foundry adapter."""
    started = time.perf_counter()
    tool_name = "list_ai_foundry_agents"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = FoundryProjectInput(project_endpoint=project_endpoint)
            if limit < 1 or limit > 500:
                raise ValueError("limit must be between 1 and 500.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        clients = azure_clients.get_azure_clients()
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        settings = load_settings()
        agents = run_with_timeout(
            callback=lambda: list(clients.ai_foundry.list_agents(validated.project_endpoint)),
            timeout_seconds=settings.request_timeout_seconds,
        )
        normalized = [
            {
                "id": getattr(agent, "id", None) if not isinstance(agent, dict) else agent.get("id"),
                "name": getattr(agent, "name", None) if not isinstance(agent, dict) else agent.get("name"),
                "status": getattr(agent, "status", None) if not isinstance(agent, dict) else agent.get("status"),
            }
            for agent in agents[:limit]
        ]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"project_endpoint": validated.project_endpoint, "limit": limit},
        )
        return {"ok": True, "project_endpoint": validated.project_endpoint, "count": len(normalized), "truncated": len(normalized) == limit, "agents": normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"project_endpoint": project_endpoint, "limit": limit},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def create_ai_foundry_agent(
    project_endpoint: str,
    agent_name: str,
    instructions: str,
    model: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Create a Foundry agent through the configured adapter after approval."""
    started = time.perf_counter()
    tool_name = "create_ai_foundry_agent"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = FoundryAgentCreateInput(
                project_endpoint=project_endpoint,
                agent_name=agent_name,
                instructions=instructions,
                model=model,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        target = {"project_endpoint": validated.project_endpoint, "agent_name": validated.agent_name, "model": validated.model}
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        settings = load_settings()
        if not approval_id:
            return _approval_id_required_payload()
        approval = get_approval_store().consume(approval_id, tool_name, validated.project_endpoint, target, {"instructions": validated.instructions})
        if not approval.allowed:
            return _approval_invalid_payload(tool_name, approval.reason)
        operation_result = run_with_timeout(
            callback=lambda: clients.ai_foundry.create_agent(validated.project_endpoint, validated.agent_name, validated.instructions, validated.model),
            timeout_seconds=settings.request_timeout_seconds,
        )

        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context=target,
        )
        return {"ok": True, "operation": tool_name, **target, "agent": operation_result, "approval": _approval_record(tool_name, target)}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"project_endpoint": project_endpoint, "agent_name": agent_name},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def delete_ai_foundry_agent(
    project_endpoint: str,
    agent_id: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Delete a Foundry agent through the configured adapter after approval."""
    started = time.perf_counter()
    tool_name = "delete_ai_foundry_agent"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated = FoundryAgentTargetInput(project_endpoint=project_endpoint, agent_id=agent_id)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        target = {"project_endpoint": validated.project_endpoint, "agent_id": validated.agent_id}
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        settings = load_settings()
        if not approval_id:
            return _approval_id_required_payload()
        approval = get_approval_store().consume(approval_id, tool_name, validated.project_endpoint, target, {})
        if not approval.allowed:
            return _approval_invalid_payload(tool_name, approval.reason)
        operation_result = run_with_timeout(lambda: clients.ai_foundry.delete_agent(validated.project_endpoint, validated.agent_id), settings.request_timeout_seconds)

        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context=target,
        )
        return {"ok": True, "operation": tool_name, **target, "deleted": bool(operation_result is not False), "status": "accepted", "approval": _approval_record(tool_name, target)}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"project_endpoint": project_endpoint, "agent_id": agent_id},
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def get_ai_foundry_agent(project_endpoint: str, agent_id: str) -> dict[str, Any]:
    """Read one Foundry agent definition without exposing credentials or runs."""
    started = time.perf_counter()
    tool_name = "get_ai_foundry_agent"
    metadata = get_tool_metadata(tool_name)
    try:
        validated = FoundryAgentTargetInput(project_endpoint=project_endpoint, agent_id=agent_id)
        clients = azure_clients.get_azure_clients()
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        agent = run_with_timeout(lambda: clients.ai_foundry.get_agent(validated.project_endpoint, validated.agent_id), load_settings().request_timeout_seconds)
        target = {"project_endpoint": validated.project_endpoint, "agent_id": validated.agent_id}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, **target, "agent": agent}
    except ValidationError as exc:
        return to_validation_error_payload(exc)
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint, "agent_id": agent_id}, error_code=error_payload["error"]["code"])
        return error_payload


def update_ai_foundry_agent(project_endpoint: str, agent_id: str, instructions: str | None = None, model: str | None = None, approval_id: str | None = None) -> dict[str, Any]:
    """Update an existing Foundry agent after explicit human approval."""
    started = time.perf_counter()
    tool_name = "update_ai_foundry_agent"
    metadata = get_tool_metadata(tool_name)
    try:
        validated = FoundryAgentUpdateInput(project_endpoint=project_endpoint, agent_id=agent_id, instructions=instructions, model=model)
        if validated.instructions is None and validated.model is None:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "At least one mutable field is required."}}
        clients = azure_clients.get_azure_clients()
        target = {"project_endpoint": validated.project_endpoint, "agent_id": validated.agent_id}
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        if not approval_id:
            return _approval_id_required_payload()
        payload = {key: value for key, value in {"instructions": validated.instructions, "model": validated.model}.items() if value is not None}
        approval = get_approval_store().consume(approval_id, tool_name, validated.project_endpoint, target, payload)
        if not approval.allowed:
            return _approval_invalid_payload(tool_name, approval.reason)
        agent = run_with_timeout(lambda: clients.ai_foundry.update_agent(validated.project_endpoint, validated.agent_id, validated.instructions, validated.model), load_settings().request_timeout_seconds)
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, "operation": tool_name, **target, "agent": agent, "approval": _approval_record(tool_name, target)}
    except ValidationError as exc:
        return to_validation_error_payload(exc)
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint, "agent_id": agent_id}, error_code=error_payload["error"]["code"])
        return error_payload
