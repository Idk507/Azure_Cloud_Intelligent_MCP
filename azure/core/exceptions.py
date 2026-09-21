class AzureError(Exception):
    """Base Azure shim exception."""


class HttpResponseError(AzureError):
    def __init__(self, message: str = "", status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ResourceNotFoundError(HttpResponseError):
    pass


class ClientAuthenticationError(HttpResponseError):
    pass


class ServiceRequestError(HttpResponseError):
    pass
