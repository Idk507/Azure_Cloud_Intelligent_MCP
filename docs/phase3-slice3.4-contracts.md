# Phase 3 Slice 3.4 Contracts

Date: 2026-09-21

## Covered Tools

- `list_openai_deployments` (`read_only`)
- `deploy_openai_model` (`controlled_action`)
- `list_ai_foundry_agents` (`read_only`)
- `create_ai_foundry_agent` (`controlled_action`)
- `delete_ai_foundry_agent` (`controlled_action`)

## Safety And Adapter Boundaries

- Azure OpenAI deployment discovery uses bounded management-plane metadata only.
- Azure OpenAI deployment create/update requires explicit approval and reports only the intended
  account, deployment, model, and acceptance status.
- Foundry agent tools require an explicitly configured verified project adapter. Without that adapter,
  they return `AI_FOUNDRY_NOT_CONFIGURED` and do not guess endpoints or SDK behavior.
- Foundry create and delete operations require explicit approval.
- Instructions and other potentially sensitive agent content are never written to audit context.

## Manual Development Check

Use a non-production Cognitive Services account and a disposable deployment name. Verify one
read-only deployment inventory call, then one approved deployment operation and its Azure Activity
Log entry. For Foundry, configure and review the verified project adapter before enabling lifecycle
operations; validate project-scoped RBAC separately.
