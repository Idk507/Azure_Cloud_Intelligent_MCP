from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.config import load_settings
from src.tools.subscriptions import list_accessible_subscriptions


class PortableOnboardingTests(unittest.TestCase):
    def test_allows_startup_without_a_preselected_subscription(self) -> None:
        settings = load_settings({})

        self.assertIsNone(settings.subscription_id)

    def test_lists_accessible_subscriptions_without_a_preselected_subscription(self) -> None:
        client = SimpleNamespace(
            subscriptions=SimpleNamespace(
                list=lambda: [
                    SimpleNamespace(subscription_id="sub-a", display_name="Engineering", state="Enabled", tenant_id="tenant-a"),
                ]
            )
        )
        with patch("src.tools.subscriptions._subscription_client", return_value=client):
            result = list_accessible_subscriptions(limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["subscriptions"], [{"id": "sub-a", "name": "Engineering", "state": "Enabled", "tenant_id": "tenant-a"}])


if __name__ == "__main__":
    unittest.main()
