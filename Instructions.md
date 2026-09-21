# Instructions for Azure Cloud Intelligence MCP

## Purpose

Build a secure Python Model Context Protocol (MCP) server that lets MCP-capable
clients inspect Azure resources and perform explicitly approved Azure operations.
The server must favor safe discovery and useful diagnostics over broad, autonomous
resource management.

## Source Of Truth

Use these documents in this order when requirements differ:

1. `scope.md` defines product intent, required capabilities, security constraints, and the
   reference tool inventory.
2. `plan.md` defines the implementation specification, phases, acceptance criteria, and
   verification gates.
3. `IMPLEMENTATION_PLAN.md` is the original detailed roadmap and supporting context.
4. `deep-research-report.md` supplies background, examples, and references; verify time-sensitive
   platform details against current official documentation before implementing them.

Update `plan.md` when a delivery decision changes. Do not silently expand scope beyond a phase's
acceptance criteria.

## Target Architecture

- Implement the server in Python 3.11 or later using the official MCP Python SDK and FastMCP.
- Use streamable HTTP at the `/mcp` endpoint. Keep the service stateless so it can scale horizontally.
- Organize code by responsibility: configuration, credential creation, Azure-client factories,
  tool modules, cross-cutting utilities, telemetry, and tests.
- Use Azure SDKs or documented Azure REST APIs. Do not shell out to `az` for normal runtime tool
  behavior; Azure CLI is for local authentication and operational setup only.
- Use typed Pydantic models and type annotations for inputs and structured, JSON-serializable
  outputs. Tool names and schemas are public contracts: version or preserve them deliberately.
- Run long-running Azure operations asynchronously, report bounded progress where MCP supports it,
  and return an operation identifier or final status rather than blocking indefinitely.

## Azure Identity And Configuration

- Local development: authenticate with `DefaultAzureCredential` and an authenticated Azure CLI session.
- Non-local environments: prefer user-assigned or system-assigned Managed Identity.
- Allow `ClientSecretCredential` only for explicitly configured automation where managed identity is
  unavailable; obtain the secret from Azure Key Vault or the deployment secret store.
- Require `AZURE_SUBSCRIPTION_ID`; make default location, logging level, and timeouts configurable.
- Never commit `.env` files, credentials, resource IDs containing sensitive data, access tokens, or
  Key Vault secret values. `.env.example` contains placeholders only.
- Validate subscription, tenant, resource group, region, and target resource before an action.

## Tool Safety Contract

### Read Operations

- Read tools are the default. They must use the least-privileged Azure role, paginate or bound
  results, and return only fields needed by the caller.
- Return normalized objects with resource identifiers, display names, location, state, and a concise
  user-facing summary where applicable.
- Convert Azure SDK exceptions into sanitized, actionable error responses. Preserve detailed stack
  traces only in protected logs.

### Write, Expensive, And Sensitive Operations

- Any create, update, delete, deploy, start, stop, scale, secret-write, query-execution, or
  pipeline-run operation is a controlled action.
- Controlled actions require the MCP client's current supported approval mechanism before Azure is
  called. Treat client approval as necessary but not sufficient: enforce server-side validation,
  scope restrictions, and Azure RBAC as well.
- Show the intended target and material impact in the tool description/result. Use idempotency or
  explicit existence checks whenever the Azure API supports them.
- Never return Key Vault secret values, connection strings, tokens, or credentials by default.
  Secret retrieval must be a separately reviewed capability with redaction and audit requirements.
- Do not add autonomous remediation, schedule-based actions, or multi-cloud support until the
  planned future backlog is explicitly approved.

## Security And Governance

- Assign Azure RBAC at the narrowest practical scope and role. Never require Subscription Owner as
  a default.
- Maintain a documented tool-to-RBAC mapping before adding a new Azure domain.
- Validate user-controlled identifiers, names, resource IDs, Kusto queries, SQL statements, and
  blob paths before using them. Constrain data-query tools to read-only queries unless a separate
  controlled-action design is approved.
- Redact sensitive parameters and outputs before structured logging. Logs record correlation ID,
  tool name, non-sensitive target context, duration, status, and sanitized failure category.
- Use TLS for remote connections. Use ngrok only for local development; prefer a managed Azure
  endpoint or approved outbound tunnel for production.
- Document security-relevant architecture changes and unresolved threat-model questions.

## Reliability And Observability

- Use explicit timeouts and Azure SDK retry policies for transient failures such as 429 and 5xx
  responses. Retry only idempotent operations or operations protected by idempotency semantics.
- Each tool must handle not-found, authentication/authorization, validation, throttling, timeout,
  and unexpected-service failures without crashing the MCP process.
- Emit structured logs and OpenTelemetry-compatible traces for every tool call. Do not put raw tool
  arguments or sensitive output into telemetry.
- Production deployment sends logs, metrics, and traces to Azure Monitor/Application Insights or
  another approved central system. Monitor call volume, latency, error rate, and controlled-action
  outcomes.

## Development Rules

- Work in small vertical slices. Complete tests and focused verification before beginning the next
  tool domain.
- Prefer an explicit service-specific module over a generic abstraction until at least three real
  use cases prove the abstraction is needed.
- Every MCP tool has: a stable name; typed and validated input; a clear docstring/description;
  minimal RBAC; sanitized errors; audit-safe logging; and unit tests for success plus failure.
- Mock Azure clients in unit tests. Keep subscription-bound integration tests opt-in and protect
  them with dedicated test scopes/resources.
- Before merging a phase: run formatting/linting, type checking, unit tests, MCP protocol tests,
  and the phase-specific manual or integration check.
- Keep dependency versions pinned or bounded deliberately. Verify SDK and MCP transport behavior
  against current official documentation before choosing API-specific implementation details.

## Documentation Rules

- Keep `README.md`, architecture, security, tools, deployment, and troubleshooting documentation
  aligned with shipped behavior.
- Record material architecture decisions, including rejected alternatives, in ADRs once the
  `docs/` structure is created.
- Document each tool's input, output, Azure permission, safety class, failure modes, and examples.
- Update the corresponding phase status and acceptance evidence in `plan.md` when work is completed.

## Definition Of Done

A change is complete only when it meets its phase acceptance criteria, passes the documented
verification commands, protects secrets, respects least privilege, leaves the server operational,
and updates affected documentation.
