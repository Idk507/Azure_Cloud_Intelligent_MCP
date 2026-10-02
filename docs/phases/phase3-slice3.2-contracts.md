# Phase 3 Slice 3.2 Contracts

Date: 2026-09-21

## Covered Tools

- `list_virtual_networks` (`read_only`)
- `list_network_security_groups` (`read_only`)
- `list_public_ip_addresses` (`read_only`)
- `create_public_ip_address` (`controlled_action`)
- `list_key_vaults` (`read_only`, metadata only)

## Safety Boundary

- Networking inventory is bounded by resource group and page limit.
- Public IP creation requires explicit approval before the Azure SDK is called.
- Key Vault tools never retrieve or return secret, key, or certificate values.
- All tools use shared error normalization and redacted structured audit logs.

## Manual Development Check

Use a non-production resource group. Run one read-only network inventory call first. For the
controlled path, create one disposable public IP only after explicit approval, then verify the
intended target in the Azure Activity Log and delete it through an approved operational process.
