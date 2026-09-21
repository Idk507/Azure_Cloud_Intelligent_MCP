from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "client_secret",
    "apikey",
    "api_key",
    "connectionstring",
    "connection_string",
    "sas",
)


def _is_sensitive_key(key: str) -> bool:
    """Return ``True`` when a dict key name suggests it holds sensitive data.

    Normalises the key to lowercase with hyphens replaced by underscores, then
    checks whether any fragment from ``SENSITIVE_KEY_FRAGMENTS`` appears as a
    substring.  This catches common variants such as ``"client-secret"``,
    ``"ClientSecret"``, ``"API_KEY"``, etc.

    Args:
        key: Dict key string to test.

    Returns:
        ``True`` if the key matches a sensitive fragment, ``False`` otherwise.
    """
    lowered = key.lower().replace("-", "_")
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_sensitive_data(value: Any) -> Any:
    """Recursively redact sensitive values from a nested data structure.

    Traverses dicts and sequences and replaces the *value* of any dict entry
    whose key is identified as sensitive by ``_is_sensitive_key`` with the
    string ``"[REDACTED]"``.  Non-sensitive values and all sequence items are
    recursed into so that nested structures are fully sanitised.

    Strings, bytes, and bytearrays are treated as scalars and returned
    unchanged (their content is not inspected).

    Args:
        value: Arbitrary Python value to sanitise.  Typically a ``dict``
               representing ``target_context`` from an audit log entry.

    Returns:
        A new structure of the same shape with sensitive values replaced by
        ``"[REDACTED]"``.
    """
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _is_sensitive_key(key_str):
                redacted[key_str] = "[REDACTED]"
            else:
                redacted[key_str] = redact_sensitive_data(item)
        return redacted

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_sensitive_data(item) for item in value]

    return value
