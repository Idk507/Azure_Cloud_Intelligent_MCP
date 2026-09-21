from __future__ import annotations

import os
import unittest


@unittest.skipUnless(
    os.environ.get("RUN_AZURE_INTEGRATION_TESTS") == "1",
    "Opt-in integration tests require dedicated non-production Azure resources.",
)
class AzureIntegrationTestCase(unittest.TestCase):
    def test_read_only_integration_scope_is_explicit(self) -> None:
        self.assertTrue(os.environ.get("AZURE_SUBSCRIPTION_ID"))
        self.assertTrue(os.environ.get("AZURE_INTEGRATION_RESOURCE_GROUP"))


if __name__ == "__main__":
    unittest.main()
