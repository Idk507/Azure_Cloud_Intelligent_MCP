class _Vaults:
    def list_by_resource_group(self, resource_group: str):
        return []


class KeyVaultManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.vaults = _Vaults()
