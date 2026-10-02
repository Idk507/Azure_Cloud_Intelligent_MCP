from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import patch

import src.monitor as monitor
from src.monitor import JsonLogFormatter, audit_tool_call, emit_tool_lifecycle_event, register_tool_lifecycle_hook, reset_telemetry, set_correlation_id, telemetry_snapshot


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.formatted: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.formatted.append(self.format(record))


class MonitorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reset_telemetry()

    def test_telemetry_is_bounded_and_excludes_target_context(self) -> None:
        audit_tool_call(logging.getLogger("test.monitor.metrics"), tool_name="example", status="success", duration_ms=10, safety_class="read_only", target_context={"resource_id": "/secret"})
        snapshot = telemetry_snapshot()
        self.assertEqual(snapshot["metrics"][0]["calls"], 1)
        self.assertNotIn("target_context", snapshot["metrics"][0])
        self.assertNotIn("resource_id", snapshot["metrics"][0])

    def test_trace_span_uses_only_bounded_safe_attributes(self) -> None:
        attributes = {}
        class Span:
            def set_attribute(self, key, value): attributes[key] = value
        class Context:
            def __enter__(self): return Span()
            def __exit__(self, *args): return None
        class Tracer:
            def start_as_current_span(self, name): return Context()
        class Trace:
            def get_tracer(self, name): return Tracer()
        with patch.object(monitor, "trace", Trace()):
            audit_tool_call(logging.getLogger("test.monitor.trace"), tool_name="example", status="success", duration_ms=5, safety_class="read_only", target_context={"resource_id": "/secret"})
        self.assertEqual(attributes["azure_mcp.tool_name"], "example")
        self.assertNotIn("resource_id", attributes)

    def test_otlp_metrics_use_only_bounded_labels(self) -> None:
        measurements = []

        class Counter:
            def add(self, value, labels): measurements.append(("count", value, labels))

        class Histogram:
            def record(self, value, labels): measurements.append(("duration", value, labels))

        with patch.object(monitor, "_tool_call_counter", Counter()), patch.object(monitor, "_tool_duration_histogram", Histogram()):
            audit_tool_call(logging.getLogger("test.monitor.metrics_export"), tool_name="example", status="success", duration_ms=5, safety_class="read_only", target_context={"resource_id": "/secret"})

        self.assertEqual(len(measurements), 2)
        self.assertEqual(measurements[0][2], {"tool_name": "example", "status": "success", "safety_class": "read_only"})

    def test_tracing_is_disabled_without_an_otlp_endpoint(self) -> None:
        with patch.object(monitor, "_tracing_configured", False), patch.dict(
            "os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": ""}, clear=False
        ):
            self.assertFalse(monitor.configure_tracing())

    def test_lifecycle_hook_receives_redacted_correlated_payload(self) -> None:
        received = []
        register_tool_lifecycle_hook(lambda event, payload: received.append((event, payload)))
        set_correlation_id("hook-test")
        emit_tool_lifecycle_event("tool.success", {"token": "secret", "tool_name": "example"})
        event, payload = received[-1]
        self.assertEqual(event, "tool.success")
        self.assertEqual(payload["correlation_id"], "hook-test")
        self.assertNotEqual(payload["token"], "secret")
    def test_audit_log_redacts_sensitive_fields(self) -> None:
        set_correlation_id("test-correlation-id")

        logger = logging.getLogger("test.monitor.redaction")
        logger.handlers = []
        logger.setLevel("INFO")
        logger.propagate = False

        handler = _CaptureHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)

        audit_tool_call(
            logger,
            tool_name="list_storage_accounts",
            status="success",
            duration_ms=12.5,
            safety_class="read_only",
            target_context={
                "resource_group": "rg-1",
                "api_key": "super-secret-value",
                "nested": {"client_secret": "hidden"},
            },
        )

        self.assertEqual(len(handler.formatted), 1)
        payload = json.loads(handler.formatted[0])
        self.assertEqual(payload["tool_name"], "list_storage_accounts")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["correlation_id"], "test-correlation-id")
        self.assertEqual(payload["target_context"]["resource_group"], "rg-1")
        self.assertEqual(payload["target_context"]["api_key"], "[REDACTED]")
        self.assertEqual(payload["target_context"]["nested"]["client_secret"], "[REDACTED]")
        self.assertEqual(payload["safety_class"], "read_only")
        self.assertEqual(payload["duration_ms"], 12.5)

    def test_audit_log_records_error_code_for_failure(self) -> None:
        set_correlation_id("test-correlation-id-error")

        logger = logging.getLogger("test.monitor.error")
        logger.handlers = []
        logger.setLevel("INFO")
        logger.propagate = False

        handler = _CaptureHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)

        audit_tool_call(
            logger,
            tool_name="list_virtual_machines",
            status="error",
            duration_ms=7.25,
            safety_class="read_only",
            target_context={
                "resource_group": "rg-ops",
                "sas_token": "abc123",
            },
            error_code="THROTTLED",
        )

        self.assertEqual(len(handler.formatted), 1)
        payload = json.loads(handler.formatted[0])
        self.assertEqual(payload["tool_name"], "list_virtual_machines")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_code"], "THROTTLED")
        self.assertEqual(payload["correlation_id"], "test-correlation-id-error")
        self.assertEqual(payload["target_context"]["resource_group"], "rg-ops")
        self.assertEqual(payload["target_context"]["sas_token"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
