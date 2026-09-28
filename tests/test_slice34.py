from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import approvals
from src.tools import ai


class FakeDeployments:
    def list(self, resource_group: str, account_name: str):
        return [
            SimpleNamespace(
                id="/deployment/1",
                name="chat",
                model=SimpleNamespace(name="gpt-4o", version="2024-08-06"),
                sku=SimpleNamespace(name="GlobalStandard", capacity=1),
                provisioning_state="Succeeded",
            )
        ]

    def begin_create_or_update(self, resource_group: str, account_name: str, deployment_name: str, payload: dict):
        return SimpleNamespace(name=deployment_name, payload=payload)


class FakeFoundryAdapter:
    def list_models(self, project_endpoint: str):
        return [{"id": "model-1", "name": "gpt-4o", "type": "model", "api_key": "must-not-leak"}]

    def list_connections(self, project_endpoint: str):
        return [{"id": "connection-1", "name": "search", "type": "azure_ai_search", "connection_string": "must-not-leak"}]

    def list_agents(self, project_endpoint: str):
        return [{"id": "agent-1", "name": "ops", "status": "active"}]

    def create_agent(self, project_endpoint: str, agent_name: str, instructions: str, model: str):
        return {"id": "agent-2", "name": agent_name, "model": model}

    def delete_agent(self, project_endpoint: str, agent_id: str):
        return True

    def get_agent(self, project_endpoint: str, agent_id: str):
        return {"id": agent_id, "name": "ops", "instructions": "Inspect health.", "model": "gpt-4o"}

    def update_agent(self, project_endpoint: str, agent_id: str, instructions: str | None = None, model: str | None = None):
        return {"id": agent_id, "instructions": instructions, "model": model}


class Slice34TestCase(unittest.TestCase):
    def setUp(self) -> None:
        approvals.reset_approval_store()
        self.env_patch = patch.dict(
            os.environ,
            {"AZURE_SUBSCRIPTION_ID": "sub-123"},
            clear=False,
        )
        self.env_patch.start()
        approvals.reset_approval_store()
        self.clients = SimpleNamespace(
            cognitive=SimpleNamespace(deployments=FakeDeployments()),
            ai_foundry=None,
        )
        self.endpoint = "https://account.services.ai.azure.com/api/projects/project"

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_list_openai_deployments_success(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.list_openai_deployments(resource_group="rg-a", account_name="account")

        self.assertTrue(result["ok"])
        self.assertEqual(result["deployments"][0]["model_name"], "gpt-4o")

    def test_deploy_openai_model_requires_approval(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", side_effect=AssertionError("should not call azure")):
            result = ai.deploy_openai_model(
                resource_group="rg-a",
                account_name="account",
                deployment_name="chat",
                model_name="gpt-4o",
                model_version="2024-08-06",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_deploy_openai_model_with_approval(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.deploy_openai_model(
                resource_group="rg-a",
                account_name="account",
                deployment_name="chat",
                model_name="gpt-4o",
                model_version="2024-08-06",
                approval_id=ai.plan_openai_deployment("rg-a", "account", "chat", "gpt-4o", "2024-08-06")["approval"]["approval_id"],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_foundry_listing_requires_verified_adapter(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.list_ai_foundry_agents(project_endpoint=self.endpoint)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "AI_FOUNDRY_NOT_CONFIGURED")

    def test_foundry_model_and_connection_inventory_redacts_credentials(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            models = ai.list_ai_foundry_models(self.endpoint)
            connections = ai.list_ai_foundry_connections(self.endpoint)
        self.assertTrue(models["ok"])
        self.assertTrue(connections["ok"])
        self.assertNotIn("api_key", models["models"][0])
        self.assertNotIn("connection_string", connections["connections"][0])

    def test_foundry_trace_status_never_returns_connection_values(self) -> None:
        with patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=secret"}, clear=False):
            result = ai.get_ai_foundry_trace_status(self.endpoint)
        self.assertTrue(result["ok"])
        self.assertTrue(result["application_insights_configured"])
        self.assertNotIn("InstrumentationKey", str(result))

    def test_foundry_agent_lifecycle_uses_adapter_and_approval(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            listed = ai.list_ai_foundry_agents(project_endpoint=self.endpoint)
            denied = ai.create_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_name="ops",
                instructions="Inspect health.",
                model="gpt-4o",
            )
            create_plan = ai.plan_ai_foundry_agent_mutation(
                operation="create", project_endpoint=self.endpoint, agent_name="ops", instructions="Inspect health.", model="gpt-4o"
            )
            created = ai.create_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_name="ops",
                instructions="Inspect health.",
                model="gpt-4o",
                approval_id=create_plan["approval"]["approval_id"],
            )
            delete_plan = ai.plan_ai_foundry_agent_mutation(operation="delete", project_endpoint=self.endpoint, agent_id="agent-1")
            deleted = ai.delete_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_id="agent-1",
                approval_id=delete_plan["approval"]["approval_id"],
            )
            read = ai.get_ai_foundry_agent(project_endpoint=self.endpoint, agent_id="agent-1")
            update_plan = ai.plan_ai_foundry_agent_mutation(
                operation="update", project_endpoint=self.endpoint, agent_id="agent-1", instructions="Inspect production health."
            )
            updated = ai.update_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_id="agent-1",
                instructions="Inspect production health.",
                approval_id=update_plan["approval"]["approval_id"],
            )

        self.assertTrue(listed["ok"])
        self.assertEqual(listed["agents"][0]["id"], "agent-1")
        self.assertEqual(denied["error"]["code"], "APPROVAL_ID_REQUIRED")
        self.assertTrue(created["ok"])
        self.assertTrue(deleted["deleted"])
        self.assertEqual(read["agent"]["id"], "agent-1")
        self.assertTrue(updated["ok"])
        self.assertEqual(updated["agent"]["instructions"], "Inspect production health.")


if __name__ == "__main__":
    unittest.main()
