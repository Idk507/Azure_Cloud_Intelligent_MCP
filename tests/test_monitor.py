from __future__ import annotations

import json
import logging
import unittest

from src.monitor import JsonLogFormatter, audit_tool_call, set_correlation_id


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.formatted: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.formatted.append(self.format(record))


class MonitorTestCase(unittest.TestCase):
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
