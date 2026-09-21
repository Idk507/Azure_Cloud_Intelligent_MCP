from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import advanced


class _Collection:
    def list(self):
        return [SimpleNamespace(id="/cluster/1", name="aks-a", location="eastus", provisioning_state="Succeeded", tags={})]

    def list_by_resource_group(self, resource_group: str):
        return [SimpleNamespace(id="/app/1", name="func-a", location="eastus", provisioning_state="Running", tags={})]


class AdvancedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123", "MAX_RESULTS": "50"}, clear=False)
        self.env_patch.start()
        self.clients = SimpleNamespace(
            aks=SimpleNamespace(managed_clusters=_Collection()),
            appservice=SimpleNamespace(web_apps=_Collection()),
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_list_aks_clusters_success(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_aks_clusters(limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["clusters"][0]["name"], "aks-a")

    def test_list_function_apps_scopes_resource_group(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_function_apps(resource_group="rg-a", limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["function_apps"][0]["name"], "func-a")
        self.assertEqual(result["resource_group"], "rg-a")

    def test_advanced_inventory_rejects_invalid_limit(self) -> None:
        result = advanced.list_aks_clusters(limit=0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_function_logs_use_bounded_monitor_query(self) -> None:
        with patch.object(
            advanced.monitoring,
            "query_log_analytics",
            return_value={"ok": True, "count": 1, "rows": [["2026-09-21", "Info", "started"]]},
        ) as query:
            result = advanced.query_function_app_logs(
                workspace_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/ws",
                function_app_name="func-a",
                limit=10,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data_classification"], "sensitive_operational_logs")
        query.assert_called_once()
        self.assertIn("AppServiceConsoleLogs", query.call_args.kwargs["query"])

    def test_function_logs_reject_invalid_name(self) -> None:
        result = advanced.query_function_app_logs(
            workspace_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/ws",
            function_app_name="func'; drop table Logs",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
