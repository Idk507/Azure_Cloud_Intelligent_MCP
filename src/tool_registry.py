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
    "list_accessible_subscriptions": ToolMetadata(name="list_accessible_subscriptions", description="List subscriptions available to the configured Azure identity without selecting one.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.subscriptions", docs_reference="docs/portable-plugin-architecture.md"),
    "list_container_app_revisions": ToolMetadata(name="list_container_app_revisions", description="List Container App revision health metadata without revision templates or secrets.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.advanced", docs_reference="docs/security-rbac.md"),
    "list_container_app_environments": ToolMetadata(name="list_container_app_environments", description="List Container Apps environment metadata without log credentials or network details.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.advanced", docs_reference="docs/security-rbac.md"),
    "list_container_apps": ToolMetadata(name="list_container_apps", description="List Container App metadata without configuration, revision templates, or secrets.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.advanced", docs_reference="docs/security-rbac.md"),
    "list_app_service_slots": ToolMetadata(name="list_app_service_slots", description="List App Service deployment-slot metadata without configuration values.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Website Contributor", owner_module="src.tools.advanced", docs_reference="docs/security-rbac.md"),
    "get_storage_lifecycle_policy": ToolMetadata(name="get_storage_lifecycle_policy", description="Read storage lifecycle policy rules without modifying retention.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Storage Account Contributor", owner_module="src.tools.storage", docs_reference="docs/security-rbac.md"),
    "list_storage_containers": ToolMetadata(name="list_storage_containers", description="List storage container metadata without blob contents or metadata values.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Storage Blob Data Reader", owner_module="src.tools.storage", docs_reference="docs/security-rbac.md"),
    "list_aks_node_pools": ToolMetadata(name="list_aks_node_pools", description="List AKS node-pool capacity and configuration metadata without credentials.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Azure Kubernetes Service Contributor", owner_module="src.tools.advanced", docs_reference="docs/security-rbac.md"),
    "list_key_vault_secret_metadata": ToolMetadata(name="list_key_vault_secret_metadata", description="List Key Vault secret metadata without retrieving values or tags.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Key Vault Secrets User", owner_module="src.tools.keyvault", docs_reference="docs/security-rbac.md"),
    "create_ai_foundry_evaluation": ToolMetadata(name="create_ai_foundry_evaluation", description="Create a Foundry evaluation after single-use approval.", safety_class=SafetyClass.CONTROLLED_ACTION, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_evaluation_runs": ToolMetadata(name="list_ai_foundry_evaluation_runs", description="List bounded Foundry evaluation-run metadata without scores or sample content.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_evaluations": ToolMetadata(name="list_ai_foundry_evaluations", description="List bounded Foundry evaluation metadata without criteria or dataset details.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_agent_threads": ToolMetadata(name="list_ai_foundry_agent_threads", description="List Foundry agent thread metadata without messages or metadata.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_thread_runs": ToolMetadata(name="list_ai_foundry_thread_runs", description="List Foundry thread run metadata without inputs or outputs.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "upsert_ai_foundry_project_connection": ToolMetadata(name="upsert_ai_foundry_project_connection", description="Create or update a Foundry project connection after single-use approval.", safety_class=SafetyClass.CONTROLLED_ACTION, minimum_rbac_role="Cognitive Services Contributor", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_thread_messages": ToolMetadata(name="list_ai_foundry_thread_messages", description="List Foundry thread message metadata without content.", safety_class=SafetyClass.SENSITIVE_DATA, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "get_ai_foundry_project_connection": ToolMetadata(name="get_ai_foundry_project_connection", description="Read Foundry project connection metadata without credentials.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "delete_ai_foundry_project_connection": ToolMetadata(name="delete_ai_foundry_project_connection", description="Delete a Foundry project connection after single-use approval.", safety_class=SafetyClass.CONTROLLED_ACTION, minimum_rbac_role="Cognitive Services Contributor", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "get_ai_foundry_trace_status": ToolMetadata(name="get_ai_foundry_trace_status", description="Report Foundry tracing readiness without exposing connection values.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_models": ToolMetadata(name="list_ai_foundry_models", description="List bounded Microsoft Foundry model metadata.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_ai_foundry_connections": ToolMetadata(name="list_ai_foundry_connections", description="List bounded Microsoft Foundry connection metadata without credential values.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Foundry User", owner_module="src.tools.ai", docs_reference="docs/foundry-agent-service.md"),
    "list_role_assignments": ToolMetadata(name="list_role_assignments", description="List bounded RBAC role assignments at a validated scope.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.governance", docs_reference="docs/security-rbac.md"),
    "list_policy_definitions": ToolMetadata(name="list_policy_definitions", description="List bounded Azure Policy definition metadata.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.governance", docs_reference="docs/security-rbac.md"),
    "list_policy_assignments": ToolMetadata(name="list_policy_assignments", description="List bounded Azure Policy assignment metadata at a validated scope.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Reader", owner_module="src.tools.governance", docs_reference="docs/security-rbac.md"),
    "list_policy_compliance_states": ToolMetadata(name="list_policy_compliance_states", description="List bounded latest Azure Policy compliance states.", safety_class=SafetyClass.READ_ONLY, minimum_rbac_role="Resource Policy Contributor or Reader", owner_module="src.tools.governance", docs_reference="docs/security-rbac.md"),
    "list_resource_groups": ToolMetadata(
        name="list_resource_groups",
        description="List Azure resource groups in the current subscription.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/security-rbac.md",
    ),
    "list_azure_resources": ToolMetadata(
        name="list_azure_resources",
        description="List generic Azure Resource Manager resources across a subscription or resource group.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
    ),
    "query_azure_resource_graph": ToolMetadata(
        name="query_azure_resource_graph",
        description="Run a bounded inventory query across explicit Azure subscriptions using Resource Graph.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader on each queried subscription",
        owner_module="src.tools.resource_graph",
        docs_reference="tasks/plan.md",
    ),
    "preview_arm_template_deployment": ToolMetadata(
        name="preview_arm_template_deployment",
        description="Preview resource-group ARM template changes using what-if without deploying resources.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Deployment Contributor plus target resource write permissions",
        owner_module="src.tools.deployments",
        docs_reference="tasks/plan.md",
    ),
    "get_arm_deployment_operation_status": ToolMetadata(
        name="get_arm_deployment_operation_status",
        description="Read the status of one named ARM deployment operation.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.deployments",
        docs_reference="tasks/plan.md",
    ),
    "list_azure_resource_providers": ToolMetadata(
        name="list_azure_resource_providers",
        description="List Azure resource providers and resource types available to the subscription.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
    ),
    "get_azure_resource": ToolMetadata(
        name="get_azure_resource",
        description="Read any Azure Resource Manager resource by resource ID.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Reader",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
    ),
    "create_azure_resource": ToolMetadata(
        name="create_azure_resource",
        description="Create any supported Azure Resource Manager resource (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Provider-specific Contributor role",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
    ),
    "update_azure_resource": ToolMetadata(
        name="update_azure_resource",
        description="Update any supported Azure Resource Manager resource (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Provider-specific Contributor role",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
    ),
    "delete_azure_resource": ToolMetadata(
        name="delete_azure_resource",
        description="Delete any supported Azure Resource Manager resource (controlled action).",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Provider-specific Contributor role",
        owner_module="src.tools.resource_mgmt",
        docs_reference="docs/azure-crud-matrix.md",
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
    "plan_azure_resource_mutation": ToolMetadata(
        name="plan_azure_resource_mutation",
        description="Create a short-lived approval plan for a generic ARM create, update, or delete request.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="No Azure permission; execution requires provider-specific RBAC",
        owner_module="src.tools.resource_mgmt",
        docs_reference="tasks/plan.md",
    ),
    "get_ai_foundry_agent": ToolMetadata(
        name="get_ai_foundry_agent",
        description="Read one Microsoft Foundry agent definition.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="Foundry User",
        owner_module="src.tools.ai",
        docs_reference="docs/foundry-agent-service.md",
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
    "plan_ai_foundry_agent_mutation": ToolMetadata(
        name="plan_ai_foundry_agent_mutation",
        description="Create a short-lived approval plan for a Foundry agent mutation.",
        safety_class=SafetyClass.READ_ONLY,
        minimum_rbac_role="No Azure permission; execution requires Foundry User",
        owner_module="src.tools.ai",
        docs_reference="tasks/plan.md",
    ),
    "update_ai_foundry_agent": ToolMetadata(
        name="update_ai_foundry_agent",
        description="Update a Microsoft Foundry agent after explicit approval.",
        safety_class=SafetyClass.CONTROLLED_ACTION,
        minimum_rbac_role="Foundry User",
        owner_module="src.tools.ai",
        docs_reference="docs/foundry-agent-service.md",
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
