"""Adapter for Azure Resource Graph's data-plane query contract."""
from __future__ import annotations

from typing import Any


class AzureResourceGraphAdapter:
    """Construct Resource Graph requests lazily to keep startup dependency-free."""

    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def query(self, query: str, subscriptions: list[str], limit: int) -> list[dict[str, Any]]:
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

        client = ResourceGraphClient(self._credential)
        response = client.resources(
            QueryRequest(
                query=query,
                subscriptions=subscriptions,
                options=QueryRequestOptions(top=limit, result_format="objectArray"),
            )
        )
        return list(response.data or [])
