# Microsoft Foundry Agent Service

This server uses `azure-ai-projects` for Foundry Agent Service data-plane operations.
It supports bounded list/get reads and approved create/update/delete operations for
agent definitions. Agent creation requires a deployed model name because Foundry's
Agent Service requires a model for a new agent.

## Human approval and hooks

Every mutation requires `has_explicit_approval=true`; the result contains a
correlation-bound approval receipt. The server emits redacted lifecycle events to
registered in-process hooks (`tool.success`, `tool.error`, and
`tool.approval_required`) and produces structured JSON audit logs. Hooks are
observers only: exceptions in a hook cannot alter Azure operations.

## Observability and privacy

Connect the Foundry project to Application Insights to enable Foundry's server-side
traces. This MCP server deliberately redacts sensitive fields before its own logs or
hooks. Do not include credentials, prompts containing secrets, or raw tool results in
hook destinations; Foundry tracing can capture those values.

## RBAC

Use the `Foundry User` role at project scope for agent operations. To view telemetry,
also grant `Log Analytics Reader` on the connected Application Insights resource.

References:

- [Foundry Agent Service quickstart](https://learn.microsoft.com/en-us/azure/ai-services/agents/quickstart)
- [Set up tracing in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup)
