"""Microsoft Foundry Agent Service data-plane adapter.

The Azure management SDK does not manage agents.  This adapter keeps the
Foundry data-plane dependency isolated and imports it lazily so non-Foundry
deployments keep working without accidental network calls at startup.
"""
from __future__ import annotations

from typing import Any

from .auth import build_credential
from .config import load_settings


class FoundryAgentServiceAdapter:
    """Small, version-tolerant wrapper around ``azure-ai-projects`` agents."""

    def _agents(self, project_endpoint: str) -> Any:
        from azure.ai.projects import AIProjectClient

        client = AIProjectClient(endpoint=project_endpoint, credential=build_credential(load_settings()))
        return client.agents

    def _project(self, project_endpoint: str) -> Any:
        from azure.ai.projects import AIProjectClient
        return AIProjectClient(endpoint=project_endpoint, credential=build_credential(load_settings()))

    def list_models(self, project_endpoint: str) -> Any:
        """List project model metadata through the SDK without guessing endpoints."""
        models = getattr(self._project(project_endpoint), "models", None)
        if models is None or not hasattr(models, "list"):
            raise RuntimeError("The configured azure-ai-projects SDK does not expose model discovery.")
        return models.list()

    def list_connections(self, project_endpoint: str) -> Any:
        """List connection metadata only; callers must redact credentials."""
        connections = getattr(self._project(project_endpoint), "connections", None)
        if connections is None or not hasattr(connections, "list"):
            raise RuntimeError("The configured azure-ai-projects SDK does not expose connection discovery.")
        return connections.list()

    def list_agents(self, project_endpoint: str) -> Any:
        return self._agents(project_endpoint).list_agents()

    def get_agent(self, project_endpoint: str, agent_id: str) -> Any:
        return self._agents(project_endpoint).get_agent(agent_id)

    def create_agent(self, project_endpoint: str, agent_name: str, instructions: str, model: str | None = None) -> Any:
        if not model:
            raise ValueError("model is required to create a Foundry agent.")
        return self._agents(project_endpoint).create_agent(name=agent_name, instructions=instructions, model=model)

    def update_agent(self, project_endpoint: str, agent_id: str, instructions: str | None = None, model: str | None = None) -> Any:
        changes = {key: value for key, value in {"instructions": instructions, "model": model}.items() if value is not None}
        return self._agents(project_endpoint).update_agent(agent_id, **changes)

    def delete_agent(self, project_endpoint: str, agent_id: str) -> Any:
        return self._agents(project_endpoint).delete_agent(agent_id)
