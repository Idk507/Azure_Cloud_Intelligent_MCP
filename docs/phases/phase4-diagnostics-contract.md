# Phase 4 Diagnostic Contract

Date: 2026-09-21

## Tool

`diagnose_virtual_machine`

## Evidence Contract

- `observations` contains source-labelled Azure observations only.
- `inferences` is empty unless a future implementation adds an evidence-backed inference explicitly.
- `evidence_sources` identifies the compute, metrics, and Advisor sources used.
- `incomplete_evidence` identifies omitted or failed evidence sources.
- `next_actions` are cautious operator actions, not autonomous remediation.
- Metrics are optional and bounded by the existing metrics query constraints.
- Advisor output is bounded and normalized through the existing Advisor tool.

## Safety Boundary

The diagnostic tool is read-only. It does not start, stop, deploy, delete, or otherwise mutate Azure
resources. Any later remediation must call a separately approved controlled-action tool.

## Verification

- `tests/test_diagnostics.py` covers observation/inference separation, optional metrics evidence,
  incomplete evidence, and invalid resource IDs.
- MCP discovery includes the diagnostic tool.
- The full suite remains the phase gate for each additional Phase 4 slice.
