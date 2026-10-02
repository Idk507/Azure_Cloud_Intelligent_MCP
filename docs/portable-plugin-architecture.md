# Portable Azure MCP Plugin Architecture

## Goal

Every user operates only on Azure resources their own Microsoft Entra identity is authorized to access. The plugin must never embed a subscription ID, Azure CLI token, client secret, or Foundry connection string.

## Two supported deployment modes

| Mode | Identity used for Azure calls | Subscription selection |
| --- | --- | --- |
| Local Codex MCP | `DefaultAzureCredential` from the user's machine: Azure CLI, developer tooling, or local environment credentials | User sets `AZURE_SUBSCRIPTION_ID`; the server starts without it for Foundry-only onboarding |
| Hosted ChatGPT MCP | Per-user Microsoft Entra OAuth token validated at the MCP resource server, then an on-behalf-of token for Azure Resource Manager and Foundry | User selects an accessible subscription in the plugin UI/session; never infer or share a server default |

`DefaultAzureCredential` is intentionally not the hosted multi-tenant identity mechanism. A hosted process can only see its own managed identity or its own environment, not a ChatGPT user's local Azure CLI session.

## Hosted publication requirements

1. Register a multi-tenant Microsoft Entra application for the MCP resource server and expose a delegated scope such as `access_as_user`.
2. Publish protected-resource metadata and OAuth authorization-server metadata, validate issuer, audience, signature, tenant allowlist, expiry, nonce/replay protections, and required scopes on every MCP request.
3. Use the validated user assertion only in an on-behalf-of exchange for Azure scopes. Do not accept caller-supplied bearer tokens as credentials or persist them in approval records, logs, or telemetry.
4. Maintain an encrypted, short-lived per-session credential and subscription context. The current implementation creates Azure SDK clients per hosted request; any future cache must be keyed by a non-secret session/tenant/subscription key, never process-wide by subscription alone.
5. Require explicit subscription selection before all ARM tools. A user may have several accessible subscriptions; selecting the first one is unsafe.
6. Preserve the existing plan/approval/execute workflow. OAuth authorizes identity; it does not approve a destructive Azure action.
7. Restrict production deployment identities to platform operations only. The shared managed identity must not become a substitute for each end user's Azure permissions.

## Hosted mode configuration

Set these only in the hosted service's secret/configuration store:

```text
MCP_AUTH_MODE=hosted
ENTRA_API_CLIENT_ID=<middle-tier application id>
ENTRA_API_CLIENT_SECRET=<middle-tier secret>
ENTRA_ALLOWED_TENANT_IDS=<comma-separated tenant ids>
MCP_PUBLIC_URL=https://<public-hostname>
```

The application registration must expose delegated `access_as_user`. Hosted mode validates its Entra JWT audience, signature, tenant, and scope, then builds an `OnBehalfOfCredential` from the request-scoped assertion. It never accepts tokens in tool inputs or logs them.

## Why this is not enabled by default

Hosted OAuth needs publisher-owned Entra application registration values, redirect URIs, consent policy, and allowed tenants. These are deployment security decisions, not values that can be safely generated in an open-source repository. The server fails closed in hosted mode until they are supplied.

## Sources

- [Azure Identity: DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/overview/azure/identity-readme?view=azure-python)
- [Azure Identity credential chains](https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains?tabs=dac)
- [MCP authorization](https://apps.extensions.modelcontextprotocol.io/api/documents/authorization.html)
- [ChatGPT developer mode and OAuth](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt)
