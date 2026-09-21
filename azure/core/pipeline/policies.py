class RetryPolicy:
    def __init__(
        self,
        total_retries: int = 3,
        retry_backoff_factor: float = 0.8,
        retry_mode: str = "exponential",
    ):
        self.total_retries = total_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_mode = retry_mode
