class DefaultAzureCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class ClientSecretCredential:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
