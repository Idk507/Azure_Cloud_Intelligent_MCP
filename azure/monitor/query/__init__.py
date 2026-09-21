class LogsQueryClient:
    def __init__(self, credential):
        self.credential = credential

    def query_workspace(self, workspace_id: str, query: str, timespan):
        return {"rows": []}


class MetricsQueryClient:
    def __init__(self, credential):
        self.credential = credential

    def query_resource(self, resource_uri: str, metric_names: list[str], timespan, interval: str):
        return {"metrics": []}
