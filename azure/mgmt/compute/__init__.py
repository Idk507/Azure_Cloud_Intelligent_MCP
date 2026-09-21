class _VirtualMachines:
    def list(self, resource_group: str):
        return []


class ComputeManagementClient:
    def __init__(self, credential, subscription_id: str, **kwargs):
        self.credential = credential
        self.subscription_id = subscription_id
        self.kwargs = kwargs
        self.virtual_machines = _VirtualMachines()
