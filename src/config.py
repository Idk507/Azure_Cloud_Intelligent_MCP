from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    subscription_id: str
    tenant_id: str | None
    client_id: str | None
    client_secret: str | None
    default_location: str
    log_level: str
    request_timeout_seconds: int
    max_results: int
    retry_total: int
    retry_backoff_factor: float


_DEFAULT_LOCATION = "eastus"
_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_REQUEST_TIMEOUT = 30
_DEFAULT_MAX_RESULTS = 200
_DEFAULT_RETRY_TOTAL = 3
_DEFAULT_RETRY_BACKOFF_FACTOR = 0.8


def _parse_int(value: str | None, fallback: int, field_name: str) -> int:
    """Parse an optional environment-variable string as a positive integer.

    Returns ``fallback`` when ``value`` is absent or empty.  Raises
    ``ConfigError`` when the string cannot be converted to an integer or the
    resulting value is not positive.

    Args:
        value:      Raw string from the environment, or ``None``.
        fallback:   Value to use when ``value`` is absent.
        field_name: Variable name included in error messages.

    Returns:
        Parsed positive integer, or ``fallback``.

    Raises:
        ConfigError: On non-integer or non-positive input.
    """
    if value is None or value == "":
        return fallback
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must be an integer.") from exc
    if parsed <= 0:
        raise ConfigError(f"{field_name} must be greater than zero.")
    return parsed


def _parse_float(value: str | None, fallback: float, field_name: str) -> float:
    """Parse an optional environment-variable string as a non-negative float.

    Returns ``fallback`` when ``value`` is absent or empty.  Raises
    ``ConfigError`` when the string cannot be converted to a float or the
    resulting value is negative.

    Args:
        value:      Raw string from the environment, or ``None``.
        fallback:   Value to use when ``value`` is absent.
        field_name: Variable name included in error messages.

    Returns:
        Parsed non-negative float, or ``fallback``.

    Raises:
        ConfigError: On non-numeric or negative input.
    """
    if value is None or value == "":
        return fallback
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must be a number.") from exc
    if parsed < 0:
        raise ConfigError(f"{field_name} must be greater than or equal to zero.")
    return parsed


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Load and validate application settings from environment variables.

    Reads all configuration from ``env`` (or ``os.environ`` when ``None``).
    ``AZURE_SUBSCRIPTION_ID`` is mandatory; all other variables fall back to
    safe defaults.  Numeric variables are parsed and validated through
    ``_parse_int`` / ``_parse_float`` so that misconfigured deployments fail
    fast with a descriptive ``ConfigError`` rather than silently using zero or
    negative values.

    Args:
        env: Optional mapping to use instead of ``os.environ``.  Useful in
             tests to inject controlled values without mutating the process
             environment.

    Returns:
        A frozen ``Settings`` dataclass populated from the resolved environment.

    Raises:
        ConfigError: When ``AZURE_SUBSCRIPTION_ID`` is missing or any numeric
                     variable contains an invalid value.
    """
    resolved = env or os.environ

    subscription_id = resolved.get("AZURE_SUBSCRIPTION_ID", "").strip()
    if not subscription_id:
        raise ConfigError("AZURE_SUBSCRIPTION_ID is required.")

    tenant_id = resolved.get("AZURE_TENANT_ID") or None
    client_id = resolved.get("AZURE_CLIENT_ID") or None
    client_secret = resolved.get("AZURE_CLIENT_SECRET") or None

    default_location = resolved.get("DEFAULT_LOCATION", _DEFAULT_LOCATION).strip() or _DEFAULT_LOCATION
    log_level = resolved.get("LOG_LEVEL", _DEFAULT_LOG_LEVEL).strip().upper() or _DEFAULT_LOG_LEVEL

    request_timeout_seconds = _parse_int(
        resolved.get("REQUEST_TIMEOUT_SECONDS"),
        _DEFAULT_REQUEST_TIMEOUT,
        "REQUEST_TIMEOUT_SECONDS",
    )
    max_results = _parse_int(
        resolved.get("MAX_RESULTS"),
        _DEFAULT_MAX_RESULTS,
        "MAX_RESULTS",
    )
    retry_total = _parse_int(
        resolved.get("RETRY_TOTAL"),
        _DEFAULT_RETRY_TOTAL,
        "RETRY_TOTAL",
    )
    retry_backoff_factor = _parse_float(
        resolved.get("RETRY_BACKOFF_FACTOR"),
        _DEFAULT_RETRY_BACKOFF_FACTOR,
        "RETRY_BACKOFF_FACTOR",
    )

    return Settings(
        subscription_id=subscription_id,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        default_location=default_location,
        log_level=log_level,
        request_timeout_seconds=request_timeout_seconds,
        max_results=max_results,
        retry_total=retry_total,
        retry_backoff_factor=retry_backoff_factor,
    )
