from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..config import load_settings
from ..monitor import audit_tool_call
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import PaginationInput, to_validation_error_payload

logger = logging.getLogger(__name__)


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
