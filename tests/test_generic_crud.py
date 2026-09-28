from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import approvals
from src.tools import resource_mgmt


class GenericCrudTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"}, clear=False)
        self.env_patch.start()
        self.resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/store"
        self.clients = SimpleNamespace(resource=SimpleNamespace(resources=SimpleNamespace(
            get_by_id=lambda resource_id, api_version: {"id": resource_id, "api_version": api_version},
            begin_create_or_update=lambda *args, **kwargs: SimpleNamespace(result=lambda: {"ok": True}),
            begin_update_by_id=lambda *args, **kwargs: SimpleNamespace(result=lambda: {"ok": True}),
            begin_delete_by_id=lambda *args, **kwargs: SimpleNamespace(result=lambda: None),
        )))
        approvals.reset_approval_store()

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_generic_read(self) -> None:
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self.clients):
            result = resource_mgmt.get_azure_resource(self.resource_id, "2023-01-01")
        self.assertTrue(result["ok"])
        self.assertEqual(result["resource"]["id"], self.resource_id)

    def test_mutations_require_matching_single_use_approval_plan(self) -> None:
        payload = {"location": "eastus", "properties": {"kind": "StorageV2"}}
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self.clients):
            denied = resource_mgmt.update_azure_resource(self.resource_id, "2023-01-01", payload)
            create_plan = resource_mgmt.plan_azure_resource_mutation("create", self.resource_id, "2023-01-01", payload)
            update_plan = resource_mgmt.plan_azure_resource_mutation("update", self.resource_id, "2023-01-01", payload)
            delete_plan = resource_mgmt.plan_azure_resource_mutation("delete", self.resource_id, "2023-01-01")
            created = resource_mgmt.create_azure_resource(self.resource_id, "2023-01-01", payload, approval_id=create_plan["approval"]["approval_id"])
            updated = resource_mgmt.update_azure_resource(self.resource_id, "2023-01-01", payload, approval_id=update_plan["approval"]["approval_id"])
            deleted = resource_mgmt.delete_azure_resource(self.resource_id, "2023-01-01", approval_id=delete_plan["approval"]["approval_id"])
            replay = resource_mgmt.delete_azure_resource(self.resource_id, "2023-01-01", approval_id=delete_plan["approval"]["approval_id"])

        self.assertEqual(denied["error"]["code"], "APPROVAL_ID_REQUIRED")
        self.assertTrue(created["ok"])
        self.assertTrue(updated["ok"])
        self.assertTrue(deleted["ok"])
        self.assertEqual(replay["error"]["code"], "APPROVAL_INVALID")

    def test_generic_read_rejects_malformed_id(self) -> None:
        result = resource_mgmt.get_azure_resource("not-an-id", "2023-01-01")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
