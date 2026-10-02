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

    @staticmethod
    def _page(pager: Any, cursor: str | None = None) -> dict[str, Any]:
        """Read one Azure SDK ``ItemPaged`` page and preserve its opaque token."""
        if not hasattr(pager, "by_page"):
            if cursor:
                raise ValueError("The configured SDK does not support continuation cursors for this operation.")
            return {"items": list(pager), "next_cursor": None}
        pages = pager.by_page(continuation_token=cursor) if cursor else pager.by_page()
        try:
            items = list(next(pages))
        except StopIteration:
            items = []
        return {"items": items, "next_cursor": getattr(pager, "continuation_token", None)}

    def list_models_page(self, project_endpoint: str, cursor: str | None = None) -> dict[str, Any]:
        """Return one opaque-cursor page of model metadata."""
        return self._page(self.list_models(project_endpoint), cursor)

    def list_connections(self, project_endpoint: str) -> Any:
        """List connection metadata only; callers must redact credentials."""
        connections = getattr(self._project(project_endpoint), "connections", None)
        if connections is None or not hasattr(connections, "list"):
            raise RuntimeError("The configured azure-ai-projects SDK does not expose connection discovery.")
        return connections.list()

    def list_connections_page(self, project_endpoint: str, cursor: str | None = None) -> dict[str, Any]:
        """Return one opaque-cursor page of connection metadata."""
        return self._page(self.list_connections(project_endpoint), cursor)

    def _openai_client(self, project_endpoint: str) -> Any:
        """Return the Foundry project's OpenAI-compatible client for evaluations."""
        client_factory = getattr(self._project(project_endpoint), "get_openai_client", None)
        if not callable(client_factory):
            raise RuntimeError("The configured azure-ai-projects SDK does not expose an OpenAI-compatible client.")
        return client_factory()

    def list_evaluations(self, project_endpoint: str, limit: int) -> Any:
        """List evaluation definitions through the documented project OpenAI client."""
        return self._openai_client(project_endpoint).evals.list(limit=limit)

    def list_evaluation_runs(self, project_endpoint: str, evaluation_id: str, limit: int) -> Any:
        """List evaluation-run metadata without retrieving scored sample content."""
        return self._openai_client(project_endpoint).evals.runs.list(evaluation_id, limit=limit)

    def create_evaluation(self, project_endpoint: str, definition: dict[str, Any]) -> Any:
        """Create a project evaluation from an already-approved definition."""
        return self._openai_client(project_endpoint).evals.create(**definition)

    def list_agent_threads(self, project_endpoint: str, agent_id: str) -> Any:
        return self._agents(project_endpoint).threads.list(agent_id=agent_id)

    def list_agent_runs(self, project_endpoint: str, thread_id: str) -> Any:
        return self._agents(project_endpoint).runs.list(thread_id)

    def list_agent_messages(self, project_endpoint: str, thread_id: str) -> Any:
        return self._agents(project_endpoint).messages.list(thread_id)

    def list_agents(self, project_endpoint: str) -> Any:
        """List agents across supported Azure AI Projects SDK generations.

        Older Agent Service clients expose ``list_agents()``, while the
        current Azure AI Projects SDK exposes ``agents.list()``. Both are
        read-only; accepting either keeps inventory available without
        guessing or adapting mutation payloads between incompatible APIs.
        """
        agents = self._agents(project_endpoint)
        legacy_list = getattr(agents, "list_agents", None)
        if callable(legacy_list):
            return legacy_list()
        current_list = getattr(agents, "list", None)
        if callable(current_list):
            return current_list()
        raise RuntimeError("The configured azure-ai-projects SDK does not expose agent inventory.")

    def get_agent(self, project_endpoint: str, agent_id: str) -> Any:
        agents = self._agents(project_endpoint)
        legacy_get = getattr(agents, "get_agent", None)
        if callable(legacy_get):
            return legacy_get(agent_id)
        current_get = getattr(agents, "get", None)
        if callable(current_get):
            return current_get(agent_id)
        raise RuntimeError("The configured azure-ai-projects SDK does not expose agent retrieval.")

    def create_agent(self, project_endpoint: str, agent_name: str, instructions: str, model: str | None = None) -> Any:
        if not model:
            raise ValueError("model is required to create a Foundry agent.")
        agents = self._agents(project_endpoint)
        legacy_create = getattr(agents, "create_agent", None)
        if callable(legacy_create):
            return legacy_create(name=agent_name, instructions=instructions, model=model)
        current_create = getattr(agents, "create_version", None)
        if callable(current_create):
            from azure.ai.projects.models import PromptAgentDefinition
            return current_create(agent_name=agent_name, definition=PromptAgentDefinition(model=model, instructions=instructions))
        raise RuntimeError("The configured azure-ai-projects SDK does not expose prompt-agent creation.")

    def update_agent(self, project_endpoint: str, agent_id: str, instructions: str | None = None, model: str | None = None) -> Any:
        changes = {key: value for key, value in {"instructions": instructions, "model": model}.items() if value is not None}
        agents = self._agents(project_endpoint)
        legacy_update = getattr(agents, "update_agent", None)
        if callable(legacy_update):
            return legacy_update(agent_id, **changes)
        current_create = getattr(agents, "create_version", None)
        if callable(current_create):
            if not instructions or not model:
                raise ValueError("The current Foundry SDK creates immutable agent versions; provide both instructions and model for an approved update.")
            from azure.ai.projects.models import PromptAgentDefinition
            return current_create(agent_name=agent_id, definition=PromptAgentDefinition(model=model, instructions=instructions))
        raise RuntimeError("The configured azure-ai-projects SDK does not expose agent updates.")

    def delete_agent(self, project_endpoint: str, agent_id: str) -> Any:
        agents = self._agents(project_endpoint)
        legacy_delete = getattr(agents, "delete_agent", None)
        if callable(legacy_delete):
            return legacy_delete(agent_id)
        current_delete = getattr(agents, "delete", None)
        if callable(current_delete):
            return current_delete(agent_id)
        raise RuntimeError("The configured azure-ai-projects SDK does not expose agent deletion.")
