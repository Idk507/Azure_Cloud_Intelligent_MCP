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
from ..validation import PaginationInput, ResourceGroupInput, VirtualMachineTargetInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def _approval_required_payload(tool_name: str, reason: str) -> dict[str, Any]:
    """Build a standardised APPROVAL_REQUIRED error payload.

    Returns a structured dict that callers can return directly when a
    controlled-action tool is invoked without ``has_explicit_approval=True``.
    The payload follows the same ``{ok, error}`` envelope used by all other
    error responses so that clients can handle it uniformly.

    Args:
        tool_name: The MCP tool name that was blocked, included in ``details``
                   so the client knows which tool requires approval.
        reason:    Human-readable explanation from the policy engine (e.g.
                   ``"explicit_approval_required"``).

    Returns:
        ``{"ok": False, "error": {"code": "APPROVAL_REQUIRED", ...}}``
    """
    return {
        "ok": False,
        "error": {
            "code": "APPROVAL_REQUIRED",
            "message": "Explicit approval is required for this controlled action.",
            "details": {
                "tool": tool_name,
                "reason": reason,
            },
        },
    }


def _power_state_from_statuses(statuses: list[Any]) -> str | None:
    """Extract the human-readable power state from an instance-view status list.

    Azure VM instance views return a list of ``InstanceViewStatus`` objects.
    Each object has a ``code`` field in the form ``"<category>/<value>"``.
    This helper scans the list for the entry whose code starts with
    ``"PowerState/"`` and returns only the value portion (e.g. ``"running"``,
    ``"deallocated"``, ``"stopped"``).

    Args:
        statuses: List of ``InstanceViewStatus`` SDK objects (or any objects
                  with a ``code`` attribute).

    Returns:
        The power-state string (e.g. ``"running"``), or ``None`` if no
        ``PowerState/`` entry is present in the list.
    """
    for status in statuses:
        code = getattr(status, "code", "")
        if isinstance(code, str) and code.startswith("PowerState/"):
            # Strip the category prefix and return just the state value.
            return code.split("/", 1)[1]
    return None


def _resolve_limit(limit: int | None) -> int:
    """Resolve and clamp the caller-supplied page limit to a safe maximum.

    Validates ``limit`` through ``PaginationInput``.  Falls back to
    ``settings.max_results`` when the value is absent or invalid, and clamps
    any valid value so it never exceeds the configured ceiling.

    Args:
        limit: Requested maximum number of results, or ``None`` for the default.

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
        return settings.max_results
    return min(parsed.limit, settings.max_results)


def list_virtual_machines(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List virtual machines in a given resource group.

    Retrieves all VMs accessible within ``resource_group`` and returns a
    normalised subset of each VM's properties.  The result set is capped at
    ``limit`` (or ``settings.max_results``) to keep responses bounded.
    The Azure SDK iterator is materialised inside ``run_with_timeout`` to
    enforce the configured deadline.  Both outcomes are recorded via
    ``audit_tool_call``.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of VMs to return.  ``None`` uses the server default.

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str,
                "count": int,
                "truncated": bool,
                "virtual_machines": [{"id", "name", "location", "type", "tags"}, ...]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "list_virtual_machines"
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

        vms: list[dict[str, Any]] = []
        list_call = lambda: list(clients.compute.virtual_machines.list(validated_rg.resource_group))
        virtual_machines = run_with_timeout(
            callback=list_call,
            timeout_seconds=settings.request_timeout_seconds,
        )
        for vm in virtual_machines:
            vms.append(
                {
                    "id": getattr(vm, "id", None),
                    "name": getattr(vm, "name", None),
                    "location": getattr(vm, "location", None),
                    "type": getattr(vm, "type", None),
                    "tags": getattr(vm, "tags", None) or {},
                }
            )
            if len(vms) >= max_results:
                break

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": validated_rg.resource_group,
                "limit": limit,
            },
        )

        return {
            "ok": True,
            "resource_group": validated_rg.resource_group,
            "count": len(vms),
            "truncated": len(vms) >= max_results,
            "virtual_machines": vms,
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
                "resource_group": resource_group,
                "limit": limit,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def get_virtual_machine_status(resource_group: str, vm_name: str) -> dict[str, Any]:
    """Get instance and power status for a virtual machine.

    Calls the Azure Compute ``instance_view`` API for the specified VM and
    extracts the full status list plus the derived power state (e.g.
    ``"running"``, ``"deallocated"``) using ``_power_state_from_statuses``.
    The call is wrapped in ``run_with_timeout`` and both outcomes are audited.

    Args:
        resource_group: Name of the resource group that contains the VM.
        vm_name: Name of the virtual machine.

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str,
                "vm_name": str,
                "power_state": str | None,
                "statuses": [{"code", "display_status", "level", "message", "time"}, ...]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "get_virtual_machine_status"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = VirtualMachineTargetInput(resource_group=resource_group, vm_name=vm_name)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()

        status_call = lambda: clients.compute.virtual_machines.instance_view(
            validated.resource_group,
            validated.vm_name,
        )
        instance_view = run_with_timeout(
            callback=status_call,
            timeout_seconds=settings.request_timeout_seconds,
        )
        statuses = list(getattr(instance_view, "statuses", []) or [])
        power_state = _power_state_from_statuses(statuses)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": validated.resource_group,
                "vm_name": validated.vm_name,
            },
        )

        return {
            "ok": True,
            "resource_group": validated.resource_group,
            "vm_name": validated.vm_name,
            "power_state": power_state,
            "statuses": [
                {
                    "code": getattr(status, "code", None),
                    "display_status": getattr(status, "display_status", None),
                    "level": getattr(status, "level", None),
                    "message": getattr(status, "message", None),
                    "time": str(getattr(status, "time", "")) or None,
                }
                for status in statuses
            ],
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": resource_group,
                "vm_name": vm_name,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def start_virtual_machine(
    resource_group: str,
    vm_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Start a virtual machine (controlled action).

    Issues a ``begin_start`` long-running operation against the Azure Compute
    API.  The call is gated by ``execute_with_policy``: if
    ``has_explicit_approval`` is ``False`` the operation is blocked and an
    ``APPROVAL_REQUIRED`` payload is returned without touching Azure.
    When approved, the operation is submitted and its acceptance is confirmed.
    Both the approval-blocked and success/failure paths are audited.

    Args:
        resource_group: Name of the resource group that contains the VM.
        vm_name: Name of the virtual machine to start.
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "start_virtual_machine",
                "resource_group": str,
                "vm_name": str,
                "accepted": bool,
                "status": "accepted"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "start_virtual_machine"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = VirtualMachineTargetInput(resource_group=resource_group, vm_name=vm_name)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        settings = load_settings()

        def _callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            operation = run_with_timeout(
                callback=lambda: clients.compute.virtual_machines.begin_start(
                    validated.resource_group,
                    validated.vm_name,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            return {
                "accepted": operation is not None,
            }

        policy_result, operation_result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=has_explicit_approval,
            callback=_callback,
        )
        if not policy_result.allowed:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            audit_tool_call(
                logger,
                tool_name=tool_name,
                status="error",
                duration_ms=duration_ms,
                safety_class=metadata.safety_class.value,
                target_context={
                    "resource_group": validated.resource_group,
                    "vm_name": validated.vm_name,
                },
                error_code="APPROVAL_REQUIRED",
            )
            return _approval_required_payload(tool_name, policy_result.reason)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": validated.resource_group,
                "vm_name": validated.vm_name,
            },
        )

        return {
            "ok": True,
            "operation": "start_virtual_machine",
            "resource_group": validated.resource_group,
            "vm_name": validated.vm_name,
            "accepted": bool(operation_result and operation_result.get("accepted")),
            "status": "accepted",
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": resource_group,
                "vm_name": vm_name,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def stop_virtual_machine(
    resource_group: str,
    vm_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Stop (power off) a virtual machine (controlled action).

    Issues a ``begin_power_off`` long-running operation against the Azure
    Compute API.  Identical approval-gate, timeout, and audit behaviour to
    ``start_virtual_machine``.  The VM is left in a deallocated state after
    the operation completes, which stops billing for compute resources.

    Args:
        resource_group: Name of the resource group that contains the VM.
        vm_name: Name of the virtual machine to stop.
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "stop_virtual_machine",
                "resource_group": str,
                "vm_name": str,
                "accepted": bool,
                "status": "accepted"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "stop_virtual_machine"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = VirtualMachineTargetInput(resource_group=resource_group, vm_name=vm_name)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        settings = load_settings()

        def _callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            operation = run_with_timeout(
                callback=lambda: clients.compute.virtual_machines.begin_power_off(
                    validated.resource_group,
                    validated.vm_name,
                ),
                timeout_seconds=settings.request_timeout_seconds,
            )
            return {
                "accepted": operation is not None,
            }

        policy_result, operation_result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=has_explicit_approval,
            callback=_callback,
        )
        if not policy_result.allowed:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            audit_tool_call(
                logger,
                tool_name=tool_name,
                status="error",
                duration_ms=duration_ms,
                safety_class=metadata.safety_class.value,
                target_context={
                    "resource_group": validated.resource_group,
                    "vm_name": validated.vm_name,
                },
                error_code="APPROVAL_REQUIRED",
            )
            return _approval_required_payload(tool_name, policy_result.reason)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": validated.resource_group,
                "vm_name": validated.vm_name,
            },
        )

        return {
            "ok": True,
            "operation": "stop_virtual_machine",
            "resource_group": validated.resource_group,
            "vm_name": validated.vm_name,
            "accepted": bool(operation_result and operation_result.get("accepted")),
            "status": "accepted",
        }
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=duration_ms,
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": resource_group,
                "vm_name": vm_name,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload
