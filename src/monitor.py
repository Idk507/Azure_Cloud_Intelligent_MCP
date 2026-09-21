from __future__ import annotations

import contextvars
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .utils.redaction import redact_sensitive_data


_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="",
)


class JsonLogFormatter(logging.Formatter):
    """Structured JSON log formatter that enriches records with audit fields.

    Overrides ``format`` to produce a single-line JSON object per log record.
    In addition to the standard fields (timestamp, level, logger, message) it
    promotes any extra attributes set by ``audit_tool_call`` (tool_name,
    duration_ms, status, safety_class, target_context, error_code) into the
    top-level JSON payload so that log aggregators can index them directly.
    The current correlation ID is always included to allow request tracing.
    """
    def format(self, record: logging.LogRecord) -> str:
        """Serialise a log record to a compact JSON string.

        Args:
            record: Standard ``logging.LogRecord`` instance, potentially
                    carrying extra audit attributes.

        Returns:
            A single-line JSON string suitable for structured log ingestion.
        """
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        if hasattr(record, "tool_name"):
            payload["tool_name"] = record.tool_name
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if hasattr(record, "status"):
            payload["status"] = record.status
        if hasattr(record, "safety_class"):
            payload["safety_class"] = record.safety_class
        if hasattr(record, "target_context"):
            payload["target_context"] = record.target_context
        if hasattr(record, "error_code"):
            payload["error_code"] = record.error_code
        return json.dumps(payload, separators=(",", ":"))


def set_correlation_id(value: str | None = None) -> str:
    """Set the correlation ID for the current async context.

    Stores ``value`` (or a freshly generated UUID4 when ``None``) in the
    ``ContextVar`` so that all log records emitted within the same request
    context share the same ID.  Called at the start of every MCP tool handler
    via the ``*_tool`` wrappers in ``app.py``.

    Args:
        value: Explicit correlation ID string, or ``None`` to auto-generate.

    Returns:
        The correlation ID that was set.
    """
    resolved = value or str(uuid.uuid4())
    _correlation_id_var.set(resolved)
    return resolved


def get_correlation_id() -> str:
    """Return the correlation ID for the current async context.

    If no ID has been set yet (e.g. during startup logging before the first
    request), a new UUID4 is generated and stored so that subsequent calls
    within the same context return the same value.

    Returns:
        The current correlation ID string.
    """
    current = _correlation_id_var.get()
    if current:
        return current
    return set_correlation_id()


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with the JSON formatter if not already set up.

    Idempotent: if the root logger already has handlers (e.g. from a test
    harness or a previous call) only the log level is updated.  On first call
    a ``StreamHandler`` with ``JsonLogFormatter`` is attached so that all
    loggers in the process emit structured JSON to stdout.

    Args:
        level: Log level string (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())

    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def audit_tool_call(
    logger: logging.Logger,
    *,
    tool_name: str,
    status: str,
    duration_ms: float,
    safety_class: str,
    target_context: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    """Emit a structured audit log entry for a completed tool call.

    Builds a payload dict from the supplied fields, redacts any sensitive keys
    in ``target_context`` via ``redact_sensitive_data``, and logs at INFO on
    success or ERROR on failure.  The ``extra`` kwarg promotes all payload
    fields into the ``LogRecord`` so that ``JsonLogFormatter`` can include them
    in the top-level JSON object.

    Args:
        logger:         Module-level logger of the calling tool.
        tool_name:      MCP tool name being audited.
        status:         ``"success"`` or ``"error"``.
        duration_ms:    Wall-clock duration of the tool call in milliseconds.
        safety_class:   Safety classification string from ``ToolMetadata``.
        target_context: Optional dict of resource identifiers (resource group,
                        VM name, etc.) to include in the audit record.  Any
                        sensitive keys are automatically redacted.
        error_code:     Optional error code string included only on failure.
    """
    payload: dict[str, Any] = {
        "tool_name": tool_name,
        "status": status,
        "duration_ms": duration_ms,
        "safety_class": safety_class,
    }
    if target_context is not None:
        payload["target_context"] = redact_sensitive_data(target_context)
    if error_code is not None:
        payload["error_code"] = error_code

    log_message = "Tool call completed." if status == "success" else "Tool call failed."
    log_fn = logger.info if status == "success" else logger.error
    log_fn(log_message, extra=payload)
