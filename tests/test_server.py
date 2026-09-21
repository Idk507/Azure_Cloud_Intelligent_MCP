from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from src import app


class ServerTestCase(unittest.TestCase):
    def test_initialize_response_shape(self) -> None:
        response = app.initialize_response()

        self.assertTrue(response["protocolVersion"])
        self.assertEqual(response["serverInfo"]["name"], app.SERVER_NAME)
        self.assertTrue(response["capabilities"]["tools"]["list"])
        self.assertTrue(response["capabilities"]["tools"]["call"])

    def test_tools_list_response_contains_phase1_and_phase3_slice31_tools(self) -> None:
        payload = app.tools_list_response()
        names = [tool["name"] for tool in payload["tools"]]

        self.assertIn("list_resource_groups", names)
        self.assertIn("list_virtual_machines", names)
        self.assertIn("list_storage_accounts", names)
        self.assertIn("get_virtual_machine_status", names)
        self.assertIn("start_virtual_machine", names)
        self.assertIn("stop_virtual_machine", names)
        self.assertIn("create_storage_account", names)
        self.assertIn("upload_blob_content", names)
        self.assertIn("download_blob_content", names)
        self.assertIn("list_virtual_networks", names)
        self.assertIn("list_network_security_groups", names)
        self.assertIn("list_public_ip_addresses", names)
        self.assertIn("create_public_ip_address", names)
        self.assertIn("list_key_vaults", names)
        self.assertIn("query_log_analytics", names)
        self.assertIn("get_resource_metrics", names)
        self.assertIn("get_cost_summary", names)
        self.assertIn("list_advisor_recommendations", names)
        self.assertIn("list_openai_deployments", names)
        self.assertIn("deploy_openai_model", names)
        self.assertIn("list_ai_foundry_agents", names)
        self.assertIn("create_ai_foundry_agent", names)
        self.assertIn("delete_ai_foundry_agent", names)
        self.assertIn("diagnose_virtual_machine", names)

    def test_health_endpoint_returns_degraded_without_subscription(self) -> None:
        previous = os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
        try:
            client = TestClient(app.http_app)
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "degraded")
        finally:
            if previous is not None:
                os.environ["AZURE_SUBSCRIPTION_ID"] = previous

    def test_health_endpoint_returns_ok_with_subscription(self) -> None:
        previous = os.environ.get("AZURE_SUBSCRIPTION_ID")
        os.environ["AZURE_SUBSCRIPTION_ID"] = "sub-123"
        try:
            client = TestClient(app.http_app)
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
        finally:
            if previous is None:
                os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
            else:
                os.environ["AZURE_SUBSCRIPTION_ID"] = previous


if __name__ == "__main__":
    unittest.main()
