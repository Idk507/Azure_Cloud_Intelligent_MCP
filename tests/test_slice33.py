from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import cost, monitoring


class FakeLogs:
    def query_workspace(self, workspace_id: str, query: str, timespan):
        return {"rows": [[1], [2], [3]]}


class FakeMetrics:
    def query_resource(self, resource_uri: str, metric_names: list[str], timespan, interval: str):
        return {"metrics": [{"name": name} for name in metric_names]}


class FakeCostUsage:
    def usage(self, scope: str, parameters: dict):
        return {"rows": [["Service A", 10.5], ["Service B", 4.25]]}


class FakeRecommendations:
    def list(self, resource_group_name: str | None = None):
        return [
            SimpleNamespace(
                id="/advisor/1",
                category="Cost",
                impact="Medium",
                short_description="Right-size resource",
                resource_id="/subscriptions/sub/resourceGroups/rg-a/providers/test/r1",
            )
        ]


class Slice33TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {"AZURE_SUBSCRIPTION_ID": "sub-123", "MAX_RESULTS": "50"},
            clear=False,
        )
        self.env_patch.start()
        self.clients = SimpleNamespace(
            monitor={"logs": FakeLogs(), "metrics": FakeMetrics()},
            cost=SimpleNamespace(query=SimpleNamespace(usage=FakeCostUsage().usage)),
            advisor=SimpleNamespace(recommendations=FakeRecommendations()),
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_log_query_is_bounded_and_truncated(self) -> None:
        with patch.object(monitoring.azure_clients, "get_azure_clients", return_value=self.clients):
            result = monitoring.query_log_analytics(
                workspace_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/ws",
                query="Heartbeat | take 3",
                limit=2,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["truncated"])

    def test_log_query_rejects_mutating_query(self) -> None:
        result = monitoring.query_log_analytics(
            workspace_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/ws",
            query="T | .drop table T",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_metrics_success(self) -> None:
        with patch.object(monitoring.azure_clients, "get_azure_clients", return_value=self.clients):
            result = monitoring.get_resource_metrics(
                resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-a",
                metric_names=["Percentage.CPU", "Network.In"],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)

    def test_cost_summary_is_bounded(self) -> None:
        with patch.object(cost.azure_clients, "get_azure_clients", return_value=self.clients):
            result = cost.get_cost_summary(scope="/subscriptions/sub", days=30)

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["days"], 30)

    def test_cost_summary_rejects_long_range(self) -> None:
        result = cost.get_cost_summary(scope="/subscriptions/sub", days=91)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_advisor_recommendations_success(self) -> None:
        with patch.object(cost.azure_clients, "get_azure_clients", return_value=self.clients):
            result = cost.list_advisor_recommendations(resource_group="rg-a", limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["recommendations"][0]["category"], "Cost")


if __name__ == "__main__":
    unittest.main()
