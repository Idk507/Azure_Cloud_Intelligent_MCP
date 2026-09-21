from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


def run_with_timeout(callback: Callable[[], T], timeout_seconds: int) -> T:
    """Execute a callable in a background thread and enforce a wall-clock deadline.

    Submits ``callback`` to a single-worker ``ThreadPoolExecutor`` and waits
    for the result up to ``timeout_seconds``.  If the future does not complete
    in time, ``concurrent.futures.TimeoutError`` is caught and re-raised as the
    built-in ``TimeoutError`` so that ``sanitize_azure_error`` can map it to
    the ``TIMEOUT`` error code without depending on ``concurrent.futures``.

    The executor is used as a context manager so the background thread is
    always cleaned up, even when a timeout occurs.

    Args:
        callback:        Zero-argument callable to execute.  Typically a lambda
                         that wraps an Azure SDK call.
        timeout_seconds: Maximum number of seconds to wait for the result.

    Returns:
        The return value of ``callback()``.

    Raises:
        TimeoutError: When ``callback`` does not complete within
                      ``timeout_seconds``.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callback)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise TimeoutError("Operation timed out before completion.") from exc
