class _Deployments:
    def list(self, resource_group_name: str, account_name: str):
        return []

    def begin_create_or_update(self, resource_group_name: str, account_name: str, deployment_name: str, payload: dict):
        return {
            "resource_group": resource_group_name,
            "account_name": account_name,
            "deployment_name": deployment_name,
            "payload": payload,
        }


class CognitiveServicesManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.deployments = _Deployments()
