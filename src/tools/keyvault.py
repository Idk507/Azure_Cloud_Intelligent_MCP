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
from ..validation import PaginationInput, ResourceGroupInput, to_validation_error_payload

logger = logging.getLogger(__name__)


def list_key_vaults(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List Key Vault metadata within a resource group (secret values are never returned).

    Retrieves all Key Vaults in ``resource_group`` via the Azure Key Vault
    Management client and returns a safe subset of each vault's properties.
    Secret values, access policies, and connection strings are intentionally
    excluded from the response.  The result set is capped at ``limit`` (or
    ``settings.max_results``) and the call is wrapped in ``run_with_timeout``.
    Both outcomes are recorded via ``audit_tool_call``.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of vaults to return.  ``None`` uses the server default.

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str,
                "count": int,
                "truncated": bool,
                "key_vaults": [
                    {"id", "name", "location", "vault_uri", "sku", "tenant_id", "tags"},
                    ...
                ]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "list_key_vaults"
    metadata = get_tool_metadata(tool_name)
    try:
        try:
            validated_rg = ResourceGroupInput(resource_group=resource_group)
            PaginationInput(limit=limit)
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        clients = azure_clients.get_azure_clients()
        settings = load_settings()
        max_results = min(limit or settings.max_results, settings.max_results)
        vaults = run_with_timeout(
            callback=lambda: list(clients.keyvault.vaults.list_by_resource_group(validated_rg.resource_group)),
            timeout_seconds=settings.request_timeout_seconds,
        )
        normalized: list[dict[str, Any]] = []
        for vault in vaults:
            normalized.append(
                {
                    "id": getattr(vault, "id", None),
                    "name": getattr(vault, "name", None),
                    "location": getattr(vault, "location", None),
                    "vault_uri": getattr(vault, "vault_uri", None),
                    "sku": getattr(getattr(vault, "sku", None), "name", None),
                    "tenant_id": getattr(vault, "tenant_id", None),
                    "tags": getattr(vault, "tags", None) or {},
                }
            )
            if len(normalized) >= max_results:
                break

        audit_tool_call(
            logger,
            tool_name=tool_name,
            status="success",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            safety_class=metadata.safety_class.value,
            target_context={"resource_group": validated_rg.resource_group, "limit": limit},
        )
        return {
            "ok": True,
            "resource_group": validated_rg.resource_group,
            "count": len(normalized),
            "truncated": len(normalized) >= max_results,
            "key_vaults": normalized,
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
