class _Usage:
    def usage(self, scope: str, parameters: dict):
        return {"rows": []}


class _Query:
    def __init__(self):
        self.usage = _Usage().usage


class CostManagementClient:
    def __init__(self, credential, **kwargs):
        self.credential = credential
        self.kwargs = kwargs
        self.query = _Query()
