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
from ..validation import AzureResourceIdInput, PaginationInput, to_validation_error_payload

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


def _validate_generic_request(resource_id: str, api_version: str, payload: dict[str, Any] | None = None) -> tuple[str, str, dict[str, Any] | None]:
    validated_id = AzureResourceIdInput(resource_id=resource_id).resource_id
    version = api_version.strip()
    if not version or len(version) > 32 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in version):
        raise ValueError("api_version must be a provider API version such as 2023-09-01.")
    if payload is not None and len(str(payload).encode("utf-8")) > 256_000:
        raise ValueError("payload exceeds the 256 KB limit.")
    return validated_id, version, payload


def _generic_resource_parts(resource_id: str) -> tuple[str, str, str, str, str]:
    parts = resource_id.strip("/").split("/")
    try:
        rg_index = parts.index("resourceGroups")
        provider_index = parts.index("providers")
    except ValueError as exc:
        raise ValueError("resource_id must include resourceGroups and providers segments.") from exc
    if rg_index + 1 >= len(parts) or provider_index + 2 >= len(parts):
        raise ValueError("resource_id is missing resource group or provider segments.")
    resource_group = parts[rg_index + 1]
    provider_parts = parts[provider_index + 1 :]
    namespace = provider_parts[0]
    typed_parts = provider_parts[1:]
    if len(typed_parts) < 2 or len(typed_parts) % 2 != 0:
        raise ValueError("resource_id must contain resource type/name pairs.")
    resource_name = typed_parts[-1]
    resource_type = typed_parts[-2]
    parent_parts = typed_parts[:-2]
    parent_path = "/" + "/".join(parent_parts) if parent_parts else ""
    return resource_group, namespace, parent_path, resource_type, resource_name


def _resolve_limit(limit: int | None) -> int:
    """Resolve and clamp the caller-supplied page limit to a safe maximum.

    Validates the raw ``limit`` value through ``PaginationInput``.  If the
    value is absent or fails validation the configured ``max_results`` ceiling
    is returned unchanged.  When a valid limit is provided it is clamped so
    that it never exceeds ``max_results``, preventing runaway list operations
    against the Azure API.

    Args:
        limit: Requested maximum number of results, or ``None`` to use the
               server default.

    Returns:
        An integer in the range ``[1, settings.max_results]``.
    """
    settings = load_settings()
    try:
        parsed = PaginationInput(limit=limit)
    except ValidationError:
        # Invalid input — fall back to the configured ceiling.
        return settings.max_results
    if parsed.limit is None:
        # Caller omitted the limit — use the configured default.
        return settings.max_results
    # Clamp to the server-side maximum to avoid oversized responses.
    return min(parsed.limit, settings.max_results)


def list_resource_groups(limit: int | None = None) -> dict[str, Any]:
    """List Azure resource groups visible in the configured subscription.

    Retrieves every resource group accessible to the authenticated service
    principal and returns a normalised subset of each group's properties.
    The result set is capped at ``limit`` items (or ``settings.max_results``
    when ``limit`` is omitted) so that callers receive a predictable,
    bounded payload regardless of how many groups exist in the subscription.

    The call is wrapped in ``run_with_timeout`` to enforce the configured
    ``request_timeout_seconds`` deadline.  Both successful completions and
    exceptions are recorded via ``audit_tool_call`` for observability.

    Args:
        limit: Maximum number of resource groups to return.  ``None`` uses
               the server-configured default (``settings.max_results``).

    Returns:
        On success::

            {
                "ok": True,
                "count": <int>,
                "truncated": <bool>,   # True when more groups exist beyond limit
                "resource_groups": [
                    {"id": ..., "name": ..., "location": ..., "tags": {...}},
                    ...
                ]
            }

        On failure, a structured error payload produced by ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "list_resource_groups"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            PaginationInput(limit=limit)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()  # Authenticated Azure SDK clients.
        settings = load_settings()
        max_results = _resolve_limit(limit)  # Clamped upper bound for this request.

        groups: list[dict[str, Any]] = []

        # Materialise the lazy Azure SDK iterator inside the timeout wrapper so
        # that a slow or hung API call is cancelled after the configured deadline.
        list_call = lambda: list(clients.resource.resource_groups.list())
        resource_groups = run_with_timeout(
            callback=list_call,
            timeout_seconds=settings.request_timeout_seconds,
        )

        for resource_group in resource_groups:
            # Normalise each SDK object to a plain dict with only the fields
            # callers need; ``getattr`` guards against SDK version differences.
            groups.append(
                {
                    "id": getattr(resource_group, "id", None),
                    "name": getattr(resource_group, "name", None),
                    "location": getattr(resource_group, "location", None),
                    "tags": getattr(resource_group, "tags", None) or {},
                }
            )
            if len(groups) >= max_results:
                # Stop early once the requested page size is reached.
                break

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "scope": "subscription",
                "limit": limit,
            },
        )

        return {
            "ok": True,
            "count": len(groups),
            "truncated": len(groups) >= max_results,
            "resource_groups": groups,
        }
    except Exception as exc:  # pragma: no cover - exercised through error shape assertions
        error_payload = as_tool_error(exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "scope": "subscription",
                "limit": limit,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def list_azure_resources(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """List generic ARM resources across a subscription or resource group."""
    started = time.perf_counter()
    tool_name = "list_azure_resources"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = None
            if resource_group:
                from ..validation import ResourceGroupInput

                validated_rg = ResourceGroupInput(resource_group=resource_group)
            PaginationInput(limit=limit)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        max_results = _resolve_limit(limit)
        if validated_rg:
            list_call = lambda: list(clients.resource.resources.list_by_resource_group(validated_rg.resource_group))
        else:
            list_call = lambda: list(clients.resource.resources.list())
        resources = run_with_timeout(callback=list_call, timeout_seconds=settings.request_timeout_seconds)
        normalized = [
            {
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "type": getattr(item, "type", None),
                "location": getattr(item, "location", None),
                "resource_group": resource_group,
                "provisioning_state": getattr(item, "provisioning_state", None),
                "tags": getattr(item, "tags", None) or {},
            }
            for item in resources[:max_results]
        ]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_group": resource_group, "limit": limit})
        return {"ok": True, "resource_group": resource_group, "count": len(normalized), "truncated": len(normalized) == max_results, "resources": normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_group": resource_group, "limit": limit}, error_code=error_payload["error"]["code"])
        return error_payload


def list_azure_resource_providers() -> dict[str, Any]:
    """List Azure resource providers available to the current subscription."""
    started = time.perf_counter()
    tool_name = "list_azure_resource_providers"
    metadata = get_tool_metadata(tool_name)
    try:
        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        providers = run_with_timeout(callback=lambda: list(clients.resource.providers.list()), timeout_seconds=settings.request_timeout_seconds)
        normalized = [
            {
                "namespace": getattr(item, "namespace", None),
                "registration_state": getattr(item, "registration_state", None),
                "resource_types": [getattr(resource_type, "resource_type", None) for resource_type in (getattr(item, "resource_types", None) or [])],
            }
            for item in providers
        ]
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": "subscription"})
        return {"ok": True, "count": len(normalized), "providers": normalized}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"scope": "subscription"}, error_code=error_payload["error"]["code"])
        return error_payload


def get_azure_resource(resource_id: str, api_version: str) -> dict[str, Any]:
    """Read any ARM resource by ID using its provider API version."""
    started = time.perf_counter()
    tool_name = "get_azure_resource"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_id, version, _ = _validate_generic_request(resource_id, api_version)
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        item = run_with_timeout(callback=lambda: clients.resource.resources.get_by_id(validated_id, api_version=version), timeout_seconds=settings.request_timeout_seconds)
        result = dict(item) if hasattr(item, "items") else {"id": getattr(item, "id", validated_id), "name": getattr(item, "name", None), "type": getattr(item, "type", None), "location": getattr(item, "location", None), "properties": getattr(item, "properties", None)}
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_id": validated_id, "api_version": version})
        return {"ok": True, "resource": result}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_id": resource_id, "api_version": api_version}, error_code=error_payload["error"]["code"])
        return error_payload


def _mutate_azure_resource(tool_name: str, resource_id: str, api_version: str, payload: dict[str, Any] | None, has_explicit_approval: bool, operation: str) -> dict[str, Any]:
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_id, version, validated_payload = _validate_generic_request(resource_id, api_version, payload)
            if operation in {"create", "update"} and not validated_payload:
                raise ValueError("payload is required for create and update.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
        settings = load_settings()

        def callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            if operation == "delete":
                poller = clients.resource.resources.begin_delete_by_id(validated_id, api_version=version)
            elif operation == "update":
                poller = clients.resource.resources.begin_update_by_id(validated_id, validated_payload, api_version=version)
            else:
                resource_group, namespace, parent_path, resource_type, resource_name = _generic_resource_parts(validated_id)
                poller = clients.resource.resources.begin_create_or_update(resource_group, namespace, parent_path, resource_type, resource_name, validated_payload, api_version=version)
            result = run_with_timeout(callback=lambda: poller.result(), timeout_seconds=settings.request_timeout_seconds)
            return {"completed": True, "result": result}

        policy_result, operation_result = execute_with_policy(tool_metadata=metadata, has_explicit_approval=has_explicit_approval, callback=callback)
        target = {"resource_id": validated_id, "api_version": version, "operation": operation}
        if not policy_result.allowed:
            audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target, error_code="APPROVAL_REQUIRED")
            return _approval_required_payload(tool_name, policy_result.reason)
        audit_tool_call(logger, tool_name=tool_name, status="success", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context=target)
        return {"ok": True, **target, "status": "completed", "completed": bool(operation_result and operation_result["completed"])}
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(logger, tool_name=tool_name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), safety_class=metadata.safety_class.value, target_context={"resource_id": resource_id, "api_version": api_version, "operation": operation}, error_code=error_payload["error"]["code"])
        return error_payload


def create_azure_resource(resource_id: str, api_version: str, payload: dict[str, Any], has_explicit_approval: bool = False) -> dict[str, Any]:
    return _mutate_azure_resource("create_azure_resource", resource_id, api_version, payload, has_explicit_approval, "create")


def update_azure_resource(resource_id: str, api_version: str, payload: dict[str, Any], has_explicit_approval: bool = False) -> dict[str, Any]:
    return _mutate_azure_resource("update_azure_resource", resource_id, api_version, payload, has_explicit_approval, "update")


def delete_azure_resource(resource_id: str, api_version: str, has_explicit_approval: bool = False) -> dict[str, Any]:
    return _mutate_azure_resource("delete_azure_resource", resource_id, api_version, None, has_explicit_approval, "delete")
