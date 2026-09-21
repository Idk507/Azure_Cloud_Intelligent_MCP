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
from ..validation import AzureLocationInput, PaginationInput, ResourceGroupInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def _resolve_limit(limit: int | None) -> int:
    """Resolve and clamp the caller-supplied page limit to a safe maximum.

    Validates ``limit`` through ``PaginationInput`` and clamps the result to
    ``settings.max_results``.  Falls back to the configured ceiling when the
    value is absent or invalid.

    Args:
        limit: Requested maximum number of results, or ``None`` for the default.

    Returns:
        An integer in the range ``[1, settings.max_results]``.
    """
    settings = load_settings()
    try:
        parsed = PaginationInput(limit=limit)
    except ValidationError:
        return settings.max_results
    return min(parsed.limit or settings.max_results, settings.max_results)


def _approval_required_payload(tool_name: str, reason: str) -> dict[str, Any]:
    """Build a standardised APPROVAL_REQUIRED error payload.

    Returns a structured dict that callers can return directly when a
    controlled-action tool is invoked without ``has_explicit_approval=True``.

    Args:
        tool_name: The MCP tool name that was blocked.
        reason:    Human-readable explanation from the policy engine.

    Returns:
        ``{"ok": False, "error": {"code": "APPROVAL_REQUIRED", ...}}``
    """
    return {
        "ok": False,
        "error": {
            "code": "APPROVAL_REQUIRED",
            "message": "Explicit approval is required for this controlled action.",
            "details": {"tool": tool_name, "reason": reason},
        },
    }


def _list_network_resources(
    *,
    tool_name: str,
    resource_group: str,
    limit: int | None,
    collection_name: str,
    output_key: str,
) -> dict[str, Any]:
    """Generic helper that lists any Azure network resource collection.

    Avoids duplicating the validate → fetch → normalise → audit pattern for
    the three read-only network list tools (VNets, NSGs, public IPs).  The
    caller supplies the SDK collection attribute name and the output dict key;
    everything else (validation, timeout, pagination, audit) is handled here.

    Args:
        tool_name:       MCP tool name used for metadata lookup and audit logs.
        resource_group:  Azure resource group to query.
        limit:           Maximum number of items to return.
        collection_name: Attribute name on ``clients.network`` that exposes the
                         collection (e.g. ``"virtual_networks"``).
        output_key:      Key under which the normalised list is returned in the
                         success payload (e.g. ``"virtual_networks"``).

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str,
                "count": int,
                "truncated": bool,
                <output_key>: [{"id", "name", "location", "tags", "provisioning_state"}, ...]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = ResourceGroupInput(resource_group=resource_group)
            PaginationInput(limit=limit)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        max_results = _resolve_limit(limit)
        collection = getattr(clients.network, collection_name)
        items = run_with_timeout(
            callback=lambda: list(collection.list(validated_rg.resource_group)),
            timeout_seconds=settings.request_timeout_seconds,
        )
        normalized: list[dict[str, Any]] = []
        for item in items:
            normalized.append(
                {
                    "id": getattr(item, "id", None),
                    "name": getattr(item, "name", None),
                    "location": getattr(item, "location", None),
                    "tags": getattr(item, "tags", None) or {},
                    "provisioning_state": getattr(item, "provisioning_state", None),
                }
            )
            if len(normalized) >= max_results:
                break

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": validated_rg.resource_group, "limit": limit},
        )
        return {
            "ok": True,
            "resource_group": validated_rg.resource_group,
            "count": len(normalized),
            "truncated": len(normalized) >= max_results,
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


def list_virtual_networks(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List virtual networks in a resource group without exposing subnet secrets.

    Delegates to ``_list_network_resources`` with the ``virtual_networks``
    collection.  Only safe metadata fields (id, name, location, tags,
    provisioning_state) are returned; subnet address prefixes and peering
    details are excluded.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of VNets to return.  ``None`` uses the server default.

    Returns:
        See ``_list_network_resources`` return shape with key ``"virtual_networks"``.
    """
    return _list_network_resources(
        tool_name="list_virtual_networks",
        resource_group=resource_group,
        limit=limit,
        collection_name="virtual_networks",
        output_key="virtual_networks",
    )


def list_network_security_groups(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List network security groups and bounded rule metadata in a resource group.

    Delegates to ``_list_network_resources`` with the
    ``network_security_groups`` collection.  Only top-level NSG metadata is
    returned; individual security rules are not expanded in the response.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of NSGs to return.  ``None`` uses the server default.

    Returns:
        See ``_list_network_resources`` return shape with key
        ``"network_security_groups"``.
    """
    return _list_network_resources(
        tool_name="list_network_security_groups",
        resource_group=resource_group,
        limit=limit,
        collection_name="network_security_groups",
        output_key="network_security_groups",
    )


def list_public_ip_addresses(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List public IP address metadata in a resource group.

    Delegates to ``_list_network_resources`` with the ``public_ip_addresses``
    collection.  Only safe metadata fields are returned; no credentials or
    secrets are included in the response.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of public IPs to return.  ``None`` uses the server default.

    Returns:
        See ``_list_network_resources`` return shape with key
        ``"public_ip_addresses"``.
    """
    return _list_network_resources(
        tool_name="list_public_ip_addresses",
        resource_group=resource_group,
        limit=limit,
        collection_name="public_ip_addresses",
        output_key="public_ip_addresses",
    )


def create_public_ip_address(
    resource_group: str,
    public_ip_name: str,
    location: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Create a static Standard-SKU public IP address (controlled action).

    Validates the resource group, location, and IP name (1–80 characters),
    then gates execution through ``execute_with_policy``.  When approved,
    issues a ``begin_create_or_update`` long-running operation with
    ``allocation_method=Static`` and ``sku=Standard``.  Both the
    approval-blocked and success/failure paths are audited.

    Args:
        resource_group:      Name of the resource group to create the IP in.
        public_ip_name:      Name for the new public IP resource (1–80 chars).
        location:            Azure region (e.g. ``"eastus"``).
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "create_public_ip_address",
                "resource_group": str,
                "public_ip_name": str,
                "location": str,
                "accepted": bool,
                "status": "accepted"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "create_public_ip_address"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = ResourceGroupInput(resource_group=resource_group)
            validated_location = AzureLocationInput(location=location)
            if not public_ip_name.strip() or len(public_ip_name.strip()) > 80:
                raise ValueError("public_ip_name must be 1-80 characters.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        settings = load_settings()

        def callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            operation = run_with_timeout(
                callback=lambda: clients.network.public_ip_addresses.begin_create_or_update(
                    validated_rg.resource_group,
                    public_ip_name.strip(),
                    {
                        "location": validated_location.location,
                        "sku": {"name": "Standard"},
                        "public_ip_allocation_method": "Static",
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
        target = {
            "resource_group": validated_rg.resource_group,
            "public_ip_name": public_ip_name.strip(),
            "location": validated_location.location,
        }
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
            target_context={"resource_group": resource_group, "public_ip_name": public_ip_name},
            error_code=error_payload["error"]["code"],
        )
        return error_payload
