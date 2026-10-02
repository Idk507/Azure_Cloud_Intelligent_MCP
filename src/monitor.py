from __future__ import annotations

import contextvars
import json
import logging
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from .utils.redaction import redact_sensitive_data

try:  # Optional: logging and local metrics remain usable without the SDK.
    from opentelemetry import metrics, trace
except ImportError:  # pragma: no cover - exercised in minimal deployments
    metrics = None  # type: ignore[assignment]
    trace = None  # type: ignore[assignment]


_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="",
)
ToolLifecycleHook = Callable[[str, dict[str, Any]], None]
_tool_lifecycle_hooks: list[ToolLifecycleHook] = []
_tool_metrics: Counter[tuple[str, str, str]] = Counter()
_tool_duration_totals: Counter[tuple[str, str]] = Counter()
_tracing_configured = False
_metrics_exporter_configured = False
_tool_call_counter: Any | None = None
_tool_duration_histogram: Any | None = None


def configure_tracing(service_name: str = "azure-cloud-intelligence-mcp") -> bool:
    """Configure explicitly requested OTLP traces and bounded RED metrics.

    Trace and metric endpoints are intentionally separate. This follows the
    OpenTelemetry environment-variable convention and avoids guessing an
    ingestion URL from an Azure connection string.
    """
    global _tracing_configured, _metrics_exporter_configured
    global _tool_call_counter, _tool_duration_histogram
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    metrics_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "").strip()
    if endpoint and not _tracing_configured:
        if trace is None:
            logging.getLogger(__name__).warning("OTLP tracing requested but OpenTelemetry API is unavailable.")
        else:
            try:
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
                trace.set_tracer_provider(provider)  # type: ignore[union-attr]
                _tracing_configured = True
            except (ImportError, ValueError, AttributeError):
                logging.getLogger(__name__).warning("OTLP tracing requested but exporter dependencies are unavailable or invalid.")
    if metrics_endpoint and not _metrics_exporter_configured:
        if metrics is None:
            logging.getLogger(__name__).warning("OTLP metrics requested but OpenTelemetry API is unavailable.")
        else:
            try:
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
                from opentelemetry.sdk.metrics import MeterProvider
                from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
                from opentelemetry.sdk.resources import Resource
                reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=metrics_endpoint))
                metrics.set_meter_provider(MeterProvider(resource=Resource.create({"service.name": service_name}), metric_readers=[reader]))
                meter = metrics.get_meter("azure_cloud_intelligent_mcp")
                _tool_call_counter = meter.create_counter("azure_mcp.tool.calls", unit="1")
                _tool_duration_histogram = meter.create_histogram("azure_mcp.tool.duration", unit="ms")
                _metrics_exporter_configured = True
            except (ImportError, ValueError, AttributeError):
                logging.getLogger(__name__).warning("OTLP metrics requested but exporter dependencies are unavailable or invalid.")
    return _tracing_configured


def telemetry_snapshot() -> dict[str, Any]:
    """Return bounded, redacted in-process RED metrics for MCP operations.

    Labels are restricted to tool name, outcome, and safety class; request
    parameters, resource identifiers, and payloads can never become metric
    dimensions. An external OpenTelemetry exporter can subscribe through the
    lifecycle-hook API without changing the request path.
    """
    rows = []
    for (tool_name, status, safety_class), count in sorted(_tool_metrics.items()):
        total = _tool_duration_totals[(tool_name, status)]
        rows.append({"tool_name": tool_name, "status": status, "safety_class": safety_class,
                     "calls": count, "duration_ms_total": round(total, 2),
                     "duration_ms_average": round(total / count, 2) if count else 0})
    return {"ok": True, "metrics": rows, "metric_scope": "process_local", "exporter_configured": _tracing_configured, "metrics_exporter_configured": _metrics_exporter_configured}


def reset_telemetry() -> None:
    """Clear local metrics for isolated tests; not intended for MCP callers."""
    _tool_metrics.clear()
    _tool_duration_totals.clear()


def _emit_tool_span(tool_name: str, status: str, duration_ms: float, safety_class: str, error_code: str | None) -> None:
    """Emit a bounded OpenTelemetry span without request or resource data."""
    if trace is None:
        return
    tracer = trace.get_tracer("azure_cloud_intelligent_mcp")
    with tracer.start_as_current_span("azure_mcp.tool_call") as span:
        span.set_attribute("azure_mcp.tool_name", tool_name)
        span.set_attribute("azure_mcp.status", status)
        span.set_attribute("azure_mcp.safety_class", safety_class)
        span.set_attribute("azure_mcp.duration_ms", duration_ms)
        span.set_attribute("azure_mcp.correlation_id", get_correlation_id())
        if error_code is not None:
            span.set_attribute("azure_mcp.error_code", error_code)


def _emit_tool_metrics(tool_name: str, status: str, duration_ms: float, safety_class: str) -> None:
    """Export RED measurements with a fixed, audit-safe label set."""
    if _tool_call_counter is None or _tool_duration_histogram is None:
        return
    labels = {"tool_name": tool_name, "status": status, "safety_class": safety_class}
    _tool_call_counter.add(1, labels)
    _tool_duration_histogram.record(duration_ms, labels)


def register_tool_lifecycle_hook(hook: ToolLifecycleHook) -> None:
    """Register an in-process observer for audit-safe tool lifecycle events.

    Hooks are observers, not policy bypasses: their failures are isolated and
    never change the outcome of an Azure operation.
    """
    _tool_lifecycle_hooks.append(hook)


def emit_tool_lifecycle_event(event: str, payload: dict[str, Any]) -> None:
    """Notify registered hooks with redacted, correlated lifecycle metadata."""
    safe_payload = redact_sensitive_data({**payload, "correlation_id": get_correlation_id()})
    for hook in tuple(_tool_lifecycle_hooks):
        try:
            hook(event, safe_payload)
        except Exception:
            logging.getLogger(__name__).warning("Tool lifecycle hook failed.")


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

    metric_key = (tool_name, status, safety_class)
    _tool_metrics[metric_key] += 1
    _tool_duration_totals[(tool_name, status)] += duration_ms
    _emit_tool_span(tool_name, status, duration_ms, safety_class, error_code)
    _emit_tool_metrics(tool_name, status, duration_ms, safety_class)

    log_message = "Tool call completed." if status == "success" else "Tool call failed."
    log_fn = logger.info if status == "success" else logger.error
    log_fn(log_message, extra=payload)
    emit_tool_lifecycle_event(f"tool.{status}", payload)
