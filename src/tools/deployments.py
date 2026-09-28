"""Read-only ARM deployment preflight and operation inspection tools."""
from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import DEPLOYMENT_NAME_PATTERN, ResourceGroupInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def _validate_deployment_target(resource_group: str, deployment_name: str) -> tuple[str, str]:
    validated_group = ResourceGroupInput(resource_group=resource_group).resource_group
    normalized_name = deployment_name.strip()
    if not DEPLOYMENT_NAME_PATTERN.fullmatch(normalized_name):
        raise ValueError("deployment_name contains unsupported characters.")
    return validated_group, normalized_name


def preview_arm_template_deployment(
    resource_group: str,
    deployment_name: str,
    template: dict[str, Any],
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview incremental ARM template changes without deploying resources."""
    started = time.perf_counter()
    tool_name = "preview_arm_template_deployment"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_group, validated_name = _validate_deployment_target(resource_group, deployment_name)
            if not isinstance(template.get("resources"), list):
                raise ValueError("template.resources must be an array.")
            if parameters is not None and not isinstance(parameters, dict):
                raise ValueError("parameters must be an object when provided.")
        except ValidationError as exc:
            return to_validation_error_payload(exc)
        except ValueError as exc:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        payload = {"properties": {"mode": "Incremental", "template": template, "parameters": parameters or {}}}
        settings = load_settings()
        client = azure_clients.get_azure_clients().resource
        poller = run_with_timeout(
            lambda: client.deployments.begin_what_if(validated_group, validated_name, payload),
            settings.request_timeout_seconds,
        )
        response = run_with_timeout(poller.result, settings.request_timeout_seconds)
        changes = [
            {"change_type": getattr(change, "change_type", None), "resource_id": getattr(change, "resource_id", None)}
            for change in (getattr(response, "changes", None) or [])
        ]
        target = {"resource_group": validated_group, "deployment_name": validated_name}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, **target, "preview_only": True, "changes": changes, "change_count": len(changes), "notice": "What-if is a prediction and does not execute a deployment."}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_group": resource_group, "deployment_name": deployment_name}, error_code=error_payload["error"]["code"])
        return error_payload


def get_arm_deployment_operation_status(resource_group: str, deployment_name: str, operation_id: str) -> dict[str, Any]:
    """Read one named ARM deployment operation's sanitized status."""
    started = time.perf_counter()
    tool_name = "get_arm_deployment_operation_status"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_group, validated_name = _validate_deployment_target(resource_group, deployment_name)
            validated_operation = operation_id.strip()
            if not validated_operation or len(validated_operation) > 256:
                raise ValueError("operation_id must be between 1 and 256 characters.")
        except ValidationError as exc:
            return to_validation_error_payload(exc)
        except ValueError as exc:
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        settings = load_settings()
        operation = run_with_timeout(
            lambda: azure_clients.get_azure_clients().resource.deployment_operations.get(validated_group, validated_name, validated_operation),
            settings.request_timeout_seconds,
        )
        target_resource = getattr(operation, "target_resource", None)
        normalized = {"operation_id": getattr(operation, "operation_id", validated_operation), "provisioning_state": getattr(operation, "provisioning_state", None), "status_code": getattr(operation, "status_code", None), "target_resource": {"id": getattr(target_resource, "id", None), "name": getattr(target_resource, "resource_name", None), "type": getattr(target_resource, "resource_type", None)} if target_resource else None}
        target = {"resource_group": validated_group, "deployment_name": validated_name, "operation_id": validated_operation}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, "operation": normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_group": resource_group, "deployment_name": deployment_name, "operation_id": operation_id}, error_code=error_payload["error"]["code"])
        return error_payload
