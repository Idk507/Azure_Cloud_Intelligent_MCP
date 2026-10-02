# Runbook: MCP Tool Error Rate or Latency

## Meaning

Users may be unable to complete Azure MCP operations, or responses may be slow. Do not retry controlled actions blindly: a timeout can leave the Azure-side outcome unknown.

## First checks

1. Check the Container App revision health and `/health`; roll back to the prior healthy revision if the new revision is not ready.
2. Query structured logs by `correlation_id` and inspect `tool_name`, `status`, `error_code`, and `duration_ms`. Do not search for or request payloads, credentials, or secret values.
3. Check the telemetry snapshot for the affected tool's success/error count and duration total. If an OTLP endpoint is configured, inspect the corresponding `azure_mcp.tool_call` span.

## Triage

- `AUTHORIZATION_FAILED` or `FORBIDDEN`: verify the Container App managed identity's least-privilege role at the exact resource scope; do not add Owner as a workaround.
- `THROTTLED`, `TIMEOUT`, or transient Azure failures: pause repeated mutating calls, capture the correlation ID, and inspect the Azure operation or Activity Log before retrying.
- Validation or approval failures: correct the typed input or generate a fresh matching approval plan; never reuse an expired or consumed receipt.

## Escalation and rollback

Escalate with the correlation ID, tool name, error code, deployment revision, and approximate time window. For a faulty release, route traffic back to the prior revision and preserve redacted logs and trace IDs for follow-up.
