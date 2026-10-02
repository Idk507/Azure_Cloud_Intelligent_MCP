# Phase 4 Data Domain Contract

Date: 2026-09-21

## SQL

`list_sql_databases` is metadata-only inventory scoped to a resource group and server. It does not
execute SQL statements or return row data.

## Cosmos DB

`list_cosmos_accounts` is metadata-only inventory. `query_cosmos_items` accepts one bounded SELECT
statement, rejects mutations/multi-statements, limits result count, and returns a sensitive-data
classification with normalized audit logging.

## Azure ML

`list_ml_workspaces`, `list_ml_models`, and `list_ml_jobs` expose bounded metadata only. No model
artifact, credential, dataset content, or job secret is returned.

## Adapter Boundary

SQL, Cosmos, and ML data-plane clients are explicit adapter slots in `AzureClients`. If an adapter
is absent, tools return `SERVICE_NOT_CONFIGURED` rather than guessing credentials, endpoints, or
SDK behavior.
