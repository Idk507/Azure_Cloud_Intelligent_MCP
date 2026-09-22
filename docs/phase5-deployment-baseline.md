# Phase 5 Deployment Baseline

## Local Validation

1. Build the image: `docker build --tag azure-cloud-intelligence-mcp:local .`
2. Run it with a runtime subscription value and verify `http://localhost:8000/health`.
3. Run the MCP smoke test against the local service before enabling controlled actions.

## Azure Container Apps

- Review [docs/azure-crud-matrix.md](azure-crud-matrix.md) before deployment. The service exposes
  verified operations only; it is not a universal Azure CRUD API.
- Generic control-plane CRUD is available through resource-ID tools, but each call still requires
  the correct provider API version, payload schema, provider-specific RBAC, and explicit approval
  for create/update/delete.
- Use `infra/main.bicep` with `infra/main.bicepparam.example` copied to a deployment-specific parameter file.
- Push an immutable image tag or digest to a private Azure Container Registry.
- Deploy with a system-assigned managed identity and grant only the resource roles required by the enabled tools.
- Keep service-principal secrets and tokens out of application settings; use Managed Identity and Key Vault-backed configuration for any future secret settings.
- Keep ingress HTTPS-only on port 8000 and validate `/health` before connecting an MCP client.

## CI

`.github/workflows/ci.yml` runs compilation, the test suite, and a container build on pushes and pull requests.

## Remaining Production Gates

- Do not enable or advertise an operation until its provider-specific CRUD contract, RBAC, approval,
  rollback, tests, and live evidence are recorded in the CRUD matrix.
- Configure a real private registry and non-production Container Apps environment.
- Run Bicep what-if/preview and deploy to a dedicated non-production resource group.
- Verify managed identity RBAC, logs, alert routing, rollback, and read-only MCP connectivity before controlled actions.
