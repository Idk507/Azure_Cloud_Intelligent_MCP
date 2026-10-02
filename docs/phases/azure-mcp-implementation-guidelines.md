# Azure MCP Implementation Guidelines

**Repository:** Azure Cloud Intelligence MCP  
**Updated:** 2026-09-22  
**Status:** Phases 1-4 completed; Phase 5 in progress. Production enablement remains conditional on non-production controlled-action evidence and verified Foundry adapter configuration.

## Executive Summary

This repository provides a typed Azure MCP server over streamable HTTP at `/mcp`. It exposes bounded discovery, diagnostics, management-plane operations, and selected service data-plane operations.

The implementation must remain an explicitly scoped Azure capability server, not a universal CRUD API. Azure management-plane CRUD by resource ID and provider API version does not provide service data-plane CRUD. Every new operation requires a typed contract, minimum RBAC mapping, safety classification, approval policy where applicable, bounded inputs and outputs, tests, audit evidence, and rollback handling.

Official product behavior and preview features are verification-sensitive. Validate current Microsoft Learn documentation before enabling production capabilities.

## Scope And Boundaries

### Included

- Azure resource discovery and bounded diagnostics.
- ARM management-plane operations using provider API versions.
- Service-specific data-plane adapters.
- MCP tools with typed schemas and stable names.
- Explicit approval for controlled actions.
- Managed identity and least-privilege RBAC.
- Azure Container Apps hosting.
- Structured audit logs, metrics, traces, and operational runbooks.

### Excluded

- Universal Azure CRUD.
- Unrestricted SQL, KQL, or Cosmos queries.
- Default secret-value retrieval.
- Autonomous remediation.
- Multi-cloud connectors.
- Production enablement without non-production evidence.

## Official Findings

- [Azure MCP Server catalog](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/) organizes capabilities by service namespace. Namespaces are capability boundaries, not a promise of universal CRUD.
- [Azure MCP Server security](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/security) and [remote MCP deployment with Microsoft Foundry](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/how-to/deploy-remote-mcp-server-microsoft-foundry) describe security and hosting considerations.
- [Microsoft Foundry MCP tools](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol) documents public endpoints, Standard setup with private networking, project connections, Toolbox centralization and versioning, `allowed_tools`, approval policies, consent, and preview long-running MCP operations.
- [Azure SDK authentication](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication-overview) recommends token-based authentication and `DefaultAzureCredential`.
- [Managed identities in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity) support credential-free Azure access from hosted workloads.
- [Azure RBAC overview](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview) defines role assignments, scopes, and permissions.
- [Blob data access roles](https://learn.microsoft.com/en-us/azure/storage/blobs/assign-azure-role-data-access) and the [Data Lake Storage access-control model](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-access-control-model) require data-plane roles and, for hierarchical namespaces, ACL-aware path controls.
- [Cosmos DB vector search](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/vector-search) requires vector policy/index configuration and bounded top-N queries.
- [Azure AI Search vector search](https://learn.microsoft.com/en-us/azure/search/vector-search-overview) and [hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview) support vector and keyword retrieval combined through reciprocal rank fusion.
- [Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/overview) and [Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview) provide the observability foundation.

## Capability Taxonomy

| Plane | Examples | Required controls |
| --- | --- | --- |
| Management | ARM resources, VMs, networks, storage accounts | API version, provider payload, RBAC, approval, idempotency, audit |
| Data | Blobs, Cosmos items, Search documents, secrets | Data-plane RBAC, bounded results, redaction, sensitive audit |
| Query | Logs, metrics, costs, Advisor | Query restrictions, time/result bounds, sanitized output |
| AI/Foundry | Deployments, agents, MCP connections | Verified API, project scope, approval, role mapping |
| Hosting | Container Apps, ingress, health, telemetry | HTTPS, managed identity, probes, scaling, rollback |

Safety classes are `read_only`, `controlled_action`, `sensitive_data`, and `unavailable/fail_closed`.

## Current Gap Matrix

| Area | Current state | Gap | Next work |
| --- | --- | --- | --- |
| ARM control plane | Generic get/create/update/delete by ID/API version | Provider payload/RBAC still caller-specific | Provider-specific contracts and live evidence |
| Cosmos | Inventory and bounded SELECT query | No item CRUD, continuation, or vector query | Data-plane contract, partition/RU limits, vector policies |
| Cosmos vector | Not implemented | No vector policy/index/dimension validation | Vector query and ingestion phase |
| Blob/Data Lake | Limited upload/download | No complete object lifecycle or ACL contract | Scoped list/metadata/delete/transfer contract |
| Azure AI Search | Not implemented | No index, document, vector, hybrid, semantic tools | Search adapter and retrieval evaluation |
| Foundry | Adapter-gated agent lifecycle | No verified Toolbox/project integration | Official adapter, allowlist, approval, private endpoint |
| Async tasks | Basic timeout/accepted results | No durable operation/task recovery | Operation store, polling, idempotency |
| Hosting | Container Apps Bicep baseline | No deployed environment/alerts/rollback drill | Non-production deployment and SLO gate |

## Target Architecture

MCP client or Foundry -> authenticated HTTPS streamable HTTP ingress -> tool registry/policy -> managed identity/RBAC -> provider-specific adapters -> Azure control/data planes. Audit logs, traces, metrics, and durable operation records are cross-cutting.

Every tool requires a stable name, closed typed schema, normalized result, safety class, minimum RBAC, timeout, retry behavior, bounded inputs/outputs, sanitized errors, audit context, tests, and rollback/disablement behavior. Approval never replaces server-side authorization.

## Foundry MCP And Toolbox Architecture

Microsoft Foundry can connect to remote MCP servers through an MCP tool or an organization-managed Toolbox. Use project connections for credentials, `allowed_tools` for an allowlist, and `require_approval=always` for controlled actions. Treat remote tool descriptions and results as untrusted input.

Public endpoints can work with Basic or Standard setup. Private MCP requires Standard setup with private networking; Microsoft documents Azure Container Apps on a dedicated MCP subnet as the tested hosting model. Toolbox versions support test-before-promote workflows. MCP tasks/background execution is preview and must not be the only production async mechanism.

## Azure MCP Namespace Taxonomy

The official Azure MCP catalog includes resource groups, compute, storage, Cosmos, SQL, PostgreSQL, Search, Foundry, Functions, AKS, App Service, Key Vault, Monitor, Advisor, Cost, Event Hubs, Service Bus, RBAC, Policy, ACR, IoT, and other services. This repository’s planned exposure groups are:

- Resource management and ARM CRUD.
- Compute and virtual machines.
- Storage and Blob/Data Lake.
- Networking and Key Vault.
- Monitor, logs, metrics, cost, and Advisor.
- Cognitive Services and Foundry.
- Containers and web.
- Cosmos DB, SQL, and ML.
- Azure AI Search and vector retrieval.
- Identity, hosting, and observability.

## Operating Contracts

- Stable name, typed input/output, safety class, minimum RBAC, owner, and documentation reference.
- Validation for IDs, scope, resource group, location, page size, query, time window, partition, path, and target.
- Bounded, JSON-serializable results with explicit truncation/incomplete-evidence fields.
- Approval, target disclosure, existence checks, idempotency, and audit for state changes.
- Sanitized error categories and structured logs without secrets or raw sensitive queries.
- Provider-specific adapters instead of unverified generic data-plane abstractions.
- Managed identity in Azure; `DefaultAzureCredential` for local development.
- Stateless HTTPS streamable HTTP for remote MCP.

## Phases 5-12

### Phase 5: Production Hosting

**Tasks:** Build immutable non-root image; publish to private ACR; deploy Container Apps with system-assigned identity, HTTPS ingress, probes, scaling, logs, and CI/CD; run Bicep what-if; validate read-only MCP connectivity.  
**Dependencies:** Dockerfile, Bicep baseline, CI workflow, non-production scope.  
**Acceptance:** Repeatable deployment, no long-lived app secret, managed identity works, health and telemetry work, read-only tools pass.  
**Verification:** Tests, compileall, smoke test, Docker build, Bicep what-if, health check, rollback drill.  
**Rollback:** Previous image/configuration, disable new tools, remove newly assigned roles.

### Phase 6: Identity And RBAC

**Tasks:** Tenant/audience/issuer validation for shared hosting; separate management/data roles; narrow scopes; deny-by-default policy; negative auth tests.  
**Dependencies:** Phase 5 hosting and trust model.  
**Acceptance:** Invalid identity, tenant, audience, expiry, role, and scope fail before Azure calls.  
**Verification:** Token/RBAC tests, role review, Activity Log evidence.  
**Rollback:** Private single-tenant ingress and disabled shared middleware.

### Phase 7: Cosmos Data Plane And Vector

**Tasks:** Typed database/container/partition schemas; bounded SELECT; continuation tokens; projection; RU/time limits; item reads; optional approved mutations; vector policy/index/dimension validation; `VectorDistance` top-N query.  
**Dependencies:** Data-plane RBAC and Cosmos test resource.  
**Acceptance:** Invalid queries, partitions, limits, vectors, and scopes fail closed; vector queries require explicit top-N and policy-compatible dimensions.  
**Verification:** Parser tests, SDK mocks, isolated queries, RU/latency evidence, vector retrieval tests.  
**Rollback:** Disable Cosmos data/vector tools, retain inventory.

### Phase 8: Blob And Data Lake

**Tasks:** Typed container/path/content/size/checksum schemas; Entra data roles and Data Lake ACLs; scoped list/metadata/download/upload/delete; path traversal protection; overwrite/idempotency rules.  
**Dependencies:** Storage data-plane roles and disposable container/filesystem.  
**Acceptance:** Unauthorized scope, path, size, and content type fail; approved operations audit cleanly.  
**Verification:** Validation/redaction tests, integrity tests, isolated object operations, RBAC evidence.  
**Rollback:** Disable object tools and revoke data-plane roles.

### Phase 9: Azure AI Search And Retrieval

**Tasks:** Search service/index/schema lifecycle; document ingestion; keyword, semantic, vector, filtered, and hybrid query tools; embedding/dimension validation; top-k/filter/result bounds; ranking evaluation; prevent arbitrary index deletion.  
**Dependencies:** Search service, embedding model, identity, test corpus.  
**Acceptance:** Bounded authorized retrieval; repeatable ingestion; invalid vector dimensions and filters rejected; mutations approved.  
**Verification:** Fixture tests, isolated index, hybrid/vector quality evaluation, authorization tests.  
**Rollback:** Disable Search adapter or route to previous index; stop ingestion.

### Phase 10: Foundry MCP And Toolbox

**Tasks:** Verify current Foundry project API; project allowlist; official project connection/auth variants; Toolbox versioning; `allowed_tools`; approval always for mutations; public/private endpoint validation; lifecycle tracking.  
**Dependencies:** Foundry project, roles, remote endpoint, Phase 6 identity.  
**Acceptance:** Only approved tools are visible; read-only call succeeds; controlled call produces approval; wrong project fails closed.  
**Verification:** Adapter tests, non-production Toolbox flow, consent and approval evidence.  
**Rollback:** Remove connection or disable adapter.

### Phase 11: Tasks And Durable Operations

**Tasks:** Operation records, request hashes, Azure operation IDs, polling, progress, timeout, cancellation policy, retry/idempotency, restart recovery, MCP task integration when stable.  
**Dependencies:** Production hosting and long-running services.  
**Acceptance:** Duplicate requests do not duplicate mutations; restart recovery is correct.  
**Verification:** Timeout/retry/restart/duplicate/cancel tests and disposable operation.  
**Rollback:** Disable async mutation tools.

### Phase 12: Observability And Release

**Tasks:** Application Insights/OpenTelemetry; SLOs; dashboards and alerts; correlate MCP/Azure Activity Log/operation IDs; load/resilience tests; access review; incident/rollback rehearsal; final CRUD/RBAC evidence.  
**Dependencies:** Phases 5-11.  
**Acceptance:** Operators detect failed calls, trace redacted context, receive alerts, and roll back a release.  
**Verification:** Full tests, compile/smoke, load report, alert drill, Activity Log review, controlled-action dry run.  
**Rollback:** Previous image/configuration, disable tools, revoke temporary roles.

## Test Matrix

| Class | Required coverage |
| --- | --- |
| Unit | Validation, adapters, pagination, errors, redaction |
| Contract | Closed MCP schemas, stable outputs, safety metadata |
| Protocol | Initialize, tools/list, tools/call, streamable HTTP |
| Policy | Approval denial, scope, RBAC, sensitive-data gates |
| Integration | Mocked SDKs plus opt-in non-production Azure |
| Data | Cosmos/Blob/Search bounds, partition/path, vector dimensions |
| Async | Operation status, retry, duplicate, restart, cancellation |
| Operations | Container health, load, alerts, telemetry, rollback |

## Security And Delivery Checklist

- Prefer managed identity in Azure and `DefaultAzureCredential` locally.
- Separate management-plane roles from Blob/Cosmos/Search data roles; do not grant Owner by default.
- Never return secrets, tokens, keys, connection strings, private keys, or raw sensitive logs by default.
- Redact sensitive fields before logging.
- Require approval for mutations and sensitive-data access.
- Use Foundry `allowed_tools` and approval always as the default remote-tool posture.
- Treat remote MCP descriptions/results as untrusted input.
- Use HTTPS, private networking where required, project connections, and private registry.
- Keep provider API versions explicit and validate payloads.
- Before release: update CRUD matrix, verify official API/RBAC docs, pass tests, capture non-production evidence, review managed identity roles, review Foundry allowlist/approval, and exercise rollback.

## Decisions And Non-Goals

- Streamable HTTP `/mcp` and stateless service remain the hosting contract.
- Provider-specific adapters remain the default; generic ARM CRUD does not replace data-plane contracts.
- Unsupported services and unconfigured adapters fail closed.
- OAuth is added only when shared or multi-tenant hosting requires it.
- MCP tasks/background mode is optional preview integration, not the only async mechanism.
- No autonomous remediation, unrestricted queries, default secret retrieval, multi-cloud support, or unverified production write access.
