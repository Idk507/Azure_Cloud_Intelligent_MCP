"""Bounded, read-only Azure RBAC and Policy discovery."""
from __future__ import annotations

import time
import re
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import AzureScopeInput, PaginationInput, to_validation_error_payload

import logging
logger = logging.getLogger(__name__)


def _scope(scope: str) -> str:
    validated = AzureScopeInput(scope=scope).scope.rstrip("/")
    required = f"/subscriptions/{load_settings().subscription_id}".lower()
    if not validated.lower().startswith(required):
        raise ValueError("scope must be within the configured subscription.")
    return validated


def _validation_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValidationError):
        return to_validation_error_payload(exc)
    return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}


def _limit(limit: int | None) -> int:
    value = PaginationInput(limit=limit).limit
    return min(value or load_settings().max_results, load_settings().max_results)


def _run(tool_name: str, scope: str, limit: int | None, callback: Any, key: str, normalize: Any) -> dict[str, Any]:
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        validated_scope, max_results = _scope(scope), _limit(limit)
        values = run_with_timeout(callback=lambda: list(callback(validated_scope)), timeout_seconds=load_settings().request_timeout_seconds)
        result = [normalize(value) for value in values[:max_results]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": validated_scope, "limit": limit})
        return {"ok": True, "scope": validated_scope, "count": len(result), "truncated": len(values) > max_results, key: result}
    except (ValidationError, ValueError) as exc:
        return _validation_error(exc)
    except Exception as exc:  # pragma: no cover
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": scope, "limit": limit}, error_code=error["error"]["code"])
        return error


def list_role_assignments(scope: str, limit: int | None = None) -> dict[str, Any]:
    """List role-assignment metadata at a validated scope, never credentials."""
    return _run("list_role_assignments", scope, limit,
        lambda value: azure_clients.get_azure_clients().authorization.role_assignments.list_for_scope(value, filter="atScope()"),
        "role_assignments", lambda item: {"id": getattr(item, "id", None), "name": getattr(item, "name", None), "principal_id": getattr(item, "principal_id", None), "role_definition_id": getattr(item, "role_definition_id", None), "scope": getattr(item, "scope", None), "principal_type": getattr(item, "principal_type", None)})


def list_policy_definitions(scope: str, limit: int | None = None) -> dict[str, Any]:
    """List policy definition metadata at the configured subscription scope."""
    return _run("list_policy_definitions", scope, limit,
        lambda value: azure_clients.get_azure_clients().policy.policy_definitions.list_by_subscription(),
        "policy_definitions", lambda item: {"id": getattr(item, "id", None), "name": getattr(item, "name", None), "display_name": getattr(getattr(item, "display_name", None), "value", getattr(item, "display_name", None)), "policy_type": getattr(item, "policy_type", None), "mode": getattr(item, "mode", None), "description": getattr(item, "description", None)})


def list_policy_assignments(scope: str, limit: int | None = None) -> dict[str, Any]:
    """List policy assignment metadata effective at a validated scope."""
    return _run("list_policy_assignments", scope, limit,
        lambda value: azure_clients.get_azure_clients().policy.policy_assignments.list_for_scope(value),
        "policy_assignments", lambda item: {"id": getattr(item, "id", None), "name": getattr(item, "name", None), "display_name": getattr(item, "display_name", None), "policy_definition_id": getattr(item, "policy_definition_id", None), "scope": getattr(item, "scope", None), "enforcement_mode": getattr(item, "enforcement_mode", None)})


def list_policy_compliance_states(scope: str, limit: int | None = None) -> dict[str, Any]:
    """Read latest bounded Azure Policy compliance states for a safe ARM scope."""
    started = time.perf_counter()
    tool_name = "list_policy_compliance_states"
    metadata = get_tool_metadata(tool_name)
    try:
        validated_scope, max_results = _scope(scope), _limit(limit)
        subscription_id = load_settings().subscription_id
        match = re.fullmatch(r"/subscriptions/[^/]+/resourceGroups/([^/]+)", validated_scope, flags=re.IGNORECASE)
        states = azure_clients.get_azure_clients().policy_insights.policy_states
        if match:
            response = run_with_timeout(callback=lambda: states.list_query_results_for_resource_group(subscription_id, match.group(1), "latest", top=max_results), timeout_seconds=load_settings().request_timeout_seconds)
        elif re.fullmatch(r"/subscriptions/[^/]+", validated_scope, flags=re.IGNORECASE):
            response = run_with_timeout(callback=lambda: states.list_query_results_for_subscription(subscription_id, "latest", top=max_results), timeout_seconds=load_settings().request_timeout_seconds)
        else:
            raise ValueError("scope must be a subscription or resource group scope for compliance queries.")
        values = getattr(response, "value", response.get("value", []) if isinstance(response, dict) else []) or []
        normalized = [{"resource_id": getattr(item, "resource_id", None), "resource_group": getattr(item, "resource_group", None), "resource_type": getattr(item, "resource_type", None), "compliance_state": getattr(item, "compliance_state", None), "policy_assignment_id": getattr(item, "policy_assignment_id", None), "policy_definition_id": getattr(item, "policy_definition_id", None), "timestamp": str(getattr(item, "timestamp", "")) or None} for item in list(values)[:max_results]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": validated_scope, "limit": limit})
        return {"ok": True, "scope": validated_scope, "count": len(normalized), "truncated": len(values) > max_results, "compliance_states": normalized, "consistency_notice": "Policy compliance results can be eventually consistent."}
    except (ValidationError, ValueError) as exc:
        return _validation_error(exc)
    except Exception as exc:  # pragma: no cover
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": scope, "limit": limit}, error_code=error["error"]["code"])
        return error
