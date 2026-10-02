from __future__ import annotations

import unittest

from src.foundry_adapter import FoundryAgentServiceAdapter


class _LegacyAgents:
    def list_agents(self):
        return ["legacy"]


class _CurrentAgents:
    def list(self):
        return ["current"]

    def get(self, agent_name):
        return {"name": agent_name}

    def delete(self, agent_name):
        return {"deleted": agent_name}


class FoundryAdapterTestCase(unittest.TestCase):
    def test_list_agents_supports_legacy_agent_service_method(self) -> None:
        adapter = FoundryAgentServiceAdapter()
        adapter._agents = lambda _endpoint: _LegacyAgents()  # type: ignore[method-assign]
        self.assertEqual(list(adapter.list_agents("https://project.example")), ["legacy"])

    def test_list_agents_supports_current_projects_sdk_method(self) -> None:
        adapter = FoundryAgentServiceAdapter()
        adapter._agents = lambda _endpoint: _CurrentAgents()  # type: ignore[method-assign]
        self.assertEqual(list(adapter.list_agents("https://project.example")), ["current"])

    def test_current_projects_sdk_get_and_delete_methods_are_supported(self) -> None:
        adapter = FoundryAgentServiceAdapter()
        adapter._agents = lambda _endpoint: _CurrentAgents()  # type: ignore[method-assign]
        self.assertEqual(adapter.get_agent("https://project.example", "agent-a")["name"], "agent-a")
        self.assertEqual(adapter.delete_agent("https://project.example", "agent-a")["deleted"], "agent-a")


if __name__ == "__main__":
    unittest.main()
