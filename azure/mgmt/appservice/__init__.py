class _WebApps:
    def list(self):
        return []

    def list_by_resource_group(self, resource_group: str):
        return []


class WebSiteManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.web_apps = _WebApps()
