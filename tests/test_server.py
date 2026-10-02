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
        self.assertIn("list_storage_containers", names)
        self.assertIn("get_storage_lifecycle_policy", names)
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
        self.assertIn("list_key_vault_secret_metadata", names)
        self.assertIn("query_log_analytics", names)
        self.assertIn("get_resource_metrics", names)
        self.assertIn("get_cost_summary", names)
        self.assertIn("list_advisor_recommendations", names)
        self.assertIn("list_openai_deployments", names)
        self.assertIn("deploy_openai_model", names)
        self.assertIn("list_ai_foundry_agents", names)
        self.assertIn("get_ai_foundry_agent", names)
        self.assertIn("create_ai_foundry_agent", names)
        self.assertIn("plan_ai_foundry_agent_mutation", names)
        self.assertIn("update_ai_foundry_agent", names)
        self.assertIn("delete_ai_foundry_agent", names)
        self.assertIn("diagnose_virtual_machine", names)
        self.assertIn("list_aks_clusters", names)
        self.assertIn("list_aks_node_pools", names)
        self.assertIn("list_function_apps", names)
        self.assertIn("list_app_service_slots", names)
        self.assertIn("list_container_apps", names)
        self.assertIn("list_container_app_environments", names)
        self.assertIn("list_container_app_revisions", names)
        self.assertIn("query_function_app_logs", names)
        self.assertIn("list_sql_databases", names)
        self.assertIn("list_cosmos_accounts", names)
        self.assertIn("query_cosmos_items", names)
        self.assertIn("list_ml_workspaces", names)
        self.assertIn("list_ml_models", names)
        self.assertIn("list_ml_jobs", names)
        self.assertIn("query_azure_resource_graph", names)
        self.assertIn("plan_azure_resource_mutation", names)
        self.assertIn("preview_arm_template_deployment", names)
        self.assertIn("get_arm_deployment_operation_status", names)
        self.assertIn("plan_virtual_machine_power_action", names)
        self.assertIn("plan_storage_mutation", names)
        self.assertIn("plan_public_ip_creation", names)
        self.assertIn("plan_openai_deployment", names)
        self.assertIn("get_telemetry_snapshot", names)
        self.assertIn("list_role_assignments", names)
        self.assertIn("list_policy_definitions", names)
        self.assertIn("list_policy_assignments", names)
        self.assertIn("list_policy_compliance_states", names)
        self.assertIn("list_ai_foundry_models", names)
        self.assertIn("list_ai_foundry_connections", names)
        self.assertIn("get_ai_foundry_trace_status", names)
        self.assertIn("plan_ai_foundry_connection_deletion", names)
        self.assertIn("delete_ai_foundry_project_connection", names)
        self.assertIn("get_ai_foundry_project_connection", names)
        self.assertIn("plan_ai_foundry_connection_upsert", names)
        self.assertIn("upsert_ai_foundry_project_connection", names)
        self.assertIn("list_ai_foundry_thread_messages", names)
        self.assertIn("list_ai_foundry_thread_runs", names)
        self.assertIn("list_ai_foundry_agent_threads", names)
        self.assertIn("list_ai_foundry_evaluations", names)
        self.assertIn("list_ai_foundry_evaluation_runs", names)
        self.assertIn("plan_ai_foundry_evaluation_creation", names)
        self.assertIn("create_ai_foundry_evaluation", names)

    def test_health_endpoint_returns_ok_without_subscription_for_portable_onboarding(self) -> None:
        previous = os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
        try:
            client = TestClient(app.http_app)
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
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

    def test_streamable_mcp_initialize_is_available_at_mcp(self) -> None:
        """Keep the documented public connector URL stable and reachable."""
        request = {
            "jsonrpc": "2.0",
            "id": "route-regression-test",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }

        with TestClient(app.http_app, base_url="http://localhost:8000") as client:
            response = client.post("/mcp", json=request, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Azure Cloud Intelligence MCP", response.text)


if __name__ == "__main__":
    unittest.main()
