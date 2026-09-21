from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..policies import execute_with_policy
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import (
    FoundryAgentCreateInput,
    FoundryAgentTargetInput,
    FoundryProjectInput,
    OpenAIDeploymentCreateInput,
    OpenAIDeploymentInput,
    to_validation_error_payload,
)

logger = logging.getLogger(__name__)


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
    has_explicit_approval: bool = False,
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
            has_explicit_approval=has_explicit_approval,
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
    has_explicit_approval: bool = False,
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
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_cloud_clients = azure_clients.get_azure_clients()
        target = {"project_endpoint": validated.project_endpoint, "agent_name": validated.agent_name}
        if clients.ai_foundry is None:
            return _foundry_not_configured_payload()
        settings = load_settings()
        policy_result, operation_result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=has_explicit_approval,
            callback=lambda: run_with_timeout(
                callback=lambda: clients.ai_foundry.create_agent(
                    validated.project_endpoint,
                    validated.agent_name,
                    validated.instructions,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            ),
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
        return {"ok": True, "operation": tool_name, **target, "agent": operation_result}
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
    has_explicit_approval: bool = False,
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
        policy_result, operation_result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=has_explicit_approval,
            callback=lambda: run_with_timeout(
                callback=lambda: clients.ai_foundry.delete_agent(
                    validated.project_endpoint,
                    validated.agent_id,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            ),
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
        return {"ok": True, "operation": tool_name, **target, "deleted": bool(operation_result is not False), "status": "accepted"}
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
