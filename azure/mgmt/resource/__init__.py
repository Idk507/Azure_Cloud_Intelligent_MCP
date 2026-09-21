class _ResourceGroups:
    def list(self):
        return []


class ResourceManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.resource_groups = _ResourceGroups()
