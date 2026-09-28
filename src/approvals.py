"""Short-lived, request-bound approval receipts for controlled operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Mapping

from .policies import ApprovalPlan, canonical_request_hash


@dataclass(frozen=True)
class ApprovalConsumptionResult:
    """The result of atomically checking and consuming an approval receipt."""

    allowed: bool
    reason: str
    plan: ApprovalPlan | None = None


class InMemoryApprovalStore:
    """Thread-safe approval store for a single MCP server process.

    This is deliberately process-local. A distributed deployment must replace
    it with durable storage offering an atomic compare-and-consume operation.
    """

    def __init__(self) -> None:
        self._plans: dict[str, ApprovalPlan] = {}
        self._consumed: set[str] = set()
        self._lock = Lock()

    def issue(self, plan: ApprovalPlan) -> None:
        """Store a newly reviewed plan, rejecting duplicate identifiers."""
        with self._lock:
            if plan.approval_id in self._plans:
                raise ValueError("approval_id already exists.")
            self._plans[plan.approval_id] = plan

    def consume(
        self,
        approval_id: str,
        tool_name: str,
        scope: str,
        target: Mapping[str, Any],
        payload: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> ApprovalConsumptionResult:
        """Atomically authorize exactly one request matching a stored plan."""
        checked_at = now or datetime.now(timezone.utc)
        with self._lock:
            plan = self._plans.get(approval_id)
            if plan is None:
                return ApprovalConsumptionResult(False, "approval_not_found")
            if approval_id in self._consumed:
                return ApprovalConsumptionResult(False, "approval_already_consumed")
            if checked_at > plan.expires_at:
                return ApprovalConsumptionResult(False, "approval_expired")
            request_hash = canonical_request_hash(tool_name, scope, target, payload)
            if request_hash != plan.request_hash:
                return ApprovalConsumptionResult(False, "approval_request_mismatch")
            self._consumed.add(approval_id)
            return ApprovalConsumptionResult(True, "approved", plan)


_approval_store = InMemoryApprovalStore()


def get_approval_store() -> InMemoryApprovalStore:
    """Return the process-local approval store used by MCP tool handlers."""
    return _approval_store


def reset_approval_store() -> None:
    """Replace the process-local store; intended for isolated tests only."""
    global _approval_store
    _approval_store = InMemoryApprovalStore()
