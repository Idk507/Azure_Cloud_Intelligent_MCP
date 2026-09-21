from __future__ import annotations

import base64
import logging
import time
from typing import Any

from pydantic import ValidationError

from .. import azure_clients
from ..auth import build_credential
from ..config import load_settings
from ..monitor import audit_tool_call
from ..policies import execute_with_policy
from ..tool_registry import get_tool_metadata
from ..utils.errors import as_tool_error
from ..utils.runtime import run_with_timeout
from ..validation import (
    BlobTransferInput,
    PaginationInput,
    ResourceGroupInput,
    StorageAccountCreateInput,
    to_validation_error_payload,
)

logger = logging.getLogger(__name__)


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
            "details": {
                "tool": tool_name,
                "reason": reason,
            },
        },
    }


def _build_blob_service_client(account_name: str) -> Any:
    """Construct an authenticated ``BlobServiceClient`` for a storage account.

    Builds the account URL from ``account_name``, obtains a credential via
    ``build_credential``, and returns a ``BlobServiceClient`` ready for
    container and blob operations.  The credential type (service principal or
    ``DefaultAzureCredential``) is determined by the current ``Settings``.

    Args:
        account_name: Storage account name (without the ``.blob.core.windows.net``
                      suffix).

    Returns:
        An authenticated ``azure.storage.blob.BlobServiceClient`` instance.
    """
    from azure.storage.blob import BlobServiceClient

    settings = load_settings()
    credential = build_credential(settings)
    account_url = f"https://{account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


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
        # Invalid input — fall back to the configured ceiling.
        return settings.max_results
    if parsed.limit is None:
        return settings.max_results
    return min(parsed.limit, settings.max_results)


def list_storage_accounts(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    """List storage accounts in a given resource group.

    Retrieves all storage accounts in ``resource_group`` via the Azure Storage
    Management client and returns a normalised subset of each account's
    properties.  The result set is capped at ``limit`` (or
    ``settings.max_results``) and the call is wrapped in ``run_with_timeout``.
    Both outcomes are recorded via ``audit_tool_call``.

    Args:
        resource_group: Name of the Azure resource group to query.
        limit: Maximum number of accounts to return.  ``None`` uses the server default.

    Returns:
        On success::

            {
                "ok": True,
                "resource_group": str,
                "count": int,
                "truncated": bool,
                "storage_accounts": [{"id", "name", "location", "kind", "sku", "tags"}, ...]
            }

        On failure, a structured error payload from ``as_tool_error``.
    """
    started = time.perf_counter()
    tool_name = "list_storage_accounts"
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

        accounts: list[dict[str, Any]] = []
        list_call = lambda: list(clients.storage.storage_accounts.list_by_resource_group(validated_rg.resource_group))
        storage_accounts = run_with_timeout(
            callback=list_call,
            timeout_seconds=settings.request_timeout_seconds,
        )
        for account in storage_accounts:
            sku = getattr(account, "sku", None)
            accounts.append(
                {
                    "id": getattr(account, "id", None),
                    "name": getattr(account, "name", None),
                    "location": getattr(account, "location", None),
                    "kind": getattr(account, "kind", None),
                    "sku": getattr(sku, "name", None),
                    "tags": getattr(account, "tags", None) or {},
                }
            )
            if len(accounts) >= max_results:
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
            "count": len(accounts),
            "truncated": len(accounts) >= max_results,
            "storage_accounts": accounts,
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


def create_storage_account(
    resource_group: str,
    account_name: str,
    location: str | None = None,
    sku_name: str = "Standard_LRS",
    kind: str = "StorageV2",
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Create an Azure storage account (controlled action).

    Validates all inputs through ``StorageAccountCreateInput``, falls back to
    ``settings.default_location`` when ``location`` is omitted, then gates
    execution through ``execute_with_policy``.  When approved, issues a
    ``begin_create`` long-running operation.  Both the approval-blocked and
    success/failure paths are audited.

    Args:
        resource_group:      Name of the resource group to create the account in.
        account_name:        Globally unique storage account name (3–24 lowercase
                             alphanumeric characters).
        location:            Azure region.  Defaults to ``settings.default_location``
                             when ``None``.
        sku_name:            Storage SKU (default ``"Standard_LRS"``).
        kind:                Account kind (default ``"StorageV2"``).
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "create_storage_account",
                "resource_group": str,
                "account_name": str,
                "location": str,
                "accepted": bool,
                "status": "accepted"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "create_storage_account"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = StorageAccountCreateInput(
                resource_group=resource_group,
                account_name=account_name,
                location=location,
                sku_name=sku_name,
                kind=kind,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        settings = load_settings()
        effective_location = validated.location or settings.default_location

        def _callback() -> dict[str, Any]:
            clients = azure_clients.get_azure_clients()
            operation = run_with_timeout(
                callback=lambda: clients.storage.storage_accounts.begin_create(
                    validated.resource_group,
                    validated.account_name,
                    {
                        "location": effective_location,
                        "sku": {"name": validated.sku_name},
                        "kind": validated.kind,
                    },
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
                    "account_name": validated.account_name,
                    "location": effective_location,
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
                "account_name": validated.account_name,
                "location": effective_location,
            },
        )

        return {
            "ok": True,
            "operation": "create_storage_account",
            "resource_group": validated.resource_group,
            "account_name": validated.account_name,
            "location": effective_location,
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
                "account_name": account_name,
                "location": location,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def upload_blob_content(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    content_base64: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Upload blob bytes decoded from a base64 payload (controlled action).

    Decodes ``content_base64`` with strict validation before any Azure call is
    made, so malformed payloads are rejected early.  Execution is gated by
    ``execute_with_policy``; when approved the decoded bytes are uploaded via
    ``BlobServiceClient`` with ``overwrite=True``.  Both the approval-blocked
    and success/failure paths are audited.

    Args:
        resource_group:      Resource group of the target storage account.
        account_name:        Storage account name.
        container_name:      Blob container name.
        blob_name:           Destination blob path within the container.
        content_base64:      Base64-encoded bytes to upload.
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "upload_blob_content",
                "resource_group": str,
                "account_name": str,
                "container_name": str,
                "blob_name": str,
                "bytes_uploaded": int,
                "status": "completed"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "upload_blob_content"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = BlobTransferInput(
                resource_group=resource_group,
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
            )
            payload = base64.b64decode(content_base64, validate=True)
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                return to_validation_error_payload(exc)
            return {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "content_base64 must be valid base64 content.",
                },
            }

        settings = load_settings()

        def _callback() -> dict[str, Any]:
            blob_service = _build_blob_service_client(validated.account_name)
            container = blob_service.get_container_client(validated.container_name)
            run_with_timeout(
                callback=lambda: container.upload_blob(validated.blob_name, payload, overwrite=True),
                timeout_seconds=settings.request_timeout_seconds,
            )
            return {
                "bytes_uploaded": len(payload),
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
                    "account_name": validated.account_name,
                    "container_name": validated.container_name,
                    "blob_name": validated.blob_name,
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
                "account_name": validated.account_name,
                "container_name": validated.container_name,
                "blob_name": validated.blob_name,
            },
        )

        return {
            "ok": True,
            "operation": "upload_blob_content",
            "resource_group": validated.resource_group,
            "account_name": validated.account_name,
            "container_name": validated.container_name,
            "blob_name": validated.blob_name,
            "bytes_uploaded": int(operation_result["bytes_uploaded"]) if operation_result else 0,
            "status": "completed",
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
                "account_name": account_name,
                "container_name": container_name,
                "blob_name": blob_name,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload


def download_blob_content(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    """Download blob bytes and return them as a base64-encoded string (sensitive data).

    Because blob content may contain secrets or PII this tool is classified as
    ``SENSITIVE_DATA`` and requires ``has_explicit_approval=True``.  When
    approved, the blob is streamed via ``download_blob().readall()`` inside
    ``run_with_timeout``, then base64-encoded before being returned so that
    binary content is safely transported over JSON.  Both the approval-blocked
    and success/failure paths are audited.

    Args:
        resource_group:      Resource group of the source storage account.
        account_name:        Storage account name.
        container_name:      Blob container name.
        blob_name:           Source blob path within the container.
        has_explicit_approval: Must be ``True`` for the operation to proceed.

    Returns:
        On success::

            {
                "ok": True,
                "operation": "download_blob_content",
                "resource_group": str,
                "account_name": str,
                "container_name": str,
                "blob_name": str,
                "bytes_downloaded": int,
                "content_base64": str,
                "status": "completed"
            }

        ``APPROVAL_REQUIRED`` payload when approval is missing; structured
        error payload from ``as_tool_error`` on unexpected exceptions.
    """
    started = time.perf_counter()
    tool_name = "download_blob_content"
    metadata = get_tool_metadata(tool_name)

    try:
        try:
            validated = BlobTransferInput(
                resource_group=resource_group,
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
            )
        except ValidationError as exc:
            return to_validation_error_payload(exc)

        settings = load_settings()

        def _callback() -> dict[str, Any]:
            blob_service = _build_blob_service_client(validated.account_name)
            container = blob_service.get_container_client(validated.container_name)

            def _download() -> bytes:
                download_stream = container.download_blob(validated.blob_name)
                return download_stream.readall()

            content = run_with_timeout(
                callback=_download,
                timeout_seconds=settings.request_timeout_seconds,
            )
            return {
                "content_base64": base64.b64encode(content).decode("ascii"),
                "bytes_downloaded": len(content),
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
                    "account_name": validated.account_name,
                    "container_name": validated.container_name,
                    "blob_name": validated.blob_name,
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
                "account_name": validated.account_name,
                "container_name": validated.container_name,
                "blob_name": validated.blob_name,
            },
        )

        return {
            "ok": True,
            "operation": "download_blob_content",
            "resource_group": validated.resource_group,
            "account_name": validated.account_name,
            "container_name": validated.container_name,
            "blob_name": validated.blob_name,
            "bytes_downloaded": int(operation_result["bytes_downloaded"]) if operation_result else 0,
            "content_base64": operation_result["content_base64"] if operation_result else "",
            "status": "completed",
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
                "account_name": account_name,
                "container_name": container_name,
                "blob_name": blob_name,
            },
            error_code=error_payload["error"]["code"],
        )
        return error_payload
