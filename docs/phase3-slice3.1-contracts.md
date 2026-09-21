# Phase 3 Slice 3.1 Contracts

Date: 2026-09-21

## Covered Tools

- `get_virtual_machine_status` (`read_only`)
- `start_virtual_machine` (`controlled_action`)
- `stop_virtual_machine` (`controlled_action`)
- `create_storage_account` (`controlled_action`)
- `upload_blob_content` (`controlled_action`)
- `download_blob_content` (`sensitive_data`)

## Safety And Approval Rules

1. Read-only tools run without approval but still enforce validation and audit logging.
2. Controlled-action and sensitive-data tools require `has_explicit_approval=true`.
3. When approval is missing, the tool returns:
   - `ok: false`
   - `error.code: APPROVAL_REQUIRED`
   - no Azure SDK action execution
4. All tools emit audit logs with `tool_name`, `status`, `duration_ms`, `safety_class`,
   `target_context`, `correlation_id`, and `error_code` on failures.

## Failure Paths Covered

- Validation failures for malformed names and missing inputs.
- Policy denial path for controlled actions and sensitive-data actions.
- Sanitized SDK failures through shared error normalization.

## Manual Check Guidance (Development Scope)

Use a dedicated non-production resource group and explicit approval only for one representative
controlled action (e.g., VM start). Confirm:

- tool response is `status: accepted` or `status: completed`
- redacted structured audit log entry exists
- Azure Activity Log shows operation against intended target
