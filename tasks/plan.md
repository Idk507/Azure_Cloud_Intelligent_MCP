# Implementation Plan: Azure and Microsoft Foundry MCP Coverage

## Overview

Extend this MCP server from a collection of service adapters into a safe Azure
operations surface. The plan prioritizes discovery, preflight, governance, and
auditable human-approved mutations over a claim of universal Azure CRUD. Azure
Resource Manager covers control-plane resources, but Azure data-plane APIs
(Storage, Key Vault, Foundry, SQL, Cosmos) require service-specific contracts.

## Evidence-Based Gap Analysis

| Area | Current repository coverage | Missing capability | Plan priority |
| --- | --- | --- | --- |
| Azure inventory | Resource groups, bounded ARM list/get/provider discovery | Cross-subscription inventory, Resource Graph queries, change history | P0 |
| ARM changes | Generic resource-ID CRUD, approval boolean | Change preview/what-if, operation polling, idempotency, locks/tags/move support | P0 |
| Approval | Boolean gate and audit log | Two-step approval receipts with immutable request hash, expiry, deny/replay path | P0 |
| Observability | JSON logs, correlation ID, local hooks | OpenTelemetry traces/metrics export, Azure Activity Log correlation, alert/runbook contract | P0 |
| Governance | RBAC metadata only | Read-only RBAC inspection, Policy compliance discovery and safe policy preflight | P1 |
| Foundry agents | List/get/create/update/delete definitions | Connection management, model/deployment discovery, invocation/session lifecycle, evaluation inventory/runs, tracing status | P1 |
| Foundry safety | Redacted local audit hooks | Project-scoped telemetry configuration status, prompt/tool-result minimization, evaluation approval boundary | P1 |
| Azure services | Targeted Compute, Storage, Network, Monitor, Cost, AKS, Functions, SQL, Cosmos, ML adapters | Provider-specific lifecycle tools only where a documented contract and test resource exists | P2 |
| Deployment | Container/Container Apps baseline | Managed identity validation, CI/CD gates, live non-production verification, load/resilience checks | P2 |

## Architecture Decisions

- Preserve generic ARM CRUD as a narrow escape hatch; never infer API versions or provider payloads.
- Add Azure Resource Graph for multi-subscription discovery. It is eventually consistent, so mutation preflight must read the authoritative resource provider after a Graph result.
- Make all mutations two-step: `plan_*` produces a redacted, immutable request hash and expiry; `approve_and_execute_*` requires the returned approval ID. A simple client boolean is not sufficient for an auditable HITL workflow.
- Use Azure deployment what-if for template/Bicep operations before approval. It predicts changes but is not an authorization bypass and has documented limits.
- Keep governance reads separate from governance writes. Policy/RBAC assignment changes are privileged and remain deferred until a dedicated security review.
- Use the stable Foundry SDK 2.x project endpoint APIs. Treat Foundry MCP Server features marked preview as a discovery reference, not a production dependency.
- Instrument only allowlisted, redacted metadata in MCP logs/hooks. Foundry traces may contain prompt and tool payloads; project retention/access settings must be explicitly reviewed.

## Dependency Graph

```text
approval contract + audit schema
    -> ARM preflight/operation tracker -> service mutations
resource graph + scope model
    -> inventory/governance reads -> diagnostics
Foundry project client
    -> agent lifecycle -> connections/invocation/evaluations
OpenTelemetry export + trace context
    -> dashboards/alerts -> production validation
```

## Phased Delivery

### Phase 0: Contract and safety baseline

Define common scope, operation, approval, error, pagination, and audit schemas. Add a persisted approval store abstraction and a test-only in-memory implementation. No additional Azure mutation tools in this phase.

### Phase 1: Azure discovery and mutation preflight

Add Resource Graph query with a safe KQL subset and bounded results; add ARM tag/lock reads; add resource-operation polling; add template/Bicep what-if. All preflight tools are read-only and return a stable plan artifact.

### Phase 2: HITL execution and observability

Turn approved plans into execution using request-hash binding, expiry, single-use approval IDs, idempotent operation handling, Activity Log correlation, OpenTelemetry tracing/metrics, and hooks. Add read-only audit-history querying.

### Phase 3: Governance reads

Add Azure RBAC role-definition/assignment inspection and Azure Policy definition/assignment/compliance discovery. Add a policy-impact preflight only; do not create assignments or remediations without a separate approved specification.

### Phase 4: Foundry project capabilities

Complete project-scoped Foundry capabilities in vertical slices: model/deployment discovery; project connection read/CRUD; agent invocation/session reads; evaluation dataset/evaluation/run reads and approved creation; telemetry connection/status inspection. Each data-plane mutation uses Phase 2 HITL.

### Phase 5: Provider-specific Azure service expansion

Prioritize service modules based on user demand and documented SDK maturity. Candidate slices: VM resize/restart, storage containers/lifecycle policies, Key Vault secret metadata/rotation requests, AKS node-pool read/scale plans, App Service slots/config metadata, SQL/Cosmos database lifecycle plans, and Azure ML endpoint/job operations. Do not expose secret values by default.

### Phase 6: Production readiness

Run an isolated Azure integration environment through every approval and rollback path. Configure managed identity, Application Insights, alert rules, retention controls, CI dependency/security gates, and incident runbooks.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Universal CRUD causes destructive or invalid provider requests | Generic ARM remains explicit; new providers require a separate contract, RBAC map, test fixture, and preflight. |
| Approval tokens replayed or altered | Hash canonical request content; enforce scope/tool binding, TTL, and one-time use. |
| Graph staleness leads to unsafe action | Re-read the authoritative resource provider before approval/execution. |
| Telemetry leaks prompts or secrets | Allowlist fields, redact at source, configure Foundry/Application Insights retention and RBAC before enabling traces. |
| Preview Foundry surface changes | Keep preview capability behind a feature flag and pin/verify SDK behavior in integration tests. |

## Official Sources

- [Azure Resource Manager overview](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/overview)
- [Azure Resource Graph overview](https://learn.microsoft.com/en-us/azure/governance/resource-graph/overview)
- [ARM deployment what-if](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deploy-what-if)
- [Azure RBAC overview](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview)
- [Azure Policy overview](https://learn.microsoft.com/en-us/azure/governance/policy/overview)
- [Foundry SDK and project endpoint overview](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/sdk-overview)
- [Foundry MCP Server tool inventory (preview)](https://learn.microsoft.com/en-us/azure/foundry/mcp/available-tools)
- [Foundry tracing setup](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup)
- [Foundry evaluation quickstart](https://learn.microsoft.com/en-us/azure/foundry/observability/quickstarts/quickstart-evaluate-hosted-agent)
