# Azure Cloud Intelligence MCP

Phase 1 and Phase 2 are completed. Phase 3 Slices 3.1 through 3.4 are now implemented.

## Current Scope (Phase 1 + Phase 3 Slice 3.1)

- `list_resource_groups`
- `list_virtual_machines(resource_group)`
- `list_storage_accounts(resource_group)`
- `get_virtual_machine_status(resource_group, vm_name)`
- `start_virtual_machine(resource_group, vm_name, has_explicit_approval)`
- `stop_virtual_machine(resource_group, vm_name, has_explicit_approval)`
- `create_storage_account(resource_group, account_name, ..., has_explicit_approval)`
- `upload_blob_content(..., content_base64, has_explicit_approval)`
- `download_blob_content(..., has_explicit_approval)`
- `list_virtual_networks(resource_group)`
- `list_network_security_groups(resource_group)`
- `list_public_ip_addresses(resource_group)`
- `create_public_ip_address(resource_group, public_ip_name, location, has_explicit_approval)`
- `list_key_vaults(resource_group)` (metadata only; no secret values)
- `query_log_analytics(workspace_id, query, timespan_hours, limit)`
- `get_resource_metrics(resource_id, metric_names, timespan_hours, interval_minutes, limit)`
- `get_cost_summary(scope, days)`
- `list_advisor_recommendations(resource_group, limit)`
- `list_openai_deployments(resource_group, account_name, limit)`
- `deploy_openai_model(..., has_explicit_approval)`
- `list_ai_foundry_agents(project_endpoint, limit)`
- `create_ai_foundry_agent(..., has_explicit_approval)`
- `delete_ai_foundry_agent(..., has_explicit_approval)`

Controlled actions and sensitive-data tools require `has_explicit_approval=true`.

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
