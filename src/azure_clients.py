from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any

from .auth import build_credential
from .config import Settings, load_settings

if TYPE_CHECKING:  # pragma: no cover
    from azure.mgmt.appservice import WebSiteManagementClient
    from azure.mgmt.containerservice import ContainerServiceClient
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    from azure.mgmt.keyvault import KeyVaultManagementClient
    from azure.mgmt.advisor import AdvisorManagementClient
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.storage import StorageManagementClient
    from azure.monitor.query import LogsQueryClient, MetricsQueryClient


@dataclass(frozen=True)
class AzureClients:
    resource: Any
    compute: Any
    storage: Any
    network: Any = None
    keyvault: Any = None
    monitor: Any = None
    cost: Any = None
    advisor: Any = None
    cognitive: Any = None
    ai_foundry: Any = None
    aks: Any = None
    appservice: Any = None
    sql: Any = None
    cosmos: Any = None
    ml: Any = None


_clients_lock = Lock()
_cached_clients: AzureClients | None = None


def _build_retry_policy(settings: Settings):
    """Construct an exponential-backoff retry policy from application settings.

    Creates an Azure Core ``RetryPolicy`` configured with the values from
    ``settings``.  All Azure SDK management clients share this policy so that
    transient failures (network blips, 429 throttling) are retried
    automatically without caller involvement.

    Args:
        settings: Loaded application settings supplying ``retry_total`` and
                  ``retry_backoff_factor``.

    Returns:
        A configured ``azure.core.pipeline.policies.RetryPolicy`` instance.
    """

    from azure.core.pipeline.policies import RetryPolicy

    return RetryPolicy(
        total_retries=settings.retry_total,
        retry_backoff_factor=settings.retry_backoff_factor,
        retry_mode="exponential",
    )


def create_azure_clients(settings: Settings) -> AzureClients:
    from azure.mgmt.appservice import WebSiteManagementClient
    from azure.mgmt.containerservice import ContainerServiceClient
    """Instantiate and bundle all Azure SDK management clients.

    Builds a credential via ``build_credential``, constructs a shared retry
    policy via ``_build_retry_policy``, and creates one client per Azure
    service plane.  The monitor entry is a plain dict keyed by
    ``"logs"`` / ``"metrics"`` because the Azure Monitor query clients do not
    share the same base class as the management clients.

    Args:
        settings: Loaded application settings containing subscription ID,
                  credential fields, and retry configuration.

    Returns:
        A frozen ``AzureClients`` dataclass holding all initialised clients.
    """
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    from azure.mgmt.keyvault import KeyVaultManagementClient
    from azure.mgmt.advisor import AdvisorManagementClient
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.storage import StorageManagementClient

    credential = build_credential(settings)
    retry_policy = _build_retry_policy(settings)

    client_kwargs: dict[str, Any] = {
        "retry_policy": retry_policy,
    }

    resource_client = ResourceManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    compute_client = ComputeManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    storage_client = StorageManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    network_client = NetworkManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    keyvault_client = KeyVaultManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    from azure.monitor.query import LogsQueryClient, MetricsQueryClient

    monitor_client = {
        "logs": LogsQueryClient(credential),
        "metrics": MetricsQueryClient(credential),
    }
    cost_client = CostManagementClient(credential, **client_kwargs)
    advisor_client = AdvisorManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    cognitive_client = CognitiveServicesManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    aks_client = ContainerServiceClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )
    appservice_client = WebSiteManagementClient(
        credential,
        settings.subscription_id,
        **client_kwargs,
    )

    return AzureClients(
        resource=resource_client,
        compute=compute_client,
        storage=storage_client,
        network=network_client,
        keyvault=keyvault_client,
        monitor=monitor_client,
        cost=cost_client,
        advisor=advisor_client,
        cognitive=cognitive_client,
        ai_foundry=None,
        aks=aks_client,
        appservice=appservice_client,
    )


def get_azure_clients() -> AzureClients:
    """Return the process-wide singleton ``AzureClients``, creating it on first call.

    Uses a double-checked locking pattern with ``_clients_lock`` to ensure
    that ``create_azure_clients`` is called exactly once even under concurrent
    requests.  Subsequent calls return the cached instance without acquiring
    the lock.

    Returns:
        The singleton ``AzureClients`` instance for the current process.
    """
    global _cached_clients
    if _cached_clients is not None:
        return _cached_clients

    with _clients_lock:
        if _cached_clients is None:
            settings = load_settings()
            _cached_clients = create_azure_clients(settings)

    return _cached_clients


def reset_client_cache() -> None:
    """Discard the cached ``AzureClients`` singleton.

    Forces the next call to ``get_azure_clients`` to rebuild all clients from
    scratch.  Primarily used in tests to inject fresh mocks between test cases
    without restarting the process.
    """
    global _cached_clients
    with _clients_lock:
        _cached_clients = None
