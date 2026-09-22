from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import resource_mgmt


class ResourceInventoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"}, clear=False)
        self.env_patch.start()
        self.clients = SimpleNamespace(
            resource=SimpleNamespace(
                resources=SimpleNamespace(
                    list=lambda: [SimpleNamespace(id="/r/1", name="r1", type="Microsoft.Storage/storageAccounts", location="eastus", tags={})],
                    list_by_resource_group=lambda rg: [SimpleNamespace(id="/r/2", name="r2", type="Microsoft.Compute/virtualMachines", location="eastus", tags={})],
                ),
                providers=SimpleNamespace(list=lambda: [SimpleNamespace(namespace="Microsoft.Storage", registration_state="Registered", resource_types=[SimpleNamespace(resource_type="storageAccounts")])]),
            )
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_lists_generic_resources(self) -> None:
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self.clients):
            result = resource_mgmt.list_azure_resources()
        self.assertTrue(result["ok"])
        self.assertEqual(result["resources"][0]["type"], "Microsoft.Storage/storageAccounts")

    def test_lists_resource_providers(self) -> None:
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self.clients):
            result = resource_mgmt.list_azure_resource_providers()
        self.assertTrue(result["ok"])
        self.assertEqual(result["providers"][0]["namespace"], "Microsoft.Storage")


if __name__ == "__main__":
    unittest.main()
