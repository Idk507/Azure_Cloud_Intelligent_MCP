# Phase 3 Slice 3.3 Contracts

Date: 2026-09-21

## Covered Tools

- `query_log_analytics` (`sensitive_data`)
- `get_resource_metrics` (`read_only`)
- `get_cost_summary` (`sensitive_data`)
- `list_advisor_recommendations` (`read_only`)

## Query And Data Boundaries

- Log queries are limited to one statement, 2,000 characters, 168 hours, and 500 rows.
- Mutating KQL operations and external data access are rejected.
- Metrics allow at most 10 metric names, 168 hours, 60-minute intervals, and 500 results.
- Cost queries are limited to a maximum 90-day window.
- Cost and Log Analytics outputs are treated as sensitive operational data and are audited without
  logging raw query text; audit context stores a short query fingerprint instead.
- Advisor results are bounded by an explicit limit and return normalized recommendation metadata.

## Manual Development Check

Use a non-production workspace and subscription scope. Run one bounded Log Analytics query, one
metric query, one cost summary, and one Advisor inventory call. Confirm the response bounds, audit
records, and least-privilege role assignments before using broader scopes.
