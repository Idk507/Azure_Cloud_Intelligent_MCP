# Environment Readiness Checks

Use these scripts before running full Phase 1 tests.

## 1. Dependency readiness

Run:

`python scripts/check_environment.py`

Exit code:

- `0`: all required modules are installed.
- `2`: one or more required modules are missing.

## 2. Policy-safe smoke tests

Run:

`python scripts/smoke_test_phase1.py`

This verifies:

- MCP initialize payload shape
- registered Phase 1 tool metadata
- health endpoint behavior when `AZURE_SUBSCRIPTION_ID` is missing

## 3. Full test suite (when dependencies are installed)

Run:

`python -m pytest -q`
