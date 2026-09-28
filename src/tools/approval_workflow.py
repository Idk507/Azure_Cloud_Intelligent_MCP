"""Small shared helpers for request-bound approval plans."""
from __future__ import annotations

from typing import Any, Mapping

from ..approvals import get_approval_store
from ..policies import build_approval_plan


def subscription_scope(subscription_id: str, resource_group: str) -> str:
    """Build the ARM scope that binds an approval to one resource group."""
    return f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"


def issue_plan(tool_name: str, scope: str, target: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    """Persist a short-lived plan and return only safe review metadata."""
    plan = build_approval_plan(tool_name, scope, target, payload)
    get_approval_store().issue(plan)
    return {
        "ok": True,
        "operation": "plan",
        "tool_name": tool_name,
        "approval": {
            "approval_id": plan.approval_id,
            "request_hash": plan.request_hash,
            "expires_at": plan.expires_at.isoformat(),
            "target": dict(target),
        },
    }


def consume_plan(approval_id: str | None, tool_name: str, scope: str, target: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Consume an exactly matching approval, returning an error payload if blocked."""
    if not approval_id:
        return {"ok": False, "error": {"code": "APPROVAL_REQUIRED", "message": "An approval_id from the matching plan tool is required.", "details": {"tool": tool_name}}}
    result = get_approval_store().consume(approval_id, tool_name, scope, target, payload)
    if result.allowed:
        return None
    return {"ok": False, "error": {"code": "APPROVAL_INVALID", "message": "The approval receipt cannot authorize this request.", "details": {"tool": tool_name, "reason": result.reason}}}
