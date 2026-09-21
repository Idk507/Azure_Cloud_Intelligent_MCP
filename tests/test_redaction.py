from __future__ import annotations

import unittest

from src.utils.redaction import redact_sensitive_data


class RedactionTestCase(unittest.TestCase):
    def test_redacts_nested_mappings_and_lists(self) -> None:
        payload = {
            "client_secret": "top-secret",
            "safe": "value",
            "nested": {
                "api_key": "k-123",
                "list": [
                    {"token": "abc"},
                    {"name": "ok"},
                    "plain",
                ],
            },
        }

        redacted = redact_sensitive_data(payload)

        self.assertEqual(redacted["client_secret"], "[REDACTED]")
        self.assertEqual(redacted["safe"], "value")
        self.assertEqual(redacted["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["list"][0]["token"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["list"][1]["name"], "ok")
        self.assertEqual(redacted["nested"]["list"][2], "plain")


if __name__ == "__main__":
    unittest.main()
