class _Collection:
    def list(self, resource_group: str):
        return []

    def begin_create_or_update(self, resource_group: str, name: str, payload: dict):
        return {"resource_group": resource_group, "name": name, "payload": payload}


class NetworkManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.virtual_networks = _Collection()
        self.network_security_groups = _Collection()
        self.public_ip_addresses = _Collection()
