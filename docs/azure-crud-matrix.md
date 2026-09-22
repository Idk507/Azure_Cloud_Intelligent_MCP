# Azure CRUD Capability Matrix

Date: 2026-09-22

This matrix is the deployment gate for Azure CRUD support. Azure does not expose one universal
CRUD API: each resource provider and data plane has its own SDK, API version, RBAC roles,
long-running-operation behavior, and delete/rollback semantics. A domain is deployment-ready only
when every enabled operation has a typed contract, validation, RBAC mapping, approval policy where
needed, sanitized errors, audit logging, mocked tests, and opt-in live evidence.

## Current Repository Capability

The generic ARM tools provide control-plane CRUD by resource ID and explicit provider API version:
`get_azure_resource`, `create_azure_resource`, `update_azure_resource`, and
`delete_azure_resource`. Create/update/delete require explicit approval, and the caller remains
responsible for provider-specific payload shape, API version, RBAC role, and rollback semantics.
Use `list_azure_resource_providers` to discover registered namespaces/resource types and
`list_azure_resources` to inventory resources before selecting a CRUD target.

| Domain | Read | Create | Update | Delete | Deployment status |
| --- | --- | --- | --- | --- | --- |
| Resource groups | List | Not implemented | Not implemented | Not implemented | Read-only only |
| Generic ARM resource by ID | Generic get | Generic create | Generic update | Generic delete | Available with provider API version and explicit approval |
| Virtual machines | List/status | Not implemented | Start/stop actions only | Not implemented | Partial actions |
| Storage accounts | List | Create | Not implemented | Not implemented | Partial CRUD |
| Blob data | Download | Upload | Overwrite upload only | Not implemented | Partial data-plane |
| Networking | VNet/NSG/public IP list | Public IP create | Not implemented | Not implemented | Partial CRUD |
| Key Vault | Vault metadata | Not implemented | Not implemented | Not implemented | Metadata only |
| Log Analytics/metrics | Query/read | Not applicable | Not applicable | Not applicable | Bounded read-only |
| Cost/Advisor | Read | Not applicable | Not applicable | Not applicable | Read-only |
| Azure OpenAI | Deployment list | Deployment create/update adapter | Deployment create/update adapter | Not implemented | Partial CRUD |
| Microsoft Foundry agents | List | Adapter-gated create | Not implemented | Adapter-gated delete | Partial CRUD |
| AKS | Cluster list | Not implemented | Not implemented | Not implemented | Read-only only |
| Function Apps | App list/log query | Not implemented | Not implemented | Not implemented | Read-only only |
| Azure SQL | Database list | Not implemented | Not implemented | Not implemented | Read-only only |
| Cosmos DB | Account list/query | Not implemented | Not implemented | Not implemented | Read/query only |
| Azure ML | Workspace/model/job list | Not implemented | Not implemented | Not implemented | Read-only only |

## Decision

The server now supports generic Azure Resource Manager control-plane create/read/update/delete by
resource ID, provider API version, and provider payload. Phase 5 may deploy that control-plane
surface only with explicit approval for mutations and provider-specific RBAC/payload validation.
Data-plane operations remain service-specific and must use their own contracts; ARM CRUD does not
mean the server can read or mutate every blob, database row, secret, or model artifact.

## Required Gate Before Enabling More Writes

For each resource operation:

1. Verify the current official SDK/API and long-running-operation behavior.
2. Add typed validation and a stable output/error contract.
3. Map the minimum management/data-plane RBAC role and scope.
4. Require explicit approval for create/update/delete or sensitive data operations.
5. Add idempotency, existence checks, rollback/failure handling, and redacted audit context.
6. Add deterministic mocked tests and an opt-in non-production integration test.
7. Record Activity Log evidence and update this matrix before deployment.

## Official References

- [Manage Azure resources by using Python](https://learn.microsoft.com/azure/azure-resource-manager/management/manage-resources-python)
- [Use the Azure libraries (SDK) for Python](https://learn.microsoft.com/azure/developer/python/sdk/azure-sdk-overview)
- [Azure RBAC overview](https://learn.microsoft.com/azure/role-based-access-control/overview)
- [Authenticate Azure-hosted Python apps with system-assigned managed identity](https://learn.microsoft.com/azure/developer/python/sdk/authentication/system-assigned-managed-identity)
- [Azure Container Apps managed identity](https://learn.microsoft.com/azure/container-apps/managed-identity)
