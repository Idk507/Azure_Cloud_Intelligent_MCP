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

    def list_slots(self, resource_group: str, app_name: str):
        return [SimpleNamespace(id="/slot/1", name="my-app/staging", location="eastus", state="Running", enabled=True, https_only=True, connection_strings="must-not-leak")]



class _ContainerAppCollection:
    def list_by_resource_group(self, resource_group: str):
        return [SimpleNamespace(id="/containerApps/mcp", name="mcp", location="eastus", provisioning_state="Succeeded", managed_environment_id="/managedEnvironments/env", latest_revision_name="mcp--0001", latest_ready_revision_name="mcp--0001", running_status="Running", workload_profile_name="Consumption", configuration="must-not-leak")]


class _ContainerEnvironmentCollection:
    def list_by_resource_group(self, resource_group: str):
        return [SimpleNamespace(id="/managedEnvironments/env", name="env", location="eastus", provisioning_state="Succeeded", zone_redundant=False, vnet_configuration=SimpleNamespace(internal=True, infrastructure_subnet_id="must-not-leak"), app_logs_configuration="must-not-leak")]


class _ContainerRevisionCollection:
    def list_revisions(self, resource_group: str, app_name: str):
        return [SimpleNamespace(id="/containerApps/mcp/revisions/mcp--0001", name="mcp--0001", properties=SimpleNamespace(active=True, created_time="2026-10-01T00:00:00Z", traffic_weight=100, provisioning_state="Provisioned", running_state="Running", health_state="Healthy", template="must-not-leak"))]


class AdvancedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123", "MAX_RESULTS": "50"}, clear=False)
        self.env_patch.start()
        self.clients = SimpleNamespace(
            aks=SimpleNamespace(managed_clusters=_Collection(), agent_pools=SimpleNamespace(list=lambda resource_group, cluster_name: [SimpleNamespace(id="/pool/1", name="system", count=3, vm_size="Standard_D4s_v5", mode="System", provisioning_state="Succeeded", type="VirtualMachineScaleSets", tags={})])),
            appservice=SimpleNamespace(web_apps=_Collection()),
            containerapps=SimpleNamespace(container_apps=_ContainerAppCollection(), managed_environments=_ContainerEnvironmentCollection(), container_apps_revisions=_ContainerRevisionCollection()),
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_list_aks_clusters_success(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_aks_clusters(limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["clusters"][0]["name"], "aks-a")

    def test_list_aks_node_pools_returns_capacity_without_credentials(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_aks_node_pools("rg-a", "aks-a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["node_pools"][0]["count"], 3)
        self.assertNotIn("kube_config", result["node_pools"][0])

    def test_list_function_apps_scopes_resource_group(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_function_apps(resource_group="rg-a", limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["function_apps"][0]["name"], "func-a")
        self.assertEqual(result["resource_group"], "rg-a")

    def test_list_app_service_slots_excludes_configuration_values(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_app_service_slots("rg-a", "my-app")
        self.assertTrue(result["ok"])
        self.assertEqual(result["slots"][0]["state"], "Running")
        self.assertNotIn("connection_strings", result["slots"][0])

    def test_list_container_apps_excludes_configuration_and_secrets(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_container_apps("rg-a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["container_apps"][0]["running_status"], "Running")
        self.assertNotIn("configuration", result["container_apps"][0])

    def test_list_container_app_environments_excludes_log_and_network_details(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_container_app_environments("rg-a")
        self.assertTrue(result["ok"])
        self.assertTrue(result["environments"][0]["is_internal"])
        self.assertNotIn("app_logs_configuration", result["environments"][0])
        self.assertNotIn("infrastructure_subnet_id", result["environments"][0])

    def test_list_container_app_revisions_excludes_revision_template(self) -> None:
        with patch.object(advanced.azure_clients, "get_azure_clients", return_value=self.clients):
            result = advanced.list_container_app_revisions("rg-a", "mcp")
        self.assertTrue(result["ok"])
        self.assertEqual(result["revisions"][0]["health_state"], "Healthy")
        self.assertNotIn("template", result["revisions"][0])

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
