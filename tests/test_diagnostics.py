from __future__ import annotations

import unittest
from unittest.mock import patch

from src.tools import diagnostics


class DiagnosticsTestCase(unittest.TestCase):
    def test_diagnostic_keeps_observations_and_inferences_separate(self) -> None:
        status = {
            "ok": True,
            "power_state": "deallocated",
            "statuses": [{"code": "PowerState/deallocated"}],
        }
        advisor = {"ok": True, "count": 0, "recommendations": []}

        with patch.object(diagnostics.compute, "get_virtual_machine_status", return_value=status):
            with patch.object(diagnostics.cost, "list_advisor_recommendations", return_value=advisor):
                result = diagnostics.diagnose_virtual_machine(resource_group="rg-a", vm_name="vm-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["inferences"], [])
        self.assertEqual(result["observations"][0]["value"], "deallocated")
        self.assertIn("metrics_not_requested", result["incomplete_evidence"])
        self.assertTrue(result["next_actions"])

    def test_diagnostic_includes_metrics_when_requested(self) -> None:
        status = {"ok": True, "power_state": "running", "statuses": []}
        metrics = {"ok": True, "count": 1, "metrics": [{"name": "Percentage.CPU"}]}
        advisor = {"ok": True, "count": 0, "recommendations": []}

        with patch.object(diagnostics.compute, "get_virtual_machine_status", return_value=status):
            with patch.object(diagnostics.monitoring, "get_resource_metrics", return_value=metrics):
                with patch.object(diagnostics.cost, "list_advisor_recommendations", return_value=advisor):
                    result = diagnostics.diagnose_virtual_machine(
                        resource_group="rg-a",
                        vm_name="vm-a",
                        resource_id="/subscriptions/sub/resourceGroups/rg-a/providers/Microsoft.Compute/virtualMachines/vm-a",
                        workspace_id="/subscriptions/sub/resourceGroups/rg-a/providers/Microsoft.OperationalInsights/workspaces/ws",
                        metric_names=["Percentage.CPU"],
                    )

        self.assertTrue(result["ok"])
        self.assertEqual(result["incomplete_evidence"], [])
        self.assertIn("monitor.metrics", result["evidence_sources"])
        self.assertEqual(len(result["observations"]), 3)

    def test_diagnostic_rejects_invalid_resource_id(self) -> None:
        result = diagnostics.diagnose_virtual_machine(
            resource_group="rg-a",
            vm_name="vm-a",
            resource_id="not-an-azure-id",
            metric_names=["Percentage.CPU"],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
