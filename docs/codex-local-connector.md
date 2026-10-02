# Connect a Self-Hosted Server to Codex

Codex can use a local MCP server directly. Run the service after authenticating with `az login` and set `AZURE_SUBSCRIPTION_ID` to the subscription you intend to operate on.

Use the streamable HTTP endpoint:

```text
http://127.0.0.1:8000/mcp
```

Start with read-only discovery tools. For create, update, delete, start, or stop operations, first call the corresponding `plan_*` tool, review the target and payload, and provide the resulting single-use `approval_id` only to the matching execution tool.

This local model is intentionally preferable for individual users: Azure sees the identity authenticated on their own computer, and Azure RBAC remains the source of authorization.
