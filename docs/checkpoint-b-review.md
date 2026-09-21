# Checkpoint B Service Coverage Review

Date: 2026-09-21

## Review Scope

This review covers all implemented Phase 3 tools and verifies approval, RBAC, audit, failure, and
rollback expectations before production enablement.

## Controlled Actions

| Tool | Approval | RBAC | Audit | Failure/rollback story |
| --- | --- | --- | --- | --- |
| `start_virtual_machine` | Explicit approval required | Virtual Machine Contributor | Target, status, duration, correlation ID, error code | Azure long-running operation is returned as accepted; retry/error is sanitized; repeated start is operationally idempotent |
| `stop_virtual_machine` | Explicit approval required | Virtual Machine Contributor | Target, status, duration, correlation ID, error code | Azure long-running operation is returned as accepted; retry/error is sanitized; repeated stop is operationally idempotent |
| `create_storage_account` | Explicit approval required | Storage Account Contributor | Target, status, duration, correlation ID, error code | Create-or-update semantics plus sanitized failure; operator verifies existence before retry |
| `upload_blob_content` | Explicit approval required | Storage Blob Data Contributor | Resource/container/blob target, status, duration, correlation ID, error code | Overwrite is explicit in the adapter; sanitized failure; caller can retry the same blob idempotently |
| `create_public_ip_address` | Explicit approval required | Network Contributor | Resource group/name/location, status, duration, correlation ID, error code | Create-or-update semantics; operator deletes disposable resource through approved Azure operations if rollback is needed |
| `deploy_openai_model` | Explicit approval required | Cognitive Services Contributor | Account/deployment/model target, status, duration, correlation ID, error code | Create-or-update semantics; operator redeploys prior approved model configuration or removes deployment through approved operations |
| `create_ai_foundry_agent` | Explicit approval required | Azure AI Developer | Project/name target, status, duration, correlation ID, error code | Adapter returns created agent identity; delete operation provides explicit rollback |
| `delete_ai_foundry_agent` | Explicit approval required | Azure AI Developer | Project/agent target, status, duration, correlation ID, error code | Deletion is irreversible at the tool layer and therefore requires explicit target confirmation and adapter-side retention/recovery policy |

## Sensitive Data Review

- Key Vault inventory returns metadata only; secret values are not retrieved.
- Blob download, Log Analytics, and Cost Management outputs are classified as sensitive and use
  bounded inputs, normalized errors, and redacted audit context.
- Log query text is represented in audit context by a short fingerprint, not raw query content.
- Foundry agent instructions are never written to audit context.

## RBAC Review

Every registered tool has a minimum role in `src/tool_registry.py` and a corresponding entry in
`docs/security-rbac.md`. No tool intentionally requests a broader role than its documented service
operation requires.

## Evidence

- Automated policy and approval tests: `tests/test_policies.py`, `tests/test_tools.py`, and
  `tests/test_slice34.py`.
- Full suite: 55 tests passing.
- Live read-only subscription/resource inventory: `docs/phase3-live-validation.md`.
- Historical live Activity Log query succeeded for the existing Cognitive Services account; no new
  resource was modified during validation.

## Decision

Phase 3 implementation and review gates are complete. Production enablement remains conditional on
an operator-approved controlled-action run in a disposable non-production scope and a verified
Foundry adapter configuration. Those are deployment gates, not unverified claims in this review.
