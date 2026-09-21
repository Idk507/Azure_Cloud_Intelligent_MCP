from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


RESOURCE_GROUP_PATTERN = re.compile(r"^[A-Za-z0-9._()/-]{1,90}$")
LOCATION_PATTERN = re.compile(r"^[a-z0-9]+(?:[a-z0-9-]{0,48}[a-z0-9])?$")
VM_NAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?$")
STORAGE_ACCOUNT_PATTERN = re.compile(r"^[a-z0-9]{3,24}$")
CONTAINER_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
METRIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
DEPLOYMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PaginationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int | None = Field(default=None, ge=1)


class ResourceGroupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str = Field(min_length=1, max_length=90)

    @field_validator("resource_group")
    @classmethod
    def validate_resource_group(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_group must be a non-empty string.")
        if not RESOURCE_GROUP_PATTERN.match(normalized):
            raise ValueError("resource_group contains unsupported characters.")
        return normalized

class AzureScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str = Field(min_length=1, max_length=300)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/subscriptions/"):
            raise ValueError("scope must start with '/subscriptions/'.")
        return normalized


class AzureResourceIdInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str = Field(min_length=1, max_length=600)

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/subscriptions/"):
            raise ValueError("resource_id must start with '/subscriptions/'.")
        return normalized


class AzureLocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=2, max_length=50)

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not LOCATION_PATTERN.match(normalized):
            raise ValueError("location must use Azure region naming format.")
        return normalized


class VirtualMachineTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str = Field(min_length=1, max_length=90)
    vm_name: str = Field(min_length=1, max_length=64)

    @field_validator("resource_group")
    @classmethod
    def validate_resource_group(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_group must be a non-empty string.")
        if not RESOURCE_GROUP_PATTERN.match(normalized):
            raise ValueError("resource_group contains unsupported characters.")
        return normalized

    @field_validator("vm_name")
    @classmethod
    def validate_vm_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("vm_name must be a non-empty string.")
        if not VM_NAME_PATTERN.match(normalized):
            raise ValueError("vm_name contains unsupported characters.")
        return normalized


class StorageAccountCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str = Field(min_length=1, max_length=90)
    account_name: str = Field(min_length=3, max_length=24)
    location: str | None = Field(default=None, min_length=2, max_length=50)
    sku_name: str = Field(default="Standard_LRS", min_length=3, max_length=50)
    kind: str = Field(default="StorageV2", min_length=3, max_length=32)

    @field_validator("resource_group")
    @classmethod
    def validate_resource_group(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_group must be a non-empty string.")
        if not RESOURCE_GROUP_PATTERN.match(normalized):
            raise ValueError("resource_group contains unsupported characters.")
        return normalized

    @field_validator("account_name")
    @classmethod
    def validate_account_name(cls, value: str) -> str:
        normalized = value.strip()
        if not STORAGE_ACCOUNT_PATTERN.match(normalized):
            raise ValueError("account_name must be 3-24 lowercase letters or digits.")
        return normalized

    @field_validator("location")
    @classmethod
    def validate_optional_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not LOCATION_PATTERN.match(normalized):
            raise ValueError("location must use Azure region naming format.")
        return normalized


class BlobTransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str = Field(min_length=1, max_length=90)
    account_name: str = Field(min_length=3, max_length=24)
    container_name: str = Field(min_length=3, max_length=63)
    blob_name: str = Field(min_length=1, max_length=1024)

    @field_validator("resource_group")
    @classmethod
    def validate_resource_group(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_group must be a non-empty string.")
        if not RESOURCE_GROUP_PATTERN.match(normalized):
            raise ValueError("resource_group contains unsupported characters.")
        return normalized

    @field_validator("account_name")
    @classmethod
    def validate_account_name(cls, value: str) -> str:
        normalized = value.strip()
        if not STORAGE_ACCOUNT_PATTERN.match(normalized):
            raise ValueError("account_name must be 3-24 lowercase letters or digits.")
        return normalized

    @field_validator("container_name")
    @classmethod
    def validate_container_name(cls, value: str) -> str:
        normalized = value.strip()
        if not CONTAINER_NAME_PATTERN.match(normalized):
            raise ValueError("container_name contains unsupported characters.")
        return normalized

    @field_validator("blob_name")
    @classmethod
    def validate_blob_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("blob_name must be a non-empty string.")
        return normalized


class LogQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=600)
    query: str = Field(min_length=1, max_length=2000)
    timespan_hours: int = Field(default=24, ge=1, le=168)
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/subscriptions/"):
            raise ValueError("workspace_id must be an Azure resource ID.")
        return normalized

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if ";" in normalized:
            raise ValueError("query must contain a single statement.")
        forbidden = (".drop", ".delete", ".alter", ".ingest", ".set", "externaldata")
        lowered = normalized.lower()
        if any(token in lowered for token in forbidden):
            raise ValueError("query contains a prohibited operation.")
        return normalized


class MetricsQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str = Field(min_length=1, max_length=600)
    metric_names: list[str] = Field(min_length=1, max_length=10)
    timespan_hours: int = Field(default=1, ge=1, le=168)
    interval_minutes: int = Field(default=5, ge=1, le=60)
    limit: int = Field(default=200, ge=1, le=500)

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/subscriptions/"):
            raise ValueError("resource_id must be an Azure resource ID.")
        return normalized

    @field_validator("metric_names")
    @classmethod
    def validate_metric_names(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if not normalized or any(not METRIC_NAME_PATTERN.match(value) for value in normalized):
            raise ValueError("metric_names contains an unsupported metric name.")
        return normalized


class CostQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str = Field(min_length=1, max_length=600)
    days: int = Field(default=30, ge=1, le=90)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/subscriptions/"):
            raise ValueError("scope must be an Azure subscription or resource scope.")
        return normalized


class OpenAIDeploymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str = Field(min_length=1, max_length=90)
    account_name: str = Field(min_length=1, max_length=64)
    deployment_name: str = Field(min_length=1, max_length=64)

    @field_validator("resource_group", "account_name", "deployment_name")
    @classmethod
    def validate_names(cls, value: str, info) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must be non-empty.")
        if info.field_name == "deployment_name" and not DEPLOYMENT_NAME_PATTERN.match(normalized):
            raise ValueError("deployment_name contains unsupported characters.")
        return normalized


class OpenAIDeploymentCreateInput(OpenAIDeploymentInput):
    model_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=64)
    sku_name: str = Field(default="GlobalStandard", min_length=1, max_length=64)
    capacity: int = Field(default=1, ge=1, le=1000)

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not MODEL_NAME_PATTERN.match(normalized):
            raise ValueError("model_name contains unsupported characters.")
        return normalized


class FoundryProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_endpoint: str = Field(min_length=1, max_length=500)

    @field_validator("project_endpoint")
    @classmethod
    def validate_project_endpoint(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith("https://") or "/api/projects/" not in normalized:
            raise ValueError("project_endpoint must be an Azure AI project endpoint.")
        return normalized


class FoundryAgentCreateInput(FoundryProjectInput):
    agent_name: str = Field(min_length=1, max_length=128)
    instructions: str = Field(min_length=1, max_length=4000)


class FoundryAgentTargetInput(FoundryProjectInput):
    agent_id: str = Field(min_length=1, max_length=256)


def to_validation_error_payload(exc: ValidationError) -> dict[str, object]:
    """Convert a Pydantic ``ValidationError`` into the standard tool error envelope.

    Extracts the structured error list from the exception and wraps it in the
    ``{ok: False, error: {...}}`` shape that all tool functions return, so that
    MCP clients receive a consistent response regardless of whether the error
    originated from a validation check or an Azure API call.

    Args:
        exc: The ``ValidationError`` raised by a Pydantic model.

    Returns:
        ``{"ok": False, "error": {"code": "VALIDATION_ERROR", "message": ...,
        "details": [<pydantic error dicts>]}}``
    """
    return {
        "ok": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Input validation failed.",
            "details": exc.errors(),
        },
    }
