from __future__ import annotations

import logging
import time
from typing import Any

from ..auth import build_credential
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout

logger = logging.getLogger(__name__)


def _subscription_client() -> Any:
    """Create the one ARM client that does not require a selected subscription."""
    from azure.mgmt.resource.subscriptions import SubscriptionClient

    return SubscriptionClient(build_credential(load_settings()))


def list_accessible_subscriptions(limit: int = 100) -> dict[str, Any]:
    """List subscriptions available to the configured Azure identity.

    This onboarding tool is deliberately read-only and can run before
    ``AZURE_SUBSCRIPTION_ID`` is configured. It never chooses a subscription;
    callers must explicitly select one for subscription-scoped tools.
    """
    started = time.perf_counter()
    tool_name = "list_accessible_subscriptions"
    metadata = get_tool_metadata(tool_name)
    try:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer between 1 and 200.")
        values = run_with_timeout(
            lambda: list(_subscription_client().subscriptions.list()),
            load_settings().request_timeout_seconds,
        )
        subscriptions = [
            {
                "id": getattr(value, "subscription_id", None),
                "name": getattr(value, "display_name", None),
                "state": str(getattr(value, "state", "")) or None,
                "tenant_id": getattr(value, "tenant_id", None),
            }
            for value in values[:limit]
        ]
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"limit": limit},
        )
        return {"ok": True, "count": len(subscriptions), "truncated": len(values) > limit, "subscriptions": subscriptions}
    except ValueError as exc:
        return {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
    except Exception as exc:
        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="error",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"limit": limit},
        )
        return as_tool_error(exc)
