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
    plan_virtual_machine_power_action,
    start_virtual_machine,
    stop_virtual_machine,
)
from .tools.resource_mgmt import (
    create_azure_resource,
    delete_azure_resource,
    get_azure_resource,
    list_azure_resource_providers,
    list_azure_resources,
    plan_azure_resource_mutation,
    list_resource_groups,
    update_azure_resource,
)
from .tools.resource_graph import query_azure_resource_graph
from .tools.deployments import get_arm_deployment_operation_status, preview_arm_template_deployment
from .tools.storage import (
    create_storage_account,
    download_blob_content,
    list_storage_accounts,
    plan_storage_mutation,
    upload_blob_content,
)
from .tools.keyvault import list_key_vaults
from .tools.monitoring import get_resource_metrics, query_log_analytics
from .tools.cost import get_cost_summary, list_advisor_recommendations
from .tools.ai import (
    create_ai_foundry_agent,
    delete_ai_foundry_agent,
    deploy_openai_model,
    get_ai_foundry_agent,
    list_ai_foundry_agents,
    list_openai_deployments,
    plan_ai_foundry_agent_mutation,
    plan_openai_deployment,
    update_ai_foundry_agent,
)
from .tools.diagnostics import diagnose_virtual_machine
from .tools.advanced import (
    list_aks_clusters,
    list_cosmos_accounts,
    list_function_apps,
    query_function_app_logs,
    list_ml_jobs,
    list_ml_models,
    list_ml_workspaces,
    list_sql_databases,
    query_cosmos_items,
)
from .tools.network import (
    create_public_ip_address,
    list_network_security_groups,
    list_public_ip_addresses,
    list_virtual_networks,
    plan_public_ip_creation,
)

SERVER_NAME = "Azure Cloud Intelligence MCP"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"

mcp = FastMCP(SERVER_NAME)

RG_TOOL_METADATA = get_tool_metadata("list_resource_groups")
LIST_RESOURCES_TOOL_METADATA = get_tool_metadata("list_azure_resources")
RESOURCE_GRAPH_TOOL_METADATA = get_tool_metadata("query_azure_resource_graph")
WHAT_IF_TOOL_METADATA = get_tool_metadata("preview_arm_template_deployment")
DEPLOYMENT_OPERATION_TOOL_METADATA = get_tool_metadata("get_arm_deployment_operation_status")
LIST_PROVIDERS_TOOL_METADATA = get_tool_metadata("list_azure_resource_providers")
GET_RESOURCE_TOOL_METADATA = get_tool_metadata("get_azure_resource")
CREATE_RESOURCE_TOOL_METADATA = get_tool_metadata("create_azure_resource")
PLAN_RESOURCE_MUTATION_TOOL_METADATA = get_tool_metadata("plan_azure_resource_mutation")
UPDATE_RESOURCE_TOOL_METADATA = get_tool_metadata("update_azure_resource")
DELETE_RESOURCE_TOOL_METADATA = get_tool_metadata("delete_azure_resource")
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
FOUNDRY_PLAN_TOOL_METADATA = get_tool_metadata("plan_ai_foundry_agent_mutation")
FOUNDRY_GET_TOOL_METADATA = get_tool_metadata("get_ai_foundry_agent")
FOUNDRY_CREATE_TOOL_METADATA = get_tool_metadata("create_ai_foundry_agent")
FOUNDRY_DELETE_TOOL_METADATA = get_tool_metadata("delete_ai_foundry_agent")
FOUNDRY_UPDATE_TOOL_METADATA = get_tool_metadata("update_ai_foundry_agent")
DIAGNOSTIC_TOOL_METADATA = get_tool_metadata("diagnose_virtual_machine")
AKS_TOOL_METADATA = get_tool_metadata("list_aks_clusters")
FUNCTION_APPS_TOOL_METADATA = get_tool_metadata("list_function_apps")
FUNCTION_LOGS_TOOL_METADATA = get_tool_metadata("query_function_app_logs")
SQL_DATABASES_TOOL_METADATA = get_tool_metadata("list_sql_databases")
COSMOS_ACCOUNTS_TOOL_METADATA = get_tool_metadata("list_cosmos_accounts")
COSMOS_QUERY_TOOL_METADATA = get_tool_metadata("query_cosmos_items")
ML_WORKSPACES_TOOL_METADATA = get_tool_metadata("list_ml_workspaces")
ML_MODELS_TOOL_METADATA = get_tool_metadata("list_ml_models")
ML_JOBS_TOOL_METADATA = get_tool_metadata("list_ml_jobs")


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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "approval_id": {"type": "string", "minLength": 1},
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
                "model": {"type": "string", "minLength": 1, "maxLength": 128},
                "approval_id": {"type": "string", "minLength": 1},
            },
            "required": ["project_endpoint", "agent_name", "instructions", "model", "approval_id"],
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
                "approval_id": {"type": "string", "minLength": 1},
            },
            "required": ["project_endpoint", "agent_id", "approval_id"],
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
    {
        "name": AKS_TOOL_METADATA.name,
        "description": AKS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": AKS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": AKS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FUNCTION_APPS_TOOL_METADATA.name,
        "description": FUNCTION_APPS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": FUNCTION_APPS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FUNCTION_APPS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FUNCTION_LOGS_TOOL_METADATA.name,
        "description": FUNCTION_LOGS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "minLength": 1},
                "function_app_name": {"type": "string", "minLength": 1, "maxLength": 60},
                "timespan_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["workspace_id", "function_app_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": FUNCTION_LOGS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FUNCTION_LOGS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": SQL_DATABASES_TOOL_METADATA.name,
        "description": SQL_DATABASES_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "server_name": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "required": ["resource_group", "server_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": SQL_DATABASES_TOOL_METADATA.safety_class.value, "minimum_rbac_role": SQL_DATABASES_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": COSMOS_ACCOUNTS_TOOL_METADATA.name,
        "description": COSMOS_ACCOUNTS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": COSMOS_ACCOUNTS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": COSMOS_ACCOUNTS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": COSMOS_QUERY_TOOL_METADATA.name,
        "description": COSMOS_QUERY_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_name": {"type": "string", "minLength": 1},
                "database_name": {"type": "string", "minLength": 1},
                "container_name": {"type": "string", "minLength": 1},
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["account_name", "database_name", "container_name", "query"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": COSMOS_QUERY_TOOL_METADATA.safety_class.value, "minimum_rbac_role": COSMOS_QUERY_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": ML_WORKSPACES_TOOL_METADATA.name,
        "description": ML_WORKSPACES_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": ML_WORKSPACES_TOOL_METADATA.safety_class.value, "minimum_rbac_role": ML_WORKSPACES_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": ML_MODELS_TOOL_METADATA.name,
        "description": ML_MODELS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"workspace_name": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "required": ["workspace_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": ML_MODELS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": ML_MODELS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": ML_JOBS_TOOL_METADATA.name,
        "description": ML_JOBS_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"workspace_name": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "required": ["workspace_name"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": ML_JOBS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": ML_JOBS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": GET_RESOURCE_TOOL_METADATA.name,
        "description": GET_RESOURCE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_id": {"type": "string", "minLength": 1}, "api_version": {"type": "string", "minLength": 1, "maxLength": 32}},
            "required": ["resource_id", "api_version"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": GET_RESOURCE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": GET_RESOURCE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": CREATE_RESOURCE_TOOL_METADATA.name,
        "description": CREATE_RESOURCE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_id": {"type": "string", "minLength": 1}, "api_version": {"type": "string", "minLength": 1, "maxLength": 32}, "payload": {"type": "object"}, "approval_id": {"type": "string", "minLength": 1}},
            "required": ["resource_id", "api_version", "payload", "approval_id"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": CREATE_RESOURCE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": CREATE_RESOURCE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": UPDATE_RESOURCE_TOOL_METADATA.name,
        "description": UPDATE_RESOURCE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_id": {"type": "string", "minLength": 1}, "api_version": {"type": "string", "minLength": 1, "maxLength": 32}, "payload": {"type": "object"}, "approval_id": {"type": "string", "minLength": 1}},
            "required": ["resource_id", "api_version", "payload", "approval_id"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": UPDATE_RESOURCE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": UPDATE_RESOURCE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": DELETE_RESOURCE_TOOL_METADATA.name,
        "description": DELETE_RESOURCE_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_id": {"type": "string", "minLength": 1}, "api_version": {"type": "string", "minLength": 1, "maxLength": 32}, "approval_id": {"type": "string", "minLength": 1}},
            "required": ["resource_id", "api_version", "approval_id"],
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": DELETE_RESOURCE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": DELETE_RESOURCE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": LIST_RESOURCES_TOOL_METADATA.name,
        "description": LIST_RESOURCES_TOOL_METADATA.description,
        "inputSchema": {
            "type": "object",
            "properties": {"resource_group": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        "x-metadata": {"safety_class": LIST_RESOURCES_TOOL_METADATA.safety_class.value, "minimum_rbac_role": LIST_RESOURCES_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": LIST_PROVIDERS_TOOL_METADATA.name,
        "description": LIST_PROVIDERS_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "x-metadata": {"safety_class": LIST_PROVIDERS_TOOL_METADATA.safety_class.value, "minimum_rbac_role": LIST_PROVIDERS_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": RESOURCE_GRAPH_TOOL_METADATA.name,
        "description": RESOURCE_GRAPH_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 2000}, "subscriptions": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "string", "minLength": 1}}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}, "required": ["query", "subscriptions"], "additionalProperties": False},
        "x-metadata": {"safety_class": RESOURCE_GRAPH_TOOL_METADATA.safety_class.value, "minimum_rbac_role": RESOURCE_GRAPH_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": WHAT_IF_TOOL_METADATA.name,
        "description": WHAT_IF_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"resource_group": {"type": "string", "minLength": 1}, "deployment_name": {"type": "string", "minLength": 1}, "template": {"type": "object"}, "parameters": {"type": "object"}}, "required": ["resource_group", "deployment_name", "template"], "additionalProperties": False},
        "x-metadata": {"safety_class": WHAT_IF_TOOL_METADATA.safety_class.value, "minimum_rbac_role": WHAT_IF_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": PLAN_RESOURCE_MUTATION_TOOL_METADATA.name,
        "description": PLAN_RESOURCE_MUTATION_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"operation": {"type": "string", "enum": ["create", "update", "delete"]}, "resource_id": {"type": "string", "minLength": 1}, "api_version": {"type": "string", "minLength": 1}, "payload": {"type": "object"}}, "required": ["operation", "resource_id", "api_version"], "additionalProperties": False},
        "x-metadata": {"safety_class": PLAN_RESOURCE_MUTATION_TOOL_METADATA.safety_class.value, "minimum_rbac_role": PLAN_RESOURCE_MUTATION_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": DEPLOYMENT_OPERATION_TOOL_METADATA.name,
        "description": DEPLOYMENT_OPERATION_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"resource_group": {"type": "string", "minLength": 1}, "deployment_name": {"type": "string", "minLength": 1}, "operation_id": {"type": "string", "minLength": 1}}, "required": ["resource_group", "deployment_name", "operation_id"], "additionalProperties": False},
        "x-metadata": {"safety_class": DEPLOYMENT_OPERATION_TOOL_METADATA.safety_class.value, "minimum_rbac_role": DEPLOYMENT_OPERATION_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_PLAN_TOOL_METADATA.name,
        "description": FOUNDRY_PLAN_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"operation": {"type": "string", "enum": ["create", "update", "delete"]}, "project_endpoint": {"type": "string", "minLength": 1}, "agent_id": {"type": "string", "minLength": 1}, "agent_name": {"type": "string", "minLength": 1}, "instructions": {"type": "string", "minLength": 1}, "model": {"type": "string", "minLength": 1}}, "required": ["operation", "project_endpoint"], "additionalProperties": False},
        "x-metadata": {"safety_class": FOUNDRY_PLAN_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_PLAN_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_GET_TOOL_METADATA.name,
        "description": FOUNDRY_GET_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"project_endpoint": {"type": "string", "minLength": 1}, "agent_id": {"type": "string", "minLength": 1}}, "required": ["project_endpoint", "agent_id"], "additionalProperties": False},
        "x-metadata": {"safety_class": FOUNDRY_GET_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_GET_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": FOUNDRY_UPDATE_TOOL_METADATA.name,
        "description": FOUNDRY_UPDATE_TOOL_METADATA.description,
        "inputSchema": {"type": "object", "properties": {"project_endpoint": {"type": "string", "minLength": 1}, "agent_id": {"type": "string", "minLength": 1}, "instructions": {"type": "string", "minLength": 1, "maxLength": 4000}, "model": {"type": "string", "minLength": 1, "maxLength": 128}, "approval_id": {"type": "string", "minLength": 1}}, "required": ["project_endpoint", "agent_id", "approval_id"], "additionalProperties": False},
        "x-metadata": {"safety_class": FOUNDRY_UPDATE_TOOL_METADATA.safety_class.value, "minimum_rbac_role": FOUNDRY_UPDATE_TOOL_METADATA.minimum_rbac_role},
    },
    {
        "name": "plan_virtual_machine_power_action",
        "description": "Plan a VM start or stop and issue a single-use approval receipt.",
        "inputSchema": {"type": "object", "properties": {"resource_group": {"type": "string", "minLength": 1}, "vm_name": {"type": "string", "minLength": 1}, "action": {"type": "string", "enum": ["start", "stop"]}}, "required": ["resource_group", "vm_name", "action"], "additionalProperties": False},
        "x-metadata": {"safety_class": "read_only", "minimum_rbac_role": "Reader"},
    },
    {
        "name": "plan_storage_mutation",
        "description": "Plan a storage mutation or sensitive blob download and issue an approval receipt.",
        "inputSchema": {"type": "object", "properties": {"operation": {"type": "string", "enum": ["create_storage_account", "upload_blob_content", "download_blob_content"]}, "resource_group": {"type": "string", "minLength": 1}, "account_name": {"type": "string", "minLength": 1}, "container_name": {"type": "string"}, "blob_name": {"type": "string"}, "content_base64": {"type": "string"}, "location": {"type": "string"}, "sku_name": {"type": "string"}, "kind": {"type": "string"}}, "required": ["operation", "resource_group", "account_name"], "additionalProperties": False},
        "x-metadata": {"safety_class": "read_only", "minimum_rbac_role": "Reader"},
    },
    {
        "name": "plan_public_ip_creation",
        "description": "Plan a static Standard public IP and issue a single-use approval receipt.",
        "inputSchema": {"type": "object", "properties": {"resource_group": {"type": "string", "minLength": 1}, "public_ip_name": {"type": "string", "minLength": 1}, "location": {"type": "string", "minLength": 1}}, "required": ["resource_group", "public_ip_name", "location"], "additionalProperties": False},
        "x-metadata": {"safety_class": "read_only", "minimum_rbac_role": "Reader"},
    },
    {
        "name": "plan_openai_deployment",
        "description": "Plan an Azure OpenAI deployment and issue a single-use approval receipt.",
        "inputSchema": {"type": "object", "properties": {"resource_group": {"type": "string", "minLength": 1}, "account_name": {"type": "string", "minLength": 1}, "deployment_name": {"type": "string", "minLength": 1}, "model_name": {"type": "string", "minLength": 1}, "model_version": {"type": "string", "minLength": 1}, "sku_name": {"type": "string"}, "capacity": {"type": "integer", "minimum": 1}}, "required": ["resource_group", "account_name", "deployment_name", "model_name", "model_version"], "additionalProperties": False},
        "x-metadata": {"safety_class": "read_only", "minimum_rbac_role": "Reader"},
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


@mcp.tool(name="plan_virtual_machine_power_action", description="Plan a start or stop operation and issue a one-time approval receipt.")
def plan_virtual_machine_power_action_tool(resource_group: str, vm_name: str, action: str) -> dict[str, Any]:
    set_correlation_id()
    return plan_virtual_machine_power_action(resource_group, vm_name, action)


@mcp.tool(name="plan_storage_mutation", description="Plan a storage account mutation, blob upload, or sensitive blob download.")
def plan_storage_mutation_tool(operation: str, resource_group: str, account_name: str, container_name: str | None = None, blob_name: str | None = None, content_base64: str | None = None, location: str | None = None, sku_name: str = "Standard_LRS", kind: str = "StorageV2") -> dict[str, Any]:
    set_correlation_id()
    return plan_storage_mutation(operation, resource_group, account_name, container_name, blob_name, content_base64, location, sku_name, kind)


@mcp.tool(name="plan_public_ip_creation", description="Plan static public IP creation and issue a one-time approval receipt.")
def plan_public_ip_creation_tool(resource_group: str, public_ip_name: str, location: str) -> dict[str, Any]:
    set_correlation_id()
    return plan_public_ip_creation(resource_group, public_ip_name, location)


@mcp.tool(name="plan_openai_deployment", description="Plan an Azure OpenAI deployment and issue a one-time approval receipt.")
def plan_openai_deployment_tool(resource_group: str, account_name: str, deployment_name: str, model_name: str, model_version: str, sku_name: str = "GlobalStandard", capacity: int = 1) -> dict[str, Any]:
    set_correlation_id()
    return plan_openai_deployment(resource_group, account_name, deployment_name, model_name, model_version, sku_name, capacity)


@mcp.tool(name="start_virtual_machine", description=TOOL_DEFINITIONS[4]["description"])
def start_virtual_machine_tool(
    resource_group: str,
    vm_name: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return start_virtual_machine(
        resource_group=resource_group,
        vm_name=vm_name,
        approval_id=approval_id,
    )


@mcp.tool(name="stop_virtual_machine", description=TOOL_DEFINITIONS[5]["description"])
def stop_virtual_machine_tool(
    resource_group: str,
    vm_name: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return stop_virtual_machine(
        resource_group=resource_group,
        vm_name=vm_name,
        approval_id=approval_id,
    )


@mcp.tool(name="create_storage_account", description=TOOL_DEFINITIONS[6]["description"])
def create_storage_account_tool(
    resource_group: str,
    account_name: str,
    location: str | None = None,
    sku_name: str = "Standard_LRS",
    kind: str = "StorageV2",
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return create_storage_account(
        resource_group=resource_group,
        account_name=account_name,
        location=location,
        sku_name=sku_name,
        kind=kind,
        approval_id=approval_id,
    )


@mcp.tool(name="upload_blob_content", description=TOOL_DEFINITIONS[7]["description"])
def upload_blob_content_tool(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    content_base64: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return upload_blob_content(
        resource_group=resource_group,
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        content_base64=content_base64,
        approval_id=approval_id,
    )


@mcp.tool(name="download_blob_content", description=TOOL_DEFINITIONS[8]["description"])
def download_blob_content_tool(
    resource_group: str,
    account_name: str,
    container_name: str,
    blob_name: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return download_blob_content(
        resource_group=resource_group,
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        approval_id=approval_id,
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
    approval_id: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return create_public_ip_address(
        resource_group=resource_group,
        public_ip_name=public_ip_name,
        location=location,
        approval_id=approval_id,
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
    approval_id: str | None = None,
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
        approval_id=approval_id,
    )


@mcp.tool(name="list_ai_foundry_agents", description=TOOL_DEFINITIONS[20]["description"])
def list_ai_foundry_agents_tool(project_endpoint: str, limit: int = 50) -> dict[str, Any]:
    set_correlation_id()
    return list_ai_foundry_agents(project_endpoint=project_endpoint, limit=limit)


@mcp.tool(name="plan_ai_foundry_agent_mutation", description=FOUNDRY_PLAN_TOOL_METADATA.description)
def plan_ai_foundry_agent_mutation_tool(operation: str, project_endpoint: str, agent_id: str | None = None, agent_name: str | None = None, instructions: str | None = None, model: str | None = None) -> dict[str, Any]:
    set_correlation_id()
    return plan_ai_foundry_agent_mutation(operation, project_endpoint, agent_id, agent_name, instructions, model)


@mcp.tool(name="create_ai_foundry_agent", description=TOOL_DEFINITIONS[21]["description"])
def create_ai_foundry_agent_tool(
    project_endpoint: str,
    agent_name: str,
    instructions: str,
    model: str,
    approval_id: str,
) -> dict[str, Any]:
    set_correlation_id()
    return create_ai_foundry_agent(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        instructions=instructions,
        model=model,
        approval_id=approval_id,
    )


@mcp.tool(name="delete_ai_foundry_agent", description=TOOL_DEFINITIONS[22]["description"])
def delete_ai_foundry_agent_tool(
    project_endpoint: str,
    agent_id: str,
    approval_id: str,
) -> dict[str, Any]:
    set_correlation_id()
    return delete_ai_foundry_agent(
        project_endpoint=project_endpoint,
        agent_id=agent_id,
        approval_id=approval_id,
    )


@mcp.tool(name="get_ai_foundry_agent", description=FOUNDRY_GET_TOOL_METADATA.description)
def get_ai_foundry_agent_tool(project_endpoint: str, agent_id: str) -> dict[str, Any]:
    set_correlation_id()
    return get_ai_foundry_agent(project_endpoint=project_endpoint, agent_id=agent_id)


@mcp.tool(name="update_ai_foundry_agent", description=FOUNDRY_UPDATE_TOOL_METADATA.description)
def update_ai_foundry_agent_tool(
    project_endpoint: str,
    agent_id: str,
    approval_id: str,
    instructions: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    set_correlation_id()
    return update_ai_foundry_agent(project_endpoint, agent_id, instructions, model, approval_id)


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


@mcp.tool(name="list_aks_clusters", description=TOOL_DEFINITIONS[24]["description"])
def list_aks_clusters_tool(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_aks_clusters(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_function_apps", description=TOOL_DEFINITIONS[25]["description"])
def list_function_apps_tool(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_function_apps(resource_group=resource_group, limit=limit)


@mcp.tool(name="query_function_app_logs", description=TOOL_DEFINITIONS[26]["description"])
def query_function_app_logs_tool(
    workspace_id: str,
    function_app_name: str,
    timespan_hours: int = 24,
    limit: int = 100,
) -> dict[str, Any]:
    set_correlation_id()
    return query_function_app_logs(
        workspace_id=workspace_id,
        function_app_name=function_app_name,
        timespan_hours=timespan_hours,
        limit=limit,
    )


@mcp.tool(name="list_sql_databases", description=TOOL_DEFINITIONS[27]["description"])
def list_sql_databases_tool(resource_group: str, server_name: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_sql_databases(resource_group=resource_group, server_name=server_name, limit=limit)


@mcp.tool(name="list_cosmos_accounts", description=TOOL_DEFINITIONS[28]["description"])
def list_cosmos_accounts_tool(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_cosmos_accounts(resource_group=resource_group, limit=limit)


@mcp.tool(name="query_cosmos_items", description=TOOL_DEFINITIONS[29]["description"])
def query_cosmos_items_tool(
    account_name: str,
    database_name: str,
    container_name: str,
    query: str,
    limit: int = 100,
) -> dict[str, Any]:
    set_correlation_id()
    return query_cosmos_items(
        account_name=account_name,
        database_name=database_name,
        container_name=container_name,
        query=query,
        limit=limit,
    )


@mcp.tool(name="list_ml_workspaces", description=TOOL_DEFINITIONS[30]["description"])
def list_ml_workspaces_tool(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_ml_workspaces(resource_group=resource_group, limit=limit)


@mcp.tool(name="list_ml_models", description=TOOL_DEFINITIONS[31]["description"])
def list_ml_models_tool(workspace_name: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_ml_models(workspace_name=workspace_name, limit=limit)


@mcp.tool(name="list_ml_jobs", description=TOOL_DEFINITIONS[32]["description"])
def list_ml_jobs_tool(workspace_name: str, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_ml_jobs(workspace_name=workspace_name, limit=limit)


@mcp.tool(name="get_azure_resource", description=TOOL_DEFINITIONS[33]["description"])
def get_azure_resource_tool(resource_id: str, api_version: str) -> dict[str, Any]:
    set_correlation_id()
    return get_azure_resource(resource_id=resource_id, api_version=api_version)


@mcp.tool(name="plan_azure_resource_mutation", description=PLAN_RESOURCE_MUTATION_TOOL_METADATA.description)
def plan_azure_resource_mutation_tool(operation: str, resource_id: str, api_version: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    set_correlation_id()
    return plan_azure_resource_mutation(operation, resource_id, api_version, payload)


@mcp.tool(name="create_azure_resource", description=TOOL_DEFINITIONS[34]["description"])
def create_azure_resource_tool(
    resource_id: str,
    api_version: str,
    payload: dict[str, Any],
    approval_id: str,
) -> dict[str, Any]:
    set_correlation_id()
    return create_azure_resource(
        resource_id=resource_id,
        api_version=api_version,
        payload=payload,
        approval_id=approval_id,
    )


@mcp.tool(name="update_azure_resource", description=TOOL_DEFINITIONS[35]["description"])
def update_azure_resource_tool(
    resource_id: str,
    api_version: str,
    payload: dict[str, Any],
    approval_id: str,
) -> dict[str, Any]:
    set_correlation_id()
    return update_azure_resource(
        resource_id=resource_id,
        api_version=api_version,
        payload=payload,
        approval_id=approval_id,
    )


@mcp.tool(name="delete_azure_resource", description=TOOL_DEFINITIONS[36]["description"])
def delete_azure_resource_tool(
    resource_id: str,
    api_version: str,
    approval_id: str,
) -> dict[str, Any]:
    set_correlation_id()
    return delete_azure_resource(
        resource_id=resource_id,
        api_version=api_version,
        approval_id=approval_id,
    )


@mcp.tool(name="list_azure_resources", description=TOOL_DEFINITIONS[37]["description"])
def list_azure_resources_tool(resource_group: str | None = None, limit: int | None = None) -> dict[str, Any]:
    set_correlation_id()
    return list_azure_resources(resource_group=resource_group, limit=limit)


@mcp.tool(name="query_azure_resource_graph", description=RESOURCE_GRAPH_TOOL_METADATA.description)
def query_azure_resource_graph_tool(query: str, subscriptions: list[str], limit: int = 100) -> dict[str, Any]:
    set_correlation_id()
    return query_azure_resource_graph(query=query, subscriptions=subscriptions, limit=limit)


@mcp.tool(name="preview_arm_template_deployment", description=WHAT_IF_TOOL_METADATA.description)
def preview_arm_template_deployment_tool(resource_group: str, deployment_name: str, template: dict[str, Any], parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    set_correlation_id()
    return preview_arm_template_deployment(resource_group, deployment_name, template, parameters)


@mcp.tool(name="get_arm_deployment_operation_status", description=DEPLOYMENT_OPERATION_TOOL_METADATA.description)
def get_arm_deployment_operation_status_tool(resource_group: str, deployment_name: str, operation_id: str) -> dict[str, Any]:
    set_correlation_id()
    return get_arm_deployment_operation_status(resource_group, deployment_name, operation_id)


@mcp.tool(name="list_azure_resource_providers", description=TOOL_DEFINITIONS[38]["description"])
def list_azure_resource_providers_tool() -> dict[str, Any]:
    set_correlation_id()
    return list_azure_resource_providers()


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
