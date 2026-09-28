from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, TypeVar

from .tool_registry import SafetyClass, ToolMetadata

T = TypeVar("T")


@dataclass(frozen=True)
class ActionPolicyResult:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ApprovalPlan:
    """An immutable, short-lived receipt for a reviewed Azure mutation.

    The receipt does not authorize execution by itself. Task 2 will persist and
    consume it exactly once; binding the hash here prevents an approval from
    being reused for a changed tool, target, scope, or payload.
    """

    approval_id: str
    tool_name: str
    scope: str
    target: Mapping[str, Any]
    payload: Mapping[str, Any]
    request_hash: str
    created_at: datetime
    expires_at: datetime


def canonical_request_hash(
    tool_name: str,
    scope: str,
    target: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> str:
    """Return a stable SHA-256 hash for a mutation's reviewed intent."""
    canonical = json.dumps(
        {"payload": payload, "scope": scope, "target": target, "tool_name": tool_name},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_approval_plan(
    tool_name: str,
    scope: str,
    target: Mapping[str, Any],
    payload: Mapping[str, Any],
    ttl_seconds: int = 300,
) -> ApprovalPlan:
    """Create a review receipt for a controlled operation without executing it."""
    normalized_tool = tool_name.strip()
    normalized_scope = scope.strip()
    if not normalized_tool or not normalized_scope:
        raise ValueError("tool_name and scope must be non-empty.")
    if ttl_seconds < 1 or ttl_seconds > 3600:
        raise ValueError("ttl_seconds must be between 1 and 3600.")

    created_at = datetime.now(timezone.utc)
    copied_target = dict(target)
    copied_payload = dict(payload)
    return ApprovalPlan(
        approval_id=str(uuid.uuid4()),
        tool_name=normalized_tool,
        scope=normalized_scope,
        target=copied_target,
        payload=copied_payload,
        request_hash=canonical_request_hash(normalized_tool, normalized_scope, copied_target, copied_payload),
        created_at=created_at,
        expires_at=created_at + timedelta(seconds=ttl_seconds),
    )


def evaluate_tool_call_policy(
    tool_metadata: ToolMetadata,
    has_explicit_approval: bool,
) -> ActionPolicyResult:
    """Evaluate whether a tool call is permitted under the current policy.

    Read-only tools are always allowed regardless of ``has_explicit_approval``.
    Controlled-action and sensitive-data tools require the caller to pass
    ``has_explicit_approval=True``; without it the call is blocked and the
    reason ``"explicit_approval_required"`` is returned so that the caller can
    surface a meaningful error to the MCP client.

    Args:
        tool_metadata:        Metadata for the tool being evaluated, including
                              its ``safety_class``.
        has_explicit_approval: Whether the caller has confirmed the action.

    Returns:
        An ``ActionPolicyResult`` with ``allowed=True`` and a reason string on
        success, or ``allowed=False`` with ``reason="explicit_approval_required"``
        when the call is blocked.
    """
    if tool_metadata.safety_class == SafetyClass.READ_ONLY:
        return ActionPolicyResult(allowed=True, reason="read_only")

    if has_explicit_approval:
        return ActionPolicyResult(allowed=True, reason="approved")

    return ActionPolicyResult(
        allowed=False,
        reason="explicit_approval_required",
    )


def execute_with_policy(
    tool_metadata: ToolMetadata,
    has_explicit_approval: bool,
    callback: Callable[[], T],
) -> tuple[ActionPolicyResult, T | None]:
    """Evaluate policy and, if allowed, execute the callback.

    Combines ``evaluate_tool_call_policy`` with callback invocation so that
    callers do not need to check the policy result themselves.  When the policy
    blocks the call, ``callback`` is never invoked and ``None`` is returned as
    the second element of the tuple.

    Args:
        tool_metadata:        Metadata for the tool being evaluated.
        has_explicit_approval: Whether the caller has confirmed the action.
        callback:             Zero-argument callable that performs the actual
                              Azure operation and returns a result of type ``T``.

    Returns:
        A ``(ActionPolicyResult, result | None)`` tuple.  ``result`` is the
        return value of ``callback()`` when allowed, or ``None`` when blocked.
    """
    result = evaluate_tool_call_policy(
        tool_metadata=tool_metadata,
        has_explicit_approval=has_explicit_approval,
    )
    if not result.allowed:
        return result, None
    return result, callback()
