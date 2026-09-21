# Security, RBAC, and Data Handling (Phase 2-3)

## Tool-to-RBAC Mapping

| Tool | Safety class | Minimum RBAC role |
| --- | --- | --- |
| `list_resource_groups` | `read_only` | `Reader` |
| `list_virtual_machines` | `read_only` | `Reader` (or `Virtual Machine Contributor`) |
| `get_virtual_machine_status` | `read_only` | `Reader` (or `Virtual Machine Contributor`) |
| `start_virtual_machine` | `controlled_action` | `Virtual Machine Contributor` |
| `stop_virtual_machine` | `controlled_action` | `Virtual Machine Contributor` |
| `list_storage_accounts` | `read_only` | `Reader` (or `Storage Account Contributor`) |
| `create_storage_account` | `controlled_action` | `Storage Account Contributor` |
| `upload_blob_content` | `controlled_action` | `Storage Blob Data Contributor` |
| `download_blob_content` | `sensitive_data` | `Storage Blob Data Reader` |
| `list_virtual_networks` | `read_only` | `Reader` |
| `list_network_security_groups` | `read_only` | `Reader` |
| `list_public_ip_addresses` | `read_only` | `Reader` |
| `create_public_ip_address` | `controlled_action` | `Network Contributor` |
| `list_key_vaults` | `read_only` | `Reader` |
| `query_log_analytics` | `sensitive_data` | `Log Analytics Reader` |
| `get_resource_metrics` | `read_only` | `Monitoring Reader` |
| `get_cost_summary` | `sensitive_data` | `Cost Management Reader` |
| `list_advisor_recommendations` | `read_only` | `Reader` |
| `list_openai_deployments` | `read_only` | `Cognitive Services Contributor` |
| `deploy_openai_model` | `controlled_action` | `Cognitive Services Contributor` |
| `list_ai_foundry_agents` | `read_only` | `Azure AI User` |
| `create_ai_foundry_agent` | `controlled_action` | `Azure AI Developer` |
| `delete_ai_foundry_agent` | `controlled_action` | `Azure AI Developer` |
| `diagnose_virtual_machine` | `read_only` | `Reader` plus `Monitoring Reader` |

## Data Handling Policy

1. Do not log secret values, tokens, client secrets, or connection strings.
2. Return only fields needed for read-only inventory use cases.
3. Normalize and validate user inputs before issuing Azure API requests.
4. For controlled actions, require explicit approval and audit-safe logging before execution.
5. Store long-lived credentials in managed stores (Key Vault or deployment secret stores).
6. Key Vault tools expose metadata only; secret, key, and certificate values are not returned.
7. Foundry agent lifecycle tools require an explicitly configured verified project adapter; they do
  not fall back to guessed SDK endpoints or credentials.

## Logging Requirements

- Every tool call log must contain:
  - `tool_name`
  - `safety_class`
  - `status`
  - `duration_ms`
  - `correlation_id`
- Logs must avoid raw request payloads that can contain sensitive values.

## Controlled Action Policy (Foundation)

Controlled actions are denied unless explicit approval is present. This policy is implemented in
`src/policies.py` and must wrap any future write, deploy, or delete tool.
