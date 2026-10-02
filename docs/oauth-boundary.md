# OAuth And Shared-Deployment Boundary

Date: 2026-09-21

## Current Deployment Assumption

The local and single-tenant development deployment uses Azure identity supplied through
`DefaultAzureCredential` or Managed Identity. The MCP server trusts the hosting boundary and does
not implement a second OAuth token-validation layer.

## Shared Or Multi-Tenant Deployment Requirement

Before exposing the server to multiple tenants or an untrusted shared MCP client, add an ingress
or middleware authorization boundary that validates:

- issuer and tenant allowlist
- audience/client ID
- signature and key rotation metadata
- expiry, not-before, and replay protections
- scope/role claims mapped to tool safety class and Azure scope

The MCP tool policy remains necessary after token validation; a valid user token alone must not
bypass explicit approval for controlled actions. The required local-versus-hosted identity split,
per-user subscription selection, and publisher configuration are specified in
[portable-plugin-architecture.md](portable-plugin-architecture.md).

## Decision

OAuth/token validation is mandatory before hosted or public multi-tenant publication. The current
implementation supports portable local onboarding with `DefaultAzureCredential`, but is not a
hosted multi-tenant OAuth resource server yet; it must fail closed rather than using a shared
Azure identity on behalf of arbitrary users.
