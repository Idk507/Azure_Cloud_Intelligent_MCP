from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import resource_graph


class ResourceGraphTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"}, clear=False)
        self.env_patch.start()
        self.request = None

        def query(query: str, subscriptions: list[str], limit: int):
            self.request = (query, subscriptions, limit)
            return [{"id": "/subscriptions/sub-1/resourceGroups/rg-a/providers/Microsoft.Storage/storageAccounts/a", "name": "a", "type": "Microsoft.Storage/storageAccounts"}]

        self.clients = SimpleNamespace(resource_graph=SimpleNamespace(query=query))

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_queries_explicit_subscriptions_with_eventual_consistency_notice(self) -> None:
        with patch.object(resource_graph.azure_clients, "get_azure_clients", return_value=self.clients):
            result = resource_graph.query_azure_resource_graph(
                query="Resources | where type =~ 'Microsoft.Storage/storageAccounts' | project id, name, type",
                subscriptions=["sub-1"],
                limit=10,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(self.request[1], ["sub-1"])
        self.assertTrue(result["eventual_consistency"])
        self.assertEqual(result["resources"][0]["name"], "a")

    def test_rejects_unbounded_or_non_inventory_kql(self) -> None:
        result = resource_graph.query_azure_resource_graph(
            query="Resources | join resourcecontainers on subscriptionId",
            subscriptions=["sub-1"],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
