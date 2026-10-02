# Self-Hosted Security Checklist

- Authenticate through Azure CLI, managed identity, or a secret manager-backed Azure Identity configuration. Never paste access tokens, client secrets, or connection strings into MCP tools or ChatGPT.
- Select an explicit subscription with `AZURE_SUBSCRIPTION_ID`; do not rely on an arbitrary default subscription.
- Grant least-privilege Azure RBAC to the identity running the server. See [security-rbac.md](security-rbac.md).
- Use private HTTPS exposure or a secure MCP tunnel. Do not publish an unauthenticated developer tunnel as a production service.
- Leave `MCP_AUTH_MODE=local` for a personal local server. Enable hosted mode only after configuring the Entra OAuth/OBO requirements in [portable-plugin-architecture.md](portable-plugin-architecture.md).
- Review audit-safe logs and telemetry by correlation ID. Do not add payloads, secret values, or raw bearer tokens to logging.
- Verify all controlled actions use the plan/approval/execute workflow.
