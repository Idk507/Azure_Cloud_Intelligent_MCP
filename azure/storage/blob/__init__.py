class _BlobDownload:
    def __init__(self, content: bytes = b""):
        self._content = content

    def readall(self) -> bytes:
        return self._content


class _ContainerClient:
    def __init__(self):
        self._store: dict[str, bytes] = {}

    def upload_blob(self, blob_name: str, data: bytes, overwrite: bool = False):
        self._store[blob_name] = data
        return {"blob_name": blob_name, "overwrite": overwrite}

    def download_blob(self, blob_name: str):
        return _BlobDownload(self._store.get(blob_name, b""))


class BlobServiceClient:
    def __init__(self, account_url: str, credential=None):
        self.account_url = account_url
        self.credential = credential
        self._containers: dict[str, _ContainerClient] = {}

    def get_container_client(self, container_name: str):
        if container_name not in self._containers:
            self._containers[container_name] = _ContainerClient()
        return self._containers[container_name]
