from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import deployments


class DeploymentToolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"}, clear=False)
        self.env_patch.start()
        self.what_if_payload = None

        def begin_what_if(resource_group: str, name: str, payload: dict):
            self.what_if_payload = (resource_group, name, payload)
            return SimpleNamespace(result=lambda: SimpleNamespace(changes=[SimpleNamespace(change_type="Modify", resource_id="/resource/a")]))

        self.clients = SimpleNamespace(
            resource=SimpleNamespace(
                deployments=SimpleNamespace(begin_what_if=begin_what_if),
                deployment_operations=SimpleNamespace(
                    get=lambda resource_group, deployment_name, operation_id: SimpleNamespace(
                        operation_id=operation_id,
                        provisioning_state="Succeeded",
                        status_code="OK",
                        target_resource=SimpleNamespace(id="/resource/a", resource_name="a", resource_type="Microsoft.Storage/storageAccounts"),
                    )
                ),
            )
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_previews_resource_group_template_without_execution(self) -> None:
        with patch.object(deployments.azure_clients, "get_azure_clients", return_value=self.clients):
            result = deployments.preview_arm_template_deployment(
                resource_group="rg-a",
                deployment_name="preview-a",
                template={"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#", "resources": []},
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["preview_only"])
        self.assertEqual(self.what_if_payload[2]["properties"]["mode"], "Incremental")
        self.assertEqual(result["changes"][0]["change_type"], "Modify")

    def test_reads_one_named_deployment_operation(self) -> None:
        with patch.object(deployments.azure_clients, "get_azure_clients", return_value=self.clients):
            result = deployments.get_arm_deployment_operation_status("rg-a", "deploy-a", "operation-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation"]["provisioning_state"], "Succeeded")

    def test_rejects_template_without_resources(self) -> None:
        result = deployments.preview_arm_template_deployment("rg-a", "preview-a", {"resources": "invalid"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
