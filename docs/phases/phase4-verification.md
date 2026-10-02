# Phase 4 Verification Evidence

Date: 2026-09-21

## Implemented Scope

- Evidence-based VM diagnostic aggregator
- AKS cluster inventory
- Function App inventory
- Fixed-projection Function App log retrieval
- SQL database inventory
- Cosmos account inventory and bounded SELECT query
- Azure ML workspace, model, and job inventory

## Commands And Results

- Opt-in integration gate with `RUN_AZURE_INTEGRATION_TESTS=1`, the supplied development
  subscription, and `DefaultResourceGroup-EUS`: passed.
- `python -m pytest -q`: passed.
- `python -m compileall src tests azure scripts`: passed.
- `python scripts/smoke_test_phase1.py`: passed; health, initialize, and tools-list checks true.
- MCP discovery exposed all Phase 4 tools.

## Safety And Evidence Boundaries

- Diagnostic output separates observations, evidence sources, incomplete evidence, and next actions.
- SQL and ML tools are metadata-only.
- Cosmos queries accept only one bounded SELECT statement and fail closed when the adapter is absent.
- Function logs use a fixed projection, bounded time window, validated app name, and sensitive-data RBAC.
- The opt-in gate verifies explicit non-production scope configuration. The repository uses local
  Azure compatibility shims, so live SDK calls remain a deployment-environment validation step.
- No Azure resources were created or modified during this gate.
- OAuth/shared-deployment authorization boundaries are documented in docs/oauth-boundary.md.
