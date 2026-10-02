from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import approvals
from src.tools import ai


class FakePaged:
    def __init__(self, first, second=None):
        self.first = first
        self.second = second
        self.continuation_token = None

    def __iter__(self):
        return iter(self.first + (self.second or []))

    def by_page(self, continuation_token=None):
        if continuation_token == "deployment-cursor-2":
            self.continuation_token = None
            yield self.second or []
        else:
            self.continuation_token = "deployment-cursor-2" if self.second else None
            yield self.first


class FakeDeployments:
    def list(self, resource_group: str, account_name: str):
        return FakePaged(
            [SimpleNamespace(
                id="/deployment/1",
                name="chat",
                model=SimpleNamespace(name="gpt-4o", version="2024-08-06"),
                sku=SimpleNamespace(name="GlobalStandard", capacity=1),
                provisioning_state="Succeeded",
            )],
            [SimpleNamespace(id="/deployment/2", name="chat-small", model=SimpleNamespace(name="gpt-4o-mini", version="2024-07-18"), sku=SimpleNamespace(name="GlobalStandard", capacity=1), provisioning_state="Succeeded")],
        )

    def begin_create_or_update(self, resource_group: str, account_name: str, deployment_name: str, payload: dict):
        return SimpleNamespace(name=deployment_name, payload=payload)


class FakeProjectConnections:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str, str, str]] = []

    def delete(self, resource_group: str, account_name: str, project_name: str, connection_name: str) -> None:
        self.deleted.append((resource_group, account_name, project_name, connection_name))

    def get(self, resource_group: str, account_name: str, project_name: str, connection_name: str):
        return SimpleNamespace(id="/connection/1", name=connection_name, properties=SimpleNamespace(target="https://search.example", category="CognitiveSearch", auth_type="ApiKey", credentials="secret"))

    def create(self, resource_group: str, account_name: str, project_name: str, connection_name: str, connection: dict):
        return SimpleNamespace(id="/connection/1", name=connection_name, type="CognitiveSearch", credentials="secret")


class FakeFoundryAdapter:
    def list_models_page(self, project_endpoint: str, cursor: str | None = None):
        if cursor == "cursor-2":
            return {"items": [{"id": "model-2", "name": "small-model", "type": "model"}], "next_cursor": None}
        return {"items": [{"id": "model-1", "name": "gpt-4o", "type": "model"}], "next_cursor": "cursor-2"}

    def create_evaluation(self, project_endpoint: str, definition: dict):
        return {"id": "eval-2", "name": definition["name"], "status": "queued", "created_at": "now"}

    def list_evaluations(self, project_endpoint: str, limit: int):
        return [{"id": "eval-1", "name": "release-check", "status": "completed", "created_at": "now", "testing_criteria": "must-not-leak"}]

    def list_evaluation_runs(self, project_endpoint: str, evaluation_id: str, limit: int):
        return [{"id": "run-1", "status": "completed", "created_at": "now", "result": "must-not-leak"}]

    def list_agent_threads(self, project_endpoint: str, agent_id: str):
        return [{"id": "thread-1", "created_at": "now", "metadata": {"secret": "must-not-leak"}}]
    def list_agent_runs(self, project_endpoint: str, thread_id: str):
        return [{"id": "run-1", "agent_id": "agent-1", "status": "completed", "input": "must-not-leak"}]
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
        self.project_connections = FakeProjectConnections()
        self.clients = SimpleNamespace(
            cognitive=SimpleNamespace(deployments=FakeDeployments(), project_connections=self.project_connections),
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

    def test_openai_deployment_inventory_returns_an_opaque_next_cursor(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            first_page = ai.list_openai_deployments(resource_group="rg-a", account_name="account", limit=1)
            second_page = ai.list_openai_deployments(resource_group="rg-a", account_name="account", limit=1, cursor="deployment-cursor-2")
        self.assertEqual(first_page["next_cursor"], "deployment-cursor-2")
        self.assertEqual(second_page["deployments"][0]["name"], "chat-small")

    def test_foundry_evaluation_reads_exclude_criteria_and_results(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            evaluations = ai.list_ai_foundry_evaluations(self.endpoint)
            runs = ai.list_ai_foundry_evaluation_runs(self.endpoint, "eval-1")
        self.assertTrue(evaluations["ok"])
        self.assertEqual(evaluations["evaluations"][0]["name"], "release-check")
        self.assertNotIn("testing_criteria", evaluations["evaluations"][0])
        self.assertTrue(runs["ok"])
        self.assertNotIn("result", runs["evaluation_runs"][0])

    def test_foundry_evaluation_creation_requires_matching_approval(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        definition = {
            "name": "release-check",
            "data_source_config": {"type": "custom", "item_schema": {"type": "object"}},
            "testing_criteria": [{"type": "text_similarity", "name": "quality"}],
        }
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            denied = ai.create_ai_foundry_evaluation(self.endpoint, definition)
            plan = ai.plan_ai_foundry_evaluation_creation(self.endpoint, definition)
            created = ai.create_ai_foundry_evaluation(self.endpoint, definition, plan["approval"]["approval_id"])
        self.assertEqual(denied["error"]["code"], "APPROVAL_REQUIRED")
        self.assertTrue(created["ok"])
        self.assertEqual(created["evaluation"]["id"], "eval-2")

    def test_foundry_model_inventory_returns_an_opaque_next_cursor(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            first_page = ai.list_ai_foundry_models(self.endpoint, limit=1)
            second_page = ai.list_ai_foundry_models(self.endpoint, limit=1, cursor="cursor-2")
        self.assertEqual(first_page["next_cursor"], "cursor-2")
        self.assertEqual(second_page["models"][0]["id"], "model-2")

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

    def test_foundry_thread_runs_exclude_inputs_and_outputs(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.list_ai_foundry_thread_runs(self.endpoint, "thread-1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["runs"][0]["status"], "completed")
        self.assertNotIn("input", result["runs"][0])

    def test_foundry_agent_threads_exclude_metadata(self) -> None:
        self.clients.ai_foundry = FakeFoundryAdapter()
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.list_ai_foundry_agent_threads(self.endpoint, "agent-1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["threads"][0]["id"], "thread-1")
        self.assertNotIn("metadata", result["threads"][0])

    def test_foundry_project_connection_delete_requires_matching_single_use_approval(self) -> None:
        plan = ai.plan_ai_foundry_connection_deletion("rg-a", "account", "project", "conn-one")
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            deleted = ai.delete_ai_foundry_project_connection("rg-a", "account", "project", "conn-one", plan["approval"]["approval_id"])
            replay = ai.delete_ai_foundry_project_connection("rg-a", "account", "project", "conn-one", plan["approval"]["approval_id"])
        self.assertTrue(deleted["ok"])
        self.assertEqual(replay["error"]["code"], "APPROVAL_INVALID")
        self.assertEqual(self.project_connections.deleted, [("rg-a", "account", "project", "conn-one")])

    def test_foundry_project_connection_read_excludes_credentials(self) -> None:
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            result = ai.get_ai_foundry_project_connection("rg-a", "account", "project", "conn-one")
        self.assertTrue(result["ok"])
        self.assertEqual(result["connection"]["name"], "conn-one")
        self.assertNotIn("credentials", result["connection"])

    def test_foundry_project_connection_upsert_binds_the_exact_payload(self) -> None:
        payload = {"properties": {"category": "CognitiveSearch", "target": "https://search.example", "authType": "None"}}
        plan = ai.plan_ai_foundry_connection_upsert("rg-a", "account", "project", "conn-one", payload)
        with patch.object(ai.azure_clients, "get_azure_clients", return_value=self.clients):
            denied = ai.upsert_ai_foundry_project_connection("rg-a", "account", "project", "conn-one", {"properties": {"category": "CognitiveSearch", "target": "https://other.example", "authType": "None"}}, plan["approval"]["approval_id"])
            accepted = ai.upsert_ai_foundry_project_connection("rg-a", "account", "project", "conn-one", payload, ai.plan_ai_foundry_connection_upsert("rg-a", "account", "project", "conn-one", payload)["approval"]["approval_id"])
        self.assertEqual(denied["error"]["code"], "APPROVAL_INVALID")
        self.assertTrue(accepted["ok"])
        self.assertNotIn("credentials", accepted["connection"])

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
