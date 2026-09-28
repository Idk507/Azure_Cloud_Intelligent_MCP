# Azure Cloud Intelligence MCP

Phase 1 and Phase 2 are completed. Phase 3 is complete, and Phase 4 advanced domain foundations are implemented.

The server does not claim universal Azure CRUD. Each service exposes only the operations listed in
the tool inventory and [docs/azure-crud-matrix.md](docs/azure-crud-matrix.md); unconfigured service
adapters fail closed.

Generic ARM control-plane CRUD is available by resource ID through `get_azure_resource`,
`create_azure_resource`, `update_azure_resource`, and `delete_azure_resource`. Mutations require
explicit approval and the caller must provide the provider API version and valid provider payload.
Use `list_azure_resource_providers` and `list_azure_resources` to discover available Azure service
providers and resource instances before performing CRUD.

Generic ARM writes now use a two-step workflow: first call
`plan_azure_resource_mutation`, review its target and expiry, then pass the returned
single-use `approval_id` to the matching create, update, or delete tool. A boolean
approval flag is no longer accepted for generic ARM writes.

Foundry agent create, update, and delete follow the same pattern through
`plan_ai_foundry_agent_mutation`; pass its `approval_id` to the corresponding
agent mutation. The approval binds the project endpoint, target agent, model, and
changed instruction content.

For multi-subscription inventory, use `query_azure_resource_graph(query, subscriptions, limit)`.
It accepts bounded inventory-style KQL only and its results are eventually consistent; always
re-read the authoritative resource provider before creating, updating, or deleting a resource.

Use `preview_arm_template_deployment(resource_group, deployment_name, template, parameters)`
to run ARM what-if before reviewing a change. It is a prediction only; it never deploys the
template. Use `get_arm_deployment_operation_status` to inspect a named deployment operation.

## Current Scope (Phase 1 + Phase 3 Slice 3.1)

- `list_resource_groups`
- `query_azure_resource_graph(query, subscriptions, limit)`
- `preview_arm_template_deployment(resource_group, deployment_name, template, parameters)`
- `get_arm_deployment_operation_status(resource_group, deployment_name, operation_id)`
- `list_virtual_machines(resource_group)`
- `list_storage_accounts(resource_group)`
- `get_virtual_machine_status(resource_group, vm_name)`
- `plan_virtual_machine_power_action(...)` then `start_virtual_machine(..., approval_id)` or `stop_virtual_machine(..., approval_id)`
- `plan_storage_mutation(...)` then `create_storage_account`, `upload_blob_content`, or `download_blob_content` with its `approval_id`
- `list_virtual_networks(resource_group)`
- `list_network_security_groups(resource_group)`
- `list_public_ip_addresses(resource_group)`
- `plan_public_ip_creation(...)` then `create_public_ip_address(..., approval_id)`
- `list_key_vaults(resource_group)` (metadata only; no secret values)
- `query_log_analytics(workspace_id, query, timespan_hours, limit)`
- `get_resource_metrics(resource_id, metric_names, timespan_hours, interval_minutes, limit)`
- `get_cost_summary(scope, days)`
- `list_advisor_recommendations(resource_group, limit)`
- `list_openai_deployments(resource_group, account_name, limit)`
- `plan_openai_deployment(...)` then `deploy_openai_model(..., approval_id)`
- `list_ai_foundry_agents(project_endpoint, limit)`
- `plan_ai_foundry_agent_mutation(...)` then `create_ai_foundry_agent(..., approval_id)`
- `get_ai_foundry_agent(project_endpoint, agent_id)`
- `update_ai_foundry_agent(..., approval_id)`
- `delete_ai_foundry_agent(..., approval_id)`
- `diagnose_virtual_machine(resource_group, vm_name, ...)`
- `list_aks_clusters(resource_group, limit)`
- `list_function_apps(resource_group, limit)`
- `query_function_app_logs(workspace_id, function_app_name, timespan_hours, limit)`
- `list_sql_databases(resource_group, server_name, limit)`
- `list_cosmos_accounts(resource_group, limit)`
- `query_cosmos_items(account_name, database_name, container_name, query, limit)`
- `list_ml_workspaces(resource_group, limit)`
- `list_ml_models(workspace_name, limit)`
- `list_ml_jobs(workspace_name, limit)`

Controlled actions and sensitive-data tools require a single-use `approval_id` from
their matching plan tool. The receipt is bound to the tool, subscription/resource
group scope, target, and payload, and expires after five minutes.
Foundry agent creation requires a deployed Foundry `model`; its plan tool creates the
approval receipt before any agent mutation is submitted.

## Prerequisites

- Python 3.11+
- Azure CLI authenticated locally (`az login`)
- Environment variable: `AZURE_SUBSCRIPTION_ID`

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `python -m pip install -r requirements.txt`
3. Set required environment variables:
   - `AZURE_SUBSCRIPTION_ID`
4. Run the server:
   - `python -m src.app`

## Endpoints

- MCP endpoint: `/mcp`
- Health endpoint: `/health`

## Verification

1. Dependency readiness check:
   - `python scripts/check_environment.py`
1. Run tests:
   - `python -m pytest -q`
1. Check syntax:
   - `python -m compileall src tests`
1. Configure a tunnel and scan tools from the MCP client.

If dependency installation is blocked by environment policy, run the smoke test:

- `python scripts/smoke_test_phase1.py`

See [docs/tunnel-options.md](docs/tunnel-options.md) for HTTPS exposure options.
See [docs/environment-readiness.md](docs/environment-readiness.md) for readiness details.
See [docs/phase5-deployment-baseline.md](docs/phase5-deployment-baseline.md) for the Container Apps and CI baseline.
