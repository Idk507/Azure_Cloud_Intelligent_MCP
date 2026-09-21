from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
    def list_agents(self, project_endpoint: str):
        return [{"id": "agent-1", "name": "ops", "status": "active"}]

    def create_agent(self, project_endpoint: str, agent_name: str, instructions: str):
        return {"id": "agent-2", "name": agent_name}

    def delete_agent(self, project_endpoint: str, agent_id: str):
        return True


class Slice34TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {"AZURE_SUBSCRIPTION_ID": "sub-123"},
            clear=False,
        )
        self.env_patch.start()
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
                has_explicit_approval=False,
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
                has_explicit_approval=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_foundry_listing_requires_verified_adapter(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.list_ai_foundry_agents(project_endpoint=self.endpoint)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "AI_FOUNDRY_NOT_CONFIGURED")

    def test_foundry_agent_lifecycle_uses_adapter_and_approval(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            listed = ai.list_ai_foundry_agents(project_endpoint=self.endpoint)
            denied = ai.create_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_name="ops",
                instructions="Inspect health.",
                has_explicit_approval=False,
            )
            created = ai.create_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_name="ops",
                instructions="Inspect health.",
                has_explicit_approval=True,
            )
            deleted = ai.delete_ai_foundry_agent(
                project_endpoint=self.endpoint,
                agent_id="agent-1",
                has_explicit_approval=True,
            )

        self.assertTrue(listed["ok"])
        self.assertEqual(listed["agents"][0]["id"], "agent-1")
        self.assertEqual(denied["error"]["code"], "APPROVAL_REQUIRED")
        self.assertTrue(created["ok"])
        self.assertTrue(deleted["deleted"])


if __name__ == "__main__":
    unittest.main()
