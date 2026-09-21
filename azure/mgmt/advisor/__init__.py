class _Recommendations:
    def list(self, resource_group_name: str | None = None):
        return []


class AdvisorManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.recommendations = _Recommendations()
