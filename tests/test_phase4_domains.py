from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import advanced


class _SqlDatabases:
    def list_by_server(self, resource_group: str, server_name: str):
        return [SimpleNamespace(id="/db/1", name="db-a", status="Online", collation="SQL_Latin1_General_CP1_CI_AS", sku=SimpleNamespace(name="S0"))]


class _CosmosAccounts:
    def list(self):
        return [SimpleNamespace(id="/cosmos/1", name="cosmos-a", location="eastus", provisioning_state="Succeeded", tags={})]


class _CosmosData:
    def query_items(self, account_name: str, database_name: str, container_name: str, query: str, limit: int):
        return [{"id": "1", "value": "safe"}]


class _MLCollection:
    def list(self, workspace_name: str | None = None):
        return [SimpleNamespace(id="/ml/1", name="item-a", status="Completed", type="model")]


class DomainsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123", "MAX_RESULTS": "50"}, clear=False)
        self.env_patch.start()
        self.clients = SimpleNamespace(
            sql=SimpleNamespace(databases=_SqlDatabases()),
            cosmos=SimpleNamespace(database_accounts=_CosmosAccounts(), query_items=_CosmosData().query_items),
            ml=SimpleNamespace(workspaces=_MLCollection(), models=_MLCollection(), jobs=_MLCollection()),
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_sql_inventory(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_sql_databases("rg-a", "sql-a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["databases"][0]["name"], "db-a")

    def test_cosmos_inventory_and_query(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            inventory = advanced.list_cosmos_accounts("rg-a")
            query = advanced.query_cosmos_items("cosmos-a", "db-a", "container-a", "SELECT * FROM c")
        self.assertTrue(inventory["ok"])
        self.assertTrue(query["ok"])
        self.assertEqual(query["items"][0]["id"], "1")

    def test_cosmos_query_rejects_non_select(self) -> None:
        result = advanced.query_cosmos_items("cosmos-a", "db-a", "container-a", "DELETE FROM c")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_ml_inventory(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            workspaces = advanced.list_ml_workspaces()
            models = advanced.list_ml_models("workspace-a")
            jobs = advanced.list_ml_jobs("workspace-a")
        self.assertTrue(workspaces["ok"])
        self.assertTrue(models["ok"])
        self.assertTrue(jobs["ok"])
        self.assertEqual(models["models"][0]["name"], "item-a")


if __name__ == "__main__":
    unittest.main()
