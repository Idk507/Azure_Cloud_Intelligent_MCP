class _ResourceGroups:
    def list(self):
        return []


class _Poller:
    def __init__(self, value=None):
        self.value = value

    def result(self):
        return self.value


class _Resources:
    def list(self):
        return []

    def list_by_resource_group(self, resource_group: str):
        return []

    def get_by_id(self, resource_id: str, *, api_version: str):
        return {"id": resource_id, "api_version": api_version, "properties": {}}

    def begin_create_or_update(self, resource_group_name: str, resource_provider_namespace: str, parent_resource_path: str, resource_type: str, resource_name: str, parameters: dict, *, api_version: str):
        return _Poller({"id": f"/subscriptions/shim/resourceGroups/{resource_group_name}/providers/{resource_provider_namespace}/{resource_type}/{resource_name}", "properties": parameters.get("properties", {})})

    def begin_update_by_id(self, resource_id: str, parameters: dict, *, api_version: str):
        return _Poller({"id": resource_id, "properties": parameters.get("properties", {})})

    def begin_delete_by_id(self, resource_id: str, *, api_version: str):
        return _Poller(None)


class _Providers:
    def list(self):
        return []


class ResourceManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.resource_groups = _ResourceGroups()
        self.resources = _Resources()
        self.providers = _Providers()
