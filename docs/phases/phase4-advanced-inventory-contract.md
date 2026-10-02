# Phase 4 Advanced Inventory Contract

Date: 2026-09-21

## Covered Tools

- `list_aks_clusters`
- `list_function_apps`

## Safety Boundary

Both tools are read-only inventory operations. They return bounded metadata only, do not invoke
application code, do not inspect pod contents, and do not return secrets or host keys.

## Scope And Reliability

- Optional resource-group scoping is validated.
- Result limits are bounded by the shared pagination settings.
- Azure calls run through the shared timeout and retry-configured clients.
- Failures are normalized and emitted through structured audit logging.

## Function Logs

Function logs use a fixed read-only projection through the existing Log Analytics contract. The
function app name is validated, the time window and result count are bounded, and the tool is
classified as sensitive operational data.
