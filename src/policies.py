from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from .tool_registry import SafetyClass, ToolMetadata

T = TypeVar("T")


@dataclass(frozen=True)
class ActionPolicyResult:
    allowed: bool
    reason: str


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
