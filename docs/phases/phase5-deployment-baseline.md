# Phase 5 Deployment Baseline

## Local Validation

1. Build the image: `docker build --tag azure-cloud-intelligence-mcp:local .`
2. Run it with a runtime subscription value and verify `http://localhost:8000/health`.
3. Run the MCP smoke test against the local service before enabling controlled actions.

## Azure Container Apps

- Review [the Azure CRUD matrix](azure-crud-matrix.md) before deployment. The service exposes
  verified operations only; it is not a universal Azure CRUD API.
- Generic control-plane CRUD is available through resource-ID tools, but each call still requires
  the correct provider API version, payload schema, provider-specific RBAC, and explicit approval
  for create/update/delete.
- Use `infra/main.bicep` with `infra/main.bicepparam.example` copied to a deployment-specific parameter file.
- Set `applicationInsightsName` to deploy a workspace-based Application Insights component alongside the
  Container Apps baseline, then connect that component to the Foundry project in Foundry portal > Traces.
  Foundry enables server-side tracing after this connection; keep the component connection string out of
  application settings and logs.
- Push an immutable image tag or digest to a private Azure Container Registry.
- Deploy with a system-assigned managed identity and grant only the resource roles required by the enabled tools.
- Keep service-principal secrets and tokens out of application settings; use Managed Identity and Key Vault-backed configuration for any future secret settings.
- Keep ingress HTTPS-only on port 8000 and validate `/health` before connecting an MCP client.
- To export traces, set `OTEL_EXPORTER_OTLP_ENDPOINT`; to export RED metrics, set
  `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. Configure each with a collector endpoint appropriate for
  the target Application Insights workspace. Neither setting accepts or logs an instrumentation
  key or connection string.

## CI

`.github/workflows/ci.yml` runs compilation, tests, Bicep compilation, whitespace validation, and
a container build on pushes and pull requests.

## Remaining Production Gates

- Do not enable or advertise an operation until its provider-specific CRUD contract, RBAC, approval,
  rollback, tests, and live evidence are recorded in the CRUD matrix.
- Configure a real private registry and non-production Container Apps environment.
- Run Bicep what-if/preview and deploy to a dedicated non-production resource group.
- Verify managed identity RBAC, logs, alert routing, rollback, and read-only MCP connectivity before controlled actions.
- Configure symptom-based alerts for sustained tool error rate and p99 duration, and attach [the tool error/latency runbook](runbooks/mcp-tool-error-or-latency.md). Alert routing requires the target non-production Azure environment and is not created by this repository alone.
