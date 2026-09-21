from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SafetyClass(str, Enum):
    READ_ONLY = "read_only"
    CONTROLLED_ACTION = "controlled_action"
    SENSITIVE_DATA = "sensitive_data"


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    safety_class: SafetyClass
    minimum_rbac_role: str
    owner_module: str
    docs_reference: str


TOOL_REGISTRY: dict[str, ToolMetadata] = {
    "list_resource_groups": ToolMetadata(
        name="list_resource_groups",
        description="List Azure resource groups in the current subscription.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/security-rbac.md",
    ),
    "list_virtual_machines": ToolMetadata(
        name="list_virtual_machines",
        description="List virtual machines in the specified resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader (or Virtual Machine Contributor)",
        owner_module="src.tools.compute",
        docs_reference="docs/security-rbac.md",
    ),
    "get_virtual_machine_status": ToolMetadata(
        name="get_virtual_machine_status",
        description="Get power and instance status for a virtual machine.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader (or Virtual Machine Contributor)",
        owner_module="src.tools.compute",
        docs_reference="docs/security-rbac.md",
    ),
    "start_virtual_machine": ToolMetadata(
        name="start_virtual_machine",
        description="Start a virtual machine (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Virtual Machine Contributor",
        owner_module="src.tools.compute",
        docs_reference="docs/security-rbac.md",
    ),
    "stop_virtual_machine": ToolMetadata(
        name="stop_virtual_machine",
        description="Stop a virtual machine (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Virtual Machine Contributor",
        owner_module="src.tools.compute",
        docs_reference="docs/security-rbac.md",
    ),
    "list_storage_accounts": ToolMetadata(
        name="list_storage_accounts",
        description="List storage accounts in the specified resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader (or Storage Account Contributor)",
        owner_module="src.tools.storage",
        docs_reference="docs/security-rbac.md",
    ),
    "create_storage_account": ToolMetadata(
        name="create_storage_account",
        description="Create a storage account (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Storage Account Contributor",
        owner_module="src.tools.storage",
        docs_reference="docs/security-rbac.md",
    ),
    "upload_blob_content": ToolMetadata(
        name="upload_blob_content",
        description="Upload blob content from base64 bytes (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Storage Blob Data Contributor",
        owner_module="src.tools.storage",
        docs_reference="docs/security-rbac.md",
    ),
    "download_blob_content": ToolMetadata(
        name="download_blob_content",
        description="Download blob content as base64 bytes (sensitive data).",
        safety_class=SafetyClass.SENSITIVE_DATA,
        minimum_rbac_role="Storage Blob Data Reader",
        owner_module="src.tools.storage",
        docs_reference="docs/security-rbac.md",
    ),
    "list_virtual_networks": ToolMetadata(
        name="list_virtual_networks",
        description="List virtual network metadata in the specified resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.network",
        docs_reference="docs/security-rbac.md",
    ),
    "list_network_security_groups": ToolMetadata(
        name="list_network_security_groups",
        description="List network security group metadata in the specified resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.network",
        docs_reference="docs/security-rbac.md",
    ),
    "list_public_ip_addresses": ToolMetadata(
        name="list_public_ip_addresses",
        description="List public IP metadata in the specified resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.network",
        docs_reference="docs/security-rbac.md",
    ),
    "create_public_ip_address": ToolMetadata(
        name="create_public_ip_address",
        description="Create a static public IP address (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Network Contributor",
        owner_module="src.tools.network",
        docs_reference="docs/security-rbac.md",
    ),
    "list_key_vaults": ToolMetadata(
        name="list_key_vaults",
        description="List Key Vault metadata without returning secret values.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.keyvault",
        docs_reference="docs/security-rbac.md",
    ),
    "query_log_analytics": ToolMetadata(
        name="query_log_analytics",
        description="Run one bounded read-only Log Analytics query.",
        safety_class=SafetyClass.SENSITIVE_DATA,
        minimum_rbac_role="Log Analytics Reader",
        owner_module="src.tools.monitoring",
        docs_reference="docs/security-rbac.md",
    ),
    "get_resource_metrics": ToolMetadata(
        name="get_resource_metrics",
        description="Read bounded metrics for one Azure resource.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Monitoring Reader",
        owner_module="src.tools.monitoring",
        docs_reference="docs/security-rbac.md",
    ),
    "get_cost_summary": ToolMetadata(
        name="get_cost_summary",
        description="Return a bounded cost summary for an Azure scope.",
        safety_class=SafetyClass.SENSITIVE_DATA,
        minimum_rbac_role="Cost Management Reader",
        owner_module="src.tools.cost",
        docs_reference="docs/security-rbac.md",
    ),
    "list_advisor_recommendations": ToolMetadata(
        name="list_advisor_recommendations",
        description="List bounded Azure Advisor recommendations.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.cost",
        docs_reference="docs/security-rbac.md",
    ),
    "list_openai_deployments": ToolMetadata(
        name="list_openai_deployments",
        description="List bounded Azure OpenAI deployment metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Cognitive Services Contributor",
        owner_module="src.tools.ai",
        docs_reference="docs/security-rbac.md",
    ),
    "deploy_openai_model": ToolMetadata(
        name="deploy_openai_model",
        description="Create or update an Azure OpenAI deployment (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Cognitive Services Contributor",
        owner_module="src.tools.ai",
        docs_reference="docs/security-rbac.md",
    ),
    "list_ai_foundry_agents": ToolMetadata(
        name="list_ai_foundry_agents",
        description="List agents through a verified Microsoft Foundry project adapter.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Azure AI User",
        owner_module="src.tools.ai",
        docs_reference="docs/security-rbac.md",
    ),
    "create_ai_foundry_agent": ToolMetadata(
        name="create_ai_foundry_agent",
        description="Create a Microsoft Foundry agent (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Azure AI Developer",
        owner_module="src.tools.ai",
        docs_reference="docs/security-rbac.md",
    ),
    "delete_ai_foundry_agent": ToolMetadata(
        name="delete_ai_foundry_agent",
        description="Delete a Microsoft Foundry agent (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Azure AI Developer",
        owner_module="src.tools.ai",
        docs_reference="docs/security-rbac.md",
    ),
    "diagnose_virtual_machine": ToolMetadata(
        name="diagnose_virtual_machine",
        description="Aggregate bounded VM observations without fabricating a root cause.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader plus Monitoring Reader",
        owner_module="src.tools.diagnostics",
        docs_reference="docs/security-rbac.md",
    ),
    "list_aks_clusters": ToolMetadata(
        name="list_aks_clusters",
        description="List bounded AKS cluster metadata without pod or secret access.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Azure Kubernetes Service Contributor",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_function_apps": ToolMetadata(
        name="list_function_apps",
        description="List bounded Azure Function App metadata without invoking application code.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "query_function_app_logs": ToolMetadata(
        name="query_function_app_logs",
        description="Query bounded Function App logs through a fixed read-only projection.",
        safety_class=SafetyClass.SENSITIVE_DATA,
        minimum_rbac_role="Log Analytics Reader",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_sql_databases": ToolMetadata(
        name="list_sql_databases",
        description="List bounded Azure SQL database metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="SQL DB Contributor",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_cosmos_accounts": ToolMetadata(
        name="list_cosmos_accounts",
        description="List bounded Cosmos DB account metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "query_cosmos_items": ToolMetadata(
        name="query_cosmos_items",
        description="Run one bounded read-only Cosmos DB SELECT query.",
        safety_class=SafetyClass.SENSITIVE_DATA,
        minimum_rbac_role="Cosmos DB Built-in Data Reader",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_ml_workspaces": ToolMetadata(
        name="list_ml_workspaces",
        description="List bounded Azure ML workspace metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="AzureML Data Scientist",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_ml_models": ToolMetadata(
        name="list_ml_models",
        description="List bounded Azure ML model metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="AzureML Data Scientist",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
    "list_ml_jobs": ToolMetadata(
        name="list_ml_jobs",
        description="List bounded Azure ML job and pipeline metadata.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="AzureML Data Scientist",
        owner_module="src.tools.advanced",
        docs_reference="docs/security-rbac.md",
    ),
}


def get_tool_metadata(tool_name: str) -> ToolMetadata:
    """Look up and return the ``ToolMetadata`` for a registered tool.

    Performs a simple dict lookup against ``TOOL_REGISTRY``.  Raises
    ``KeyError`` with a descriptive message when the tool name is not
    registered, which surfaces as a server-side error rather than a silent
    ``None`` return.

    Args:
        tool_name: The canonical MCP tool name (e.g. ``"list_resource_groups"``).

    Returns:
        The ``ToolMetadata`` dataclass for the requested tool.

    Raises:
        KeyError: When ``tool_name`` is not present in ``TOOL_REGISTRY``.
    """
    metadata = TOOL_REGISTRY.get(tool_name)
    if metadata is None:
        raise KeyError(f"Unknown tool metadata: {tool_name}")
    return metadata
