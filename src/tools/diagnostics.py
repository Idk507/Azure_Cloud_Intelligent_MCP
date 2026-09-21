from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..validation import VirtualMachineTargetInput, to_validation_error_payload
from . import compute, cost, monitoring

logger = logging.getLogger(__name__)


def _next_actions(power_state: str | None, evidence_complete: bool) -> list[str]:
    actions: list[str] = []
    if power_state not in {"running", "starting", "deallocating"}:
        actions.append("Confirm the intended VM power state before taking any action.")
    if not evidence_complete:
        actions.append("Collect bounded Monitor metrics and workspace logs for the VM resource.")
    if not actions:
        actions.append("Review the returned observations with the operator before changing resources.")
    return actions


def diagnose_virtual_machine(
    resource_group: str,
    vm_name: str,
    resource_id: str | None = None,
    workspace_id: str | None = None,
    metric_names: list[str] | None = None,
    timespan_hours: int = 1,
) -> dict[str, Any]:
    """Aggregate VM observations without fabricating a root cause."""
    started = time.perf_counter()
    tool_name = "diagnose_virtual_machine"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            target = VirtualMachineTargetInput(resource_group=resource_group, vm_name=vm_name)
            if timespan_hours < 1 or timespan_hours > 168:
                raise ValueError("timespan_hours must be between 1 and 168.")
            if workspace_id and not workspace_id.startswith("/subscriptions/"):
                raise ValueError("workspace_id must be an Azure resource ID.")
            if resource_id and not resource_id.startswith("/subscriptions/"):
                raise ValueError("resource_id must be an Azure resource ID.")
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}

        status_result = compute.get_virtual_machine_status(target.resource_group, target.vm_name)
        observations: list[dict[str, Any]] = [
            {
                "source": "compute.instance_view",
                "ok": bool(status_result.get("ok")),
                "value": status_result.get("power_state"),
                "detail": status_result.get("statuses", []),
            }
        ]
        evidence_sources = ["compute.instance_view"]
        incomplete_evidence: list[str] = []

        metrics_result: dict[str, Any] | None = None
        if resource_id and metric_names:
            metrics_result = monitoring.get_resource_metrics(
                resource_id=resource_id,
                metric_names=metric_names,
                timespan_hours=timespan_hours,
            )
            evidence_sources.append("monitor.metrics")
            observations.append(
                {
                    "source": "monitor.metrics",
                    "ok": bool(metrics_result.get("ok")),
                    "value": metrics_result.get("metrics", []),
                    "detail": {"count": metrics_result.get("count", 0)},
                }
            )
        else:
            incomplete_evidence.append("metrics_not_requested")

        advisor_result = cost.list_advisor_recommendations(resource_group=target.resource_group, limit=20)
        evidence_sources.append("advisor.recommendations")
        observations.append(
            {
                "source": "advisor.recommendations",
                "ok": bool(advisor_result.get("ok")),
                "value": advisor_result.get("recommendations", []),
                "detail": {"count": advisor_result.get("count", 0)},
            }
        )

        status_ok = bool(status_result.get("ok"))
        power_state = status_result.get("power_state") if status_ok else None
        if not status_ok:
            incomplete_evidence.append("vm_instance_view_failed")
        if advisor_result.get("ok") is False:
            incomplete_evidence.append("advisor_query_failed")
        if metrics_result is not None and metrics_result.get("ok") is False:
            incomplete_evidence.append("metrics_query_failed")

        evidence_complete = not incomplete_evidence
        result = {
            "ok": True,
            "resource_group": target.resource_group,
            "vm_name": target.vm_name,
            "observations": observations,
            "inferences": [],
            "evidence_sources": evidence_sources,
            "timespan_hours": timespan_hours,
            "incomplete_evidence": incomplete_evidence,
            "next_actions": _next_actions(power_state, evidence_complete),
        }
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={
                "resource_group": target.resource_group,
                "vm_name": target.vm_name,
                "timespan_hours": timespan_hours,
            },
        )
        return result
    except Exception as exc:  # pragma: no cover
        error_payload = as_tool_error(exc)
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": resource_group, "vm_name": vm_name},
            error_code=error_payload["error"]["code"],
        )
        return error_payload
