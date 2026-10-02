# Azure and Foundry MCP Work Items

## Phase 0

- [x] Task 1: Define approval-plan, execution, and audit schemas.
  - Acceptance: Canonical request hashes bind tool, scope, target, and payload; approval has TTL and single-use semantics.
  - Verify: Focused policy/serialization tests and full `python -m pytest -q`.
  - Dependencies: None.
  - Files likely touched: `src/policies.py`, `src/monitor.py`, `src/validation.py`, `tests/test_policies.py`.

- [x] Task 2: Add an approval store abstraction and in-memory test implementation.
  - Acceptance: A rejected, expired, replayed, or payload-mismatched approval cannot invoke Azure.
  - Verify: Unit tests covering all denied paths.
  - Dependencies: Task 1.
  - Files likely touched: `src/approvals.py`, `src/policies.py`, `tests/test_approvals.py`.

## Checkpoint: Safety foundation

- [x] All existing mutations still require valid HITL approval and no new Azure calls occur during unit tests.

## Phase 1

- [x] Task 3: Add bounded Azure Resource Graph inventory queries.
  - Acceptance: Query accepts explicit subscriptions, a read-only KQL subset, pagination, and returns an eventual-consistency notice.
  - Verify: Mocked query and validation tests.
  - Dependencies: Task 1.
  - Files likely touched: `src/tools/resource_graph.py`, `src/azure_clients.py`, `src/app.py`, `tests/test_resource_graph.py`.

- [x] Task 4: Add ARM what-if and long-running-operation status tools.
  - Acceptance: What-if produces a redacted plan; execution never starts from the preflight tool; operation status is bounded and sanitized.
  - Verify: Mocked ARM client tests.
  - Dependencies: Task 3.
  - Files likely touched: `src/tools/deployments.py`, `src/validation.py`, `src/app.py`, `tests/test_deployments.py`.

## Phase 2

- [x] Task 5: Bind generic and provider mutations to approval plans.
  - Progress: Generic ARM and Foundry agent mutations complete; provider-specific mutation migration remains.
  - Acceptance: Mutations accept approval IDs rather than a bare boolean and emit approval/execution/operation audit events.
  - Verify: Regression tests for generic ARM and Foundry mutations.
  - Dependencies: Tasks 2 and 4.
  - Files likely touched: `src/tools/resource_mgmt.py`, `src/tools/ai.py`, `src/policies.py`, `tests/test_generic_crud.py`.

- [ ] Task 6: Export OpenTelemetry traces and RED metrics.
  - Progress: Optional OTLP trace and metric exporters emit only the bounded tool name, outcome, safety class, and duration dimensions. The deployment baseline can now create an opt-in workspace-based Application Insights component; the remaining verification is to connect it to the Foundry project and run an Application Insights smoke test.
  - Acceptance: Tool spans preserve correlation IDs, metrics use bounded labels, and no secrets are attributes.
  - Verify: Telemetry unit tests plus an opt-in Application Insights smoke test.
  - Dependencies: Task 5.
  - Files likely touched: `src/monitor.py`, `src/config.py`, `requirements.txt`, `tests/test_monitor.py`.

## Checkpoint: Auditable mutation path

- [ ] A disposable non-production resource completes plan -> approval -> execution -> Activity Log/trace correlation -> operation status.

## Phase 3

- [x] Task 7: Add RBAC and Azure Policy read-only discovery.
  - Completed: Role assignments, policy definitions/assignments, and bounded Policy Insights compliance reads are implemented and scope-validated.
  - Acceptance: Roles, assignments, policy definitions/assignments, and compliance results are bounded and scope-validated.
  - Verify: Mocked management-client tests and minimum-role documentation.
  - Dependencies: Task 3.
  - Files likely touched: `src/tools/governance.py`, `src/app.py`, `docs/security-rbac.md`, `tests/test_governance.py`.

## Phase 4

- [x] Task 8: Add Foundry model/deployment and project-connection discovery.
  - Completed: Bounded model, Azure OpenAI deployment, and connection discovery are implemented; each inventory path supports opaque SDK continuation cursors and excludes credentials.
  - Acceptance: Project endpoint validation, no credential values returned, model/deployment/connection reads are paginated.
  - Verify: Adapter contract tests.
  - Dependencies: Tasks 2 and 6.
  - Files likely touched: `src/foundry_adapter.py`, `src/tools/ai.py`, `tests/test_foundry.py`.

- [x] Task 9: Add approved Foundry connection CRUD and agent session/invocation reads.
  - Completed: Connection get/upsert/delete operations require request-bound approval for mutations; thread, message, and run reads return metadata only.
  - Acceptance: Connection mutations use approval IDs; agent session reads exclude sensitive content unless explicitly authorized.
  - Verify: Approval and redaction tests.
  - Dependencies: Task 8.
  - Files likely touched: `src/foundry_adapter.py`, `src/tools/ai.py`, `src/validation.py`, `tests/test_foundry.py`.

- [x] Task 10: Add Foundry evaluation and tracing-status tools.
  - Completed: Tracing readiness is redacted; evaluation and run reads are bounded; evaluation creation is HITL-protected.
  - Acceptance: Evaluation reads are bounded; evaluation creation is HITL-protected; tracing reports configuration status without exposing connection strings.
  - Verify: Adapter contract tests and opt-in project smoke test.
  - Dependencies: Tasks 6 and 9.
  - Files likely touched: `src/tools/foundry_evaluations.py`, `src/app.py`, `tests/test_foundry_evaluations.py`.

## Checkpoint: Foundry readiness

- [ ] A dedicated Foundry project proves agent, connection, evaluation, and trace-status workflows with redacted audit evidence.
  - Progress: The live project successfully completed a disposable agent `plan -> approval -> create -> read -> separate approval -> delete` lifecycle on 2026-10-02. Connection, evaluation, and trace-status smoke checks remain opt-in because they require project resources and telemetry configuration not present in the validation project.

## Phase 5 and 6

- [ ] Task 11: Select and implement provider-specific Azure service slices from verified demand.
  - Progress: Added Key Vault secret-metadata, AKS node-pool, Storage container/lifecycle-policy, App Service slot, Container App, managed-environment, and revision-health reads; all are bounded and non-mutating.
  - Acceptance: Each slice has a service contract, minimal RBAC, preflight/rollback story, and isolated tests.
  - Verify: Focused tests plus one non-production live validation per slice.
  - Dependencies: Task 5.
  - Files likely touched: Service-specific modules and tests only.

- [ ] Task 12: Complete production operational readiness.
  - Progress: The Container App has liveness and readiness probes, Bicep compilation is a CI gate, the error/latency runbook is available, and Bicep can optionally create the workspace-based Application Insights component required for Foundry tracing. Alert routing plus staging failure and rollback validation require a non-production Azure environment and notification target.
  - Acceptance: Managed identity, telemetry, alerts, CI gates, runbooks, and a tested rollback path are in place.
  - Verify: Staging deployment and failure simulation.
  - Dependencies: Tasks 6, 7, 10, and 11.
  - Files likely touched: `infra/`, CI configuration, `docs/`.
