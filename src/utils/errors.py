from __future__ import annotations

from typing import Any

try:
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ResourceNotFoundError,
        ServiceRequestError,
    )
except Exception:  # pragma: no cover
    ClientAuthenticationError = type("ClientAuthenticationError", (Exception,), {})
    HttpResponseError = type("HttpResponseError", (Exception,), {})
    ResourceNotFoundError = type("ResourceNotFoundError", (Exception,), {})
    ServiceRequestError = type("ServiceRequestError", (Exception,), {})


def sanitize_azure_error(exc: Exception) -> dict[str, Any]:
    """Map an Azure SDK exception to a safe, client-facing error dict.

    Inspects the exception type and, for ``HttpResponseError``, the HTTP status
    code, and returns a structured ``{code, message}`` dict.  Raw exception
    messages are intentionally suppressed to avoid leaking internal Azure
    resource paths or subscription details to callers.

    Handled exception types and their codes:

    - ``TimeoutError``              → ``TIMEOUT``
    - ``ResourceNotFoundError``     → ``RESOURCE_NOT_FOUND``
    - ``ClientAuthenticationError`` → ``AUTHENTICATION_FAILED``
    - ``ServiceRequestError``       → ``UPSTREAM_UNAVAILABLE``
    - ``HttpResponseError`` 403     → ``AUTHORIZATION_FAILED``
    - ``HttpResponseError`` 429     → ``THROTTLED``
    - ``HttpResponseError`` other   → ``AZURE_HTTP_ERROR`` (with status_code)
    - Any other exception           → ``UNEXPECTED_ERROR``

    Args:
        exc: The exception to classify.

    Returns:
        A dict with at least ``"code"`` and ``"message"`` keys.
    """
    if isinstance(exc, TimeoutError):
        return {
            "code": "TIMEOUT",
            "message": "Operation timed out before completion.",
        }

    if isinstance(exc, ResourceNotFoundError):
        return {
            "code": "RESOURCE_NOT_FOUND",
            "message": "The requested Azure resource was not found.",
        }

    if isinstance(exc, ClientAuthenticationError):
        return {
            "code": "AUTHENTICATION_FAILED",
            "message": "Authentication failed for the configured Azure identity.",
        }

    if isinstance(exc, ServiceRequestError):
        return {
            "code": "UPSTREAM_UNAVAILABLE",
            "message": "Azure service is temporarily unavailable. Please retry.",
        }

    if isinstance(exc, HttpResponseError):
        status_code = getattr(exc, "status_code", None)
        if status_code == 403:
            return {
                "code": "AUTHORIZATION_FAILED",
                "message": "The configured Azure identity does not have permission for this action.",
            }
        if status_code == 429:
            return {
                "code": "THROTTLED",
                "message": "Azure request was throttled. Retry after backoff.",
            }
        return {
            "code": "AZURE_HTTP_ERROR",
            "message": "Azure API request failed.",
            "status_code": status_code,
        }

    return {
        "code": "UNEXPECTED_ERROR",
        "message": "Unexpected server error while processing Azure request.",
    }


def as_tool_error(exc: Exception) -> dict[str, Any]:
    """Wrap a sanitised Azure error in the standard tool error envelope.

    Delegates to ``sanitize_azure_error`` and wraps the result in the
    ``{ok: False, error: {...}}`` envelope that all tool functions return on
    failure, ensuring a consistent response shape for MCP clients.

    Args:
        exc: The exception to wrap.

    Returns:
        ``{"ok": False, "error": {"code": ..., "message": ..., ...}}``
    """
    return {
        "ok": False,
        "error": sanitize_azure_error(exc),
    }
