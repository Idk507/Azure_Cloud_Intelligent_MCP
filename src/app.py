from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from .config import ConfigError, load_settings
from .monitor import configure_logging, set_correlation_id
from .tool_registry import get_tool_metadata
from .tools.compute import (
    get_virtual_machine_status,
    list_virtual_machines,
    start_virtual_machine,
    stop_virtual_machine,
)
from .tools.resource_mgmt import list_resource_groups
from .tools.storage import (
    create_storage_account,
    download_blob_content,
    list_storage_accounts,
    upload_blob_content,
)
from .tools.keyvault import list_key_vaults
from .tools.monitoring import get_resource_metrics, query_log_analytics
from .tools.cost import get_cost_summary, list_advisor_recommendations
from .tools.ai import (
    create_ai_foundry_agent,
    delete_ai_foundry_agent,
    deploy_openai_model,
    list_ai_foundry_agents,
    list_openai_deployments,
)
from .tools.diagnostics import diagnose_virtual_machine
from .tools.network import (
    create_public_ip_address,
    list_network_security_groups,
    list_public_ip_addresses,
    list_virtual_networks,
)

SERVER_NAME = "Azure Cloud Intelligence MCP"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"

mcp = FastMCP(SERVER_NAME)

RG_TOOL_METADATA = get_tool_metadata("list_resource_groups")
VM_TOOL_METADATA = get_tool_metadata("list_virtual_machines")
ST_TOOL_METADATA = get_tool_metadata("list_storage_accounts")
VM_STATUS_TOOL_METADATA = get_tool_metadata("get_virtual_machine_status")
VM_START_TOOL_METADATA = get_tool_metadata("start_virtual_machine")
VM_STOP_TOOL_METADATA = get_tool_metadata("stop_virtual_machine")
ST_CREATE_TOOL_METADATA = get_tool_metadata("create_storage_account")
ST_UPLOAD_BLOB_TOOL_METADATA = get_tool_metadata("upload_blob_content")
ST_DOWNLOAD_BLOB_TOOL_METADATA = get_tool_metadata("download_blob_content")
VNET_TOOL_METADATA = get_tool_metadata("list_virtual_networks")
NSG_TOOL_METADATA = get_tool_metadata("list_network_security_groups")
PUBLIC_IP_TOOL_METADATA = get_tool_metadata("list_public_ip_addresses")
PUBLIC_IP_CREATE_TOOL_METADATA = get_tool_metadata("create_public_ip_address")
KEY_VAULT_TOOL_METADATA = get_tool_metadata("list_key_vaults")
LOG_QUERY_TOOL_METADATA = get_tool_metadata("query_log_analytics")
METRICS_TOOL_METADATA = get_tool_metadata("get_resource_metrics")
COST_TOOL_METADATA = get_tool_metadata("get_cost_summary")
ADVISOR_TOOL_METADATA = get_tool_metadata("list_advisor_recommendations")
OPENAI_LIST_TOOL_METADATA = get_tool_metadata("list_openai_deployments")
OPENAI_DEPLOY_TOOL_METADATA = get_tool_metadata("deploy_openai_model")
FOUNDRY_LIST_TOOL_METADATA = get_tool_metadata("list_ai_foundry_agents")
FOUNDRY_CREATE_TOOL_METADATA = get_tool_metadata("create_ai_foundry_agent")
FOUNDRY_DELETE_TOOL_METADATA = get_tool_metadata("delete_ai_foundry_agent")
DIAGNOSTIC_TOOL_METADATA = get_tool_metadata("diagnose_virtual_machine")


TOOL_DEFINITIONS = [
    {
        "name": RG_TOOL_METADATA.name,
        "description": RG_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": RG_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": RG_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": VM_TOOL_METADATA.name,
        "description": VM_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": VM_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": VM_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": ST_TOOL_METADATA.name,
        "description": ST_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": ST_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": ST_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": VM_STATUS_TOOL_METADATA.name,
        "description": VM_STATUS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "vm_name": {"type": "string", "minLength": 1},
            },
            "required": ["resource_group", "vm_name"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": VM_STATUS_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": VM_STATUS_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": VM_START_TOOL_METADATA.name,
        "description": VM_START_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "vm_name": {"type": "string", "minLength": 1},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "vm_name"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": VM_START_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": VM_START_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": VM_STOP_TOOL_METADATA.name,
        "description": VM_STOP_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "vm_name": {"type": "string", "minLength": 1},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "vm_name"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": VM_STOP_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": VM_STOP_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": ST_CREATE_TOOL_METADATA.name,
        "description": ST_CREATE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "account_name": {"type": "string", "minLength": 3, "maxLength": 24},
                "location": {"type": "string", "minLength": 2},
                "sku_name": {"type": "string", "minLength": 3},
                "kind": {"type": "string", "minLength": 3},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "account_name"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": ST_CREATE_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": ST_CREATE_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": ST_UPLOAD_BLOB_TOOL_METADATA.name,
        "description": ST_UPLOAD_BLOB_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "account_name": {"type": "string", "minLength": 3, "maxLength": 24},
                "container_name": {"type": "string", "minLength": 3},
                "blob_name": {"type": "string", "minLength": 1},
                "content_base64": {"type": "string", "minLength": 1},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "account_name", "container_name", "blob_name", "content_base64"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": ST_UPLOAD_BLOB_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": ST_UPLOAD_BLOB_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": ST_DOWNLOAD_BLOB_TOOL_METADATA.name,
        "description": ST_DOWNLOAD_BLOB_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "account_name": {"type": "string", "minLength": 3, "maxLength": 24},
                "container_name": {"type": "string", "minLength": 3},
                "blob_name": {"type": "string", "minLength": 1},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "account_name", "container_name", "blob_name"],
            "additionalProperties": False,
        },
        "x-metadata": {
            "safety_class": ST_DOWNLOAD_BLOB_TOOL_METADATA.safety_class.value,
            "minimum_rbac_role": ST_DOWNLOAD_BLOB_TOOL_METADATA.minimum_rbac_role,
        },
    },
    {
        "name": VNET_TOOL_METADATA.name,
        "description": VNET_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1}},
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": VNET_TOOL_METADATA.safety_class.value, "minimum_rbac_role": VNET_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": NSG_TOOL_METADATA.name,
        "description": NSG_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1}},
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": NSG_TOOL_METADATA.safety_class.value, "minimum_rbac_role": NSG_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": PUBLIC_IP_TOOL_METADATA.name,
        "description": PUBLIC_IP_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1}},
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": PUBLIC_IP_TOOL_METADATA.safety_class.value, "minimum_rbac_role": PUBLIC_IP_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": PUBLIC_IP_CREATE_TOOL_METADATA.name,
        "description": PUBLIC_IP_CREATE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "public_ip_name": {"type": "string", "minLength": 1, "maxLength": 80},
                "location": {"type": "string", "minLength": 2},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "public_ip_name", "location"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": PUBLIC_IP_CREATE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": PUBLIC_IP_CREATE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": KEY_VAULT_TOOL_METADATA.name,
        "description": KEY_VAULT_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1}},
            "required": ["resource_group"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": KEY_VAULT_TOOL_METADATA.safety_class.value, "minimum_rbac_role": KEY_VAULT_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": LOG_QUERY_TOOL_METADATA.name,
        "description": LOG_QUERY_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "minLength": 1},
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "timespan_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["workspace_id", "query"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": LOG_QUERY_TOOL_METADATA.safety_class.value, "minimum_rbac_role": LOG_QUERY_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": METRICS_TOOL_METADATA.name,
        "description": METRICS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "minLength": 1},
                "metric_names": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "string"}},
                "timespan_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                "interval_minutes": {"type": "integer", "minimum": 1, "maximum": 60},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["resource_id", "metric_names"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": METRICS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": METRICS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": COST_TOOL_METADATA.name,
        "description": COST_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"scope": {"type": "string", "minLength": 1}, "days": {"type": "integer", "minimum": 1, "maximum": 90}},
            "required": ["scope"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": COST_TOOL_METADATA.safety_class.value, "minimum_rbac_role": COST_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": ADVISOR_TOOL_METADATA.name,
        "description": ADVISOR_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": ADVISOR_TOOL_METADATA.safety_class.value, "minimum_rbac_role": ADVISOR_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": OPENAI_LIST_TOOL_METADATA.name,
        "description": OPENAI_LIST_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "account_name": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["resource_group", "account_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": OPENAI_LIST_TOOL_METADATA.safety_class.value, "minimum_rbac_role": OPENAI_LIST_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": OPENAI_DEPLOY_TOOL_METADATA.name,
        "description": OPENAI_DEPLOY_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "account_name": {"type": "string", "minLength": 1},
                "deployment_name": {"type": "string", "minLength": 1},
                "model_name": {"type": "string", "minLength": 1},
                "model_version": {"type": "string", "minLength": 1},
                "sku_name": {"type": "string", "minLength": 1},
                "capacity": {"type": "integer", "minimum": 1, "maximum": 1000},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["resource_group", "account_name", "deployment_name", "model_name", "model_version"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": OPENAI_DEPLOY_TOOL_METADATA.safety_class.value, "minimum_rbac_role": OPENAI_DEPLOY_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_LIST_TOOL_METADATA.name,
        "description": FOUNDRY_LIST_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"project_endpoint": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "required": ["project_endpoint"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": FOUNDRY_LIST_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_LIST_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_CREATE_TOOL_METADATA.name,
        "description": FOUNDRY_CREATE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_endpoint": {"type": "string", "minLength": 1},
                "agent_name": {"type": "string", "minLength": 1, "maxLength": 128},
                "instructions": {"type": "string", "minLength": 1, "maxLength": 4000},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["project_endpoint", "agent_name", "instructions"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": FOUNDRY_CREATE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_CREATE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_DELETE_TOOL_METADATA.name,
        "description": FOUNDRY_DELETE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_endpoint": {"type": "string", "minLength": 1},
                "agent_id": {"type": "string", "minLength": 1},
                "has_explicit_approval": {"type": "boolean"},
            },
            "required": ["project_endpoint", "agent_id"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": FOUNDRY_DELETE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_DELETE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": DIAGNOSTIC_TOOL_METADATA.name,
        "description": DIAGNOSTIC_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "minLength": 1},
                "vm_name": {"type": "string", "minLength": 1},
                "resource_id": {"type": "string", "minLength": 1},
                "workspace_id": {"type": "string", "minLength": 1},
                "metric_names": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                "timespan_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            },
            "required": ["resource_group", "vm_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": DIAGNOSTIC_TOOL_METADATA.safety_class.value, "minimum_rbac_role": DIAGNOSTIC_TOOL_METADATA.minimum_rbac_role},
    },
]


def initialize_response() -> dict[str, Any]:
    """Build the MCP ``initialize`` response payload.

    Returns the server name, version, and capability advertisement that the
    MCP client receives during the handshake phase.  Advertising
    ``tools.list`` and ``tools.call`` tells the client that this server
    supports tool discovery and invocation.

    Returns:
        A dict conforming to the MCP ``initialize`` response schema.
    """
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
        "capabilities": {
            "tools": {
                "list": True,
                "call": True,
            }
        },
    }


def tools_list_response() -> dict[str, Any]:
    """Return the full list of registered MCP tool definitions.

    Wraps ``TOOL_DEFINITIONS`` in the ``{"tools": [...]}`` envelope expected
    by the MCP ``tools/list`` response.  Each entry includes the tool name,
    description, JSON Schema input spec, and ``x-metadata`` with safety class
    and minimum RBAC role.

    Returns:
        ``{"tools": [<tool_definition>, ...]}``
    """
    return {"tools": TOOL_DEFINITIONS}


@mcp.tool(name="list_resource_groups", description=TOOL_DEFINITIONS[0]["description"])
def list_resource_groups_tool(limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_resource_groups(limit=limit)


@mcp.tool(name="list_virtual_machines", description=TOOL_DEFINITIONS[1]["description"])
def list_virtual_machines_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_virtual_machines(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_storage_accounts", description=TOOL_DEFINITIONS[2]["description"])
def list_storage_accounts_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_storage_accounts(resource_group=resource_group, limit=limit)


@mcp.tool(name="get_virtual_machine_status", description=TOOL_DEFINITIONS[3]["description"])
def get_virtual_machine_status_tool(resource_group: str, vm_name: str) -> dict[str, Any]:
    set_correlation_id()
    return get_virtual_machine_status(resource_group=resource_group, vm_name=vm_name)


@mcp.tool(name="start_virtual_machine", description=TOOL_DEFINITIONS[4]["description"])
def start_virtual_machine_tool(
    resource_group: str,
    vm_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return start_virtual_machine(
        resource_group=resource_group,
        vm_name=vm_name,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="stop_virtual_machine", description=TOOL_DEFINITIONS[5]["description"])
def stop_virtual_machine_tool(
    resource_group: str,
    vm_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return stop_virtual_machine(
        resource_group=resource_group,
        vm_name=vm_name,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="create_storage_account", description=TOOL_DEFINITIONS[6]["description"])
def create_storage_account_tool(
    resource_group: str,
    account_name: str,
    location: str | None = None,
    sku_name: str = "Standard_LRS",
    kind: str = "StorageV2",
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return create_storage_account(
        resource_group=resource_group,
        account_name=account_name,
        location=location,
        sku_name=sku_name,
        kind=kind,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="upload_blob_content", description=TOOL_DEFINITIONS[7]["description"])
def upload_blob_content_tool(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    content_base64: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return upload_blob_content(
        resource_group=resource_group,
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        content_base64=content_base64,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="download_blob_content", description=TOOL_DEFINITIONS[8]["description"])
def download_blob_content_tool(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return download_blob_content(
        resource_group=resource_group,
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="list_virtual_networks", description=TOOL_DEFINITIONS[9]["description"])
def list_virtual_networks_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_virtual_networks(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_network_security_groups", description=TOOL_DEFINITIONS[10]["description"])
def list_network_security_groups_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_network_security_groups(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_public_ip_addresses", description=TOOL_DEFINITIONS[11]["description"])
def list_public_ip_addresses_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_public_ip_addresses(resource_group=resource_group, limit=limit)


@mcp.tool(name="create_public_ip_address", description=TOOL_DEFINITIONS[12]["description"])
def create_public_ip_address_tool(
    resource_group: str,
    public_ip_name: str,
    location: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return create_public_ip_address(
        resource_group=resource_group,
        public_ip_name=public_ip_name,
        location=location,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="list_key_vaults", description=TOOL_DEFINITIONS[13]["description"])
def list_key_vaults_tool(resource_group: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_key_vaults(resource_group=resource_group, limit=limit)


@mcp.tool(name="query_log_analytics", description=TOOL_DEFINITIONS[14]["description"])
def query_log_analytics_tool(
    workspace_id: str,
    query: str,
    timespan_hours: int = 24,
    limit: int = 100,
) -> dict[str, Any]:
    set_correlation_id()
    return query_log_analytics(
        workspace_id=workspace_id,
        query=query,
        timespan_hours=timespan_hours,
        limit=limit,
    )


@mcp.tool(name="get_resource_metrics", description=TOOL_DEFINITIONS[15]["description"])
def get_resource_metrics_tool(
    resource_id: str,
    metric_names: list[str],
    timespan_hours: int = 1,
    interval_minutes: int = 5,
    limit: int = 200,
) -> dict[str, Any]:
    set_correlation_id()
    return get_resource_metrics(
        resource_id=resource_id,
        metric_names=metric_names,
        timespan_hours=timespan_hours,
        interval_minutes=interval_minutes,
        limit=limit,
    )


@mcp.tool(name="get_cost_summary", description=TOOL_DEFINITIONS[16]["description"])
def get_cost_summary_tool(scope: str, days: int = 30) -> dict[str, Any]:
    set_correlation_id()
    return get_cost_summary(scope=scope, days=days)


@mcp.tool(name="list_advisor_recommendations", description=TOOL_DEFINITIONS[17]["description"])
def list_advisor_recommendations_tool(
    resource_group: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    set_correlation_id()
    return list_advisor_recommendations(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_openai_deployments", description=TOOL_DEFINITIONS[18]["description"])
def list_openai_deployments_tool(
    resource_group: str,
    account_name: str,
    limit: int = 50,
) -> dict[str, Any]:
    set_correlation_id()
    return list_openai_deployments(resource_group=resource_group, account_name=account_name, limit=limit)


@mcp.tool(name="deploy_openai_model", description=TOOL_DEFINITIONS[19]["description"])
def deploy_openai_model_tool(
    resource_group: str,
    account_name: str,
    deployment_name: str,
    model_name: str,
    model_version: str,
    sku_name: str = "GlobalStandard",
    capacity: int = 1,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return deploy_openai_model(
        resource_group=resource_group,
        account_name=account_name,
        deployment_name=deployment_name,
        model_name=model_name,
        model_version=model_version,
        sku_name=sku_name,
        capacity=capacity,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="list_ai_foundry_agents", description=TOOL_DEFINITIONS[20]["description"])
def list_ai_foundry_agents_tool(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    set_correlation_id()
    return list_ai_foundry_agents(project_endpoint=project_endpoint, limit=limit)


@mcp.tool(name="create_ai_foundry_agent", description=TOOL_DEFINITIONS[21]["description"])
def create_ai_foundry_agent_tool(
    project_endpoint: str,
    agent_name: str,
    instructions: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return create_ai_foundry_agent(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        instructions=instructions,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="delete_ai_foundry_agent", description=TOOL_DEFINITIONS[22]["description"])
def delete_ai_foundry_agent_tool(
    project_endpoint: str,
    agent_id: str,
    has_explicit_approval: bool = False,
) -> dict[str, Any]:
    set_correlation_id()
    return delete_ai_foundry_agent(
        project_endpoint=project_endpoint,
        agent_id=agent_id,
        has_explicit_approval=has_explicit_approval,
    )


@mcp.tool(name="diagnose_virtual_machine", description=TOOL_DEFINITIONS[23]["description"])
def diagnose_virtual_machine_tool(
    resource_group: str,
    vm_name: str,
    resource_id: str | None = None,
    workspace_id: str | None = None,
    metric_names: list[str] | None = None,
    timespan_hours: int = 1,
) -> dict[str, Any]:
    set_correlation_id()
    return diagnose_virtual_machine(
        resource_group=resource_group,
        vm_name=vm_name,
        resource_id=resource_id,
        workspace_id=workspace_id,
        metric_names=metric_names,
        timespan_hours=timespan_hours,
    )


def create_http_app() -> FastAPI:
    """Assemble and return the FastAPI application with health and MCP endpoints.

    Registers a ``GET /health`` endpoint that returns ``{"status": "ok"}`` when
    settings load successfully or ``{"status": "degraded"}`` on ``ConfigError``.
    Mounts the FastMCP streamable-HTTP transport at ``/mcp`` when the
    ``streamable_http_app`` factory is available on the ``mcp`` instance.

    Returns:
        A configured ``FastAPI`` application instance.
    """
    app = FastAPI(title=SERVER_NAME)

    @app.get("/health")
    def health() -> dict[str, str]:
        try:
            load_settings()
            return {"status": "ok"}
        except ConfigError:
            return {"status": "degraded"}

    streamable_http_factory = getattr(mcp, "streamable_http_app", None)
    if callable(streamable_http_factory):
        app.mount("/mcp", streamable_http_factory())

    return app


http_app = create_http_app()
app = http_app


def run() -> None:
    """Configure logging and start the MCP server over streamable HTTP.

    Loads settings to determine the log level, configures the root logger via
    ``configure_logging``, then starts the FastMCP server bound to all
    interfaces on port 8000 using the ``streamable-http`` transport.

    This function is the entry point when the module is run directly
    (``python -m src.app``).
    """
    settings = load_settings()
    configure_logging(settings.log_level)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
