from __future__ import annotations

from .config import ConfigError, Settings


def build_credential(settings: Settings):
    """Build an Azure credential from settings, preferring explicit service principal.

    Checks whether all three service-principal fields (``tenant_id``,
    ``client_id``, ``client_secret``) are present in ``settings``.

    - If all three are set, returns a ``ClientSecretCredential``.
    - If none are set, returns a ``DefaultAzureCredential`` (which walks the
      standard Azure credential chain: env vars, managed identity, Azure CLI,
      etc.) with the interactive browser excluded for headless server use.
    - If only some are set, raises ``ConfigError`` to prevent silent
      misconfiguration.

    Args:
        settings: Loaded application settings containing optional SP fields.

    Returns:
        An Azure credential object compatible with all Azure SDK clients.

    Raises:
        ConfigError: When only a subset of the service-principal fields are set.
    """
    from azure.identity import ClientSecretCredential, DefaultAzureCredential

    explicit_values = [settings.tenant_id, settings.client_id, settings.client_secret]
    has_explicit_values = any(explicit_values)

    if has_explicit_values and not all(explicit_values):
        raise ConfigError(
            "AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET must all be set "
            "when using service principal authentication."
        )

    if all(explicit_values):
        return ClientSecretCredential(
            tenant_id=settings.tenant_id,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)
