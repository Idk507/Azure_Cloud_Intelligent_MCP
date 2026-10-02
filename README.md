# Azure Cloud Intelligence MCP

## Start here

For a complete fresh-clone walkthrough—including Azure sign-in, local validation, ngrok, Codex,
and ChatGPT—follow [SETUP.md](SETUP.md). It is the recommended installation guide for individual users.


The server does not claim universal Azure CRUD. Each service exposes only the operations listed in
the tool inventory and [docs/phases/azure-crud-matrix.md](docs/phases/azure-crud-matrix.md); unconfigured service
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

## Current Scope

The running server's `tools.list` response is the authoritative tool inventory. It includes
bounded Azure Resource Graph and ARM discovery, HITL-protected generic ARM and supported
provider mutations, governance inspection, Foundry project operations, observability, and
read-only service slices. The full operation/RBAC matrix is maintained in
[docs/phases/azure-crud-matrix.md](docs/phases/azure-crud-matrix.md) and
[docs/security-rbac.md](docs/security-rbac.md).

Notable provider-specific inventory includes:

- Key Vault secret metadata only (never secret values), Storage containers and lifecycle policies,
  AKS node pools, App Service slots, and Container Apps, environments, and revision health.
- Azure OpenAI deployments plus Foundry models, connections, agents, threads, runs, evaluations,
  and tracing readiness, with sensitive content excluded by default.

The foundational tool categories are:

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
- Azure CLI authenticated locally (`az login`), a managed identity, or a service principal configured through Azure Identity.
- `AZURE_SUBSCRIPTION_ID` for subscription-scoped Azure Resource Manager tools. It is optional when using Foundry-only tools.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `python -m pip install -r requirements.txt`
3. Set the target subscription before using subscription-scoped tools:
   - `AZURE_SUBSCRIPTION_ID=<your-subscription-id>`
   - If unknown, call `list_accessible_subscriptions` first, then select an ID explicitly. The server never selects one automatically.
4. Run the server:
   - `python -m src.app`

## Docker quick start

Docker is an alternative to the Python virtual-environment setup. It is intended for a managed
identity (when deployed on Azure) or an Azure service principal passed in by the container runtime.
It does **not** reuse a host `az login` session automatically.

```powershell
docker build --tag azure-cloud-intelligence-mcp:local .
$env:AZURE_SUBSCRIPTION_ID = '<your-subscription-id>'
$env:AZURE_TENANT_ID = '<your-tenant-id>'
$env:AZURE_CLIENT_ID = '<your-service-principal-client-id>'
$env:AZURE_CLIENT_SECRET = '<your-service-principal-secret>'
docker run --rm -p 8000:8000 `
  -e AZURE_SUBSCRIPTION_ID -e AZURE_TENANT_ID -e AZURE_CLIENT_ID -e AZURE_CLIENT_SECRET `
  azure-cloud-intelligence-mcp:local
```

Never put these values in the image, Dockerfile, repository, or a committed `.env` file. For a
personal laptop setup using `az login`, use the Python path in [SETUP.md](SETUP.md) instead.

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
See [docs/phases/environment-readiness.md](docs/phases/environment-readiness.md) for readiness details.
See [docs/phases/phase5-deployment-baseline.md](docs/phases/phase5-deployment-baseline.md) for the Container Apps and CI baseline.
For the local-Codex versus hosted-ChatGPT identity model required for publication, see
[docs/portable-plugin-architecture.md](docs/portable-plugin-architecture.md).

## Self-hosting and MCP clients

- [Self-hosted quick start](docs/self-hosted-quickstart.md)
- [ChatGPT private connector](docs/chatgpt-private-connector.md)
- [Codex local connector](docs/codex-local-connector.md)
- [Self-hosted security checklist](docs/self-hosted-security.md)
