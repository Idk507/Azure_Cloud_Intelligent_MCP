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


def _foundry_inventory(project_endpoint: str, limit: int, tool_name: str, method_name: str, output_key: str) -> dict[str, Any]:
    """Run one bounded Foundry inventory read and return safe metadata only."""
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        validated = FoundryProjectInput(project_endpoint=project_endpoint)
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        clients = azure_clients.get_azure_clients()
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        values = list(run_with_timeout(lambda: getattr(clients.ai_foundry, method_name)(validated.project_endpoint), load_settings().request_timeout_seconds))
        normalized = [{"id": value.get("id") if isinstance(value, dict) else getattr(value, "id", None), "name": value.get("name") if isinstance(value, dict) else getattr(value, "name", None), "type": value.get("type") if isinstance(value, dict) else getattr(value, "type", None), "status": value.get("status") if isinstance(value, dict) else getattr(value, "status", None)} for value in values[:limit]]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": validated.project_endpoint, "limit": limit})
        return {"ok": True, "project_endpoint": validated.project_endpoint, "count": len(normalized), "truncated": len(values) > limit, output_key: normalized}
    except (ValidationError, ValueError) as exc:
        return to_validation_error_payload(exc) if isinstance(exc, ValidationError) else {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
    except Exception as exc:  # pragma: no cover
        error = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter()-started)*1000, 2), safety_class=metadata.safety_class.value, target_context={"project_endpoint": project_endpoint, "limit": limit}, error_code=error["error"]["code"])
        return error


def list_ai_foundry_models(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    """List bounded Foundry model metadata for one validated project endpoint."""
    return _foundry_inventory(project_endpoint, limit, "list_ai_foundry_models", "list_models", "models")


def list_ai_foundry_connections(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    """List bounded Foundry connection metadata without returning credentials."""
    return _foundry_inventory(project_endpoint, limit, "list_ai_foundry_connections", "list_connections", "connections")


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
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        deployments = run_with_timeout(
            callback=lambda: list(
                clients.cognitive.deployments.list(
                    validated.resource_group,
                    validated.account_name,
                )
            ),
            timeout_seconds=settings.request_timeout_seconds,
        )
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
