from __future__ import annotations

import unittest

from src.policies import build_approval_plan, canonical_request_hash, execute_with_policy
from src.tool_registry import SafetyClass, ToolMetadata, get_tool_metadata


class PoliciesTestCase(unittest.TestCase):
    def test_canonical_request_hash_is_order_independent_and_binds_request_content(self) -> None:
        first = canonical_request_hash(
            tool_name="delete_azure_resource",
            scope="/subscriptions/sub-1",
            target={"resource_id": "/subscriptions/sub-1/resourceGroups/rg-a"},
            payload={"tags": {"owner": "platform", "cost": "42"}},
        )
        reordered = canonical_request_hash(
            tool_name="delete_azure_resource",
            scope="/subscriptions/sub-1",
            target={"resource_id": "/subscriptions/sub-1/resourceGroups/rg-a"},
            payload={"tags": {"cost": "42", "owner": "platform"}},
        )
        changed = canonical_request_hash(
            tool_name="delete_azure_resource",
            scope="/subscriptions/sub-1",
            target={"resource_id": "/subscriptions/sub-1/resourceGroups/rg-b"},
            payload={"tags": {"owner": "platform", "cost": "42"}},
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

    def test_approval_plan_returns_expiring_request_bound_receipt(self) -> None:
        plan = build_approval_plan(
            tool_name="delete_azure_resource",
            scope="/subscriptions/sub-1",
            target={"resource_id": "/subscriptions/sub-1/resourceGroups/rg-a"},
            payload={"api_version": "2024-01-01"},
            ttl_seconds=120,
        )

        self.assertTrue(plan.approval_id)
        self.assertEqual(plan.tool_name, "delete_azure_resource")
        self.assertEqual(plan.scope, "/subscriptions/sub-1")
        self.assertEqual((plan.expires_at - plan.created_at).total_seconds(), 120)
        self.assertEqual(
            plan.request_hash,
            canonical_request_hash(plan.tool_name, plan.scope, plan.target, plan.payload),
        )
    def test_read_only_tool_allowed_without_approval(self) -> None:
        metadata = get_tool_metadata("list_resource_groups")

        called = {"value": False}

        def callback() -> str:
            called["value"] = True
            return "ok"

        policy_result, result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=False,
            callback=callback,
        )

        self.assertTrue(policy_result.allowed)
        self.assertEqual(policy_result.reason, "read_only")
        self.assertTrue(called["value"])
        self.assertEqual(result, "ok")

    def test_controlled_action_denied_without_approval(self) -> None:
        metadata = ToolMetadata(
            name="delete_resource_group",
            description="Delete an Azure resource group.",
            safety_class=SafetyClass.CONTROLLED_ACTION,
            minimum_rbac_role="Contributor",
            owner_module="src.tools.resource_mgmt",
            docs_reference="docs/security-rbac.md",
        )

        called = {"value": False}

        def callback() -> str:
            called["value"] = True
            return "should-not-run"

        policy_result, result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=False,
            callback=callback,
        )

        self.assertFalse(policy_result.allowed)
        self.assertEqual(policy_result.reason, "explicit_approval_required")
        self.assertFalse(called["value"])
        self.assertIsNone(result)

    def test_controlled_action_allowed_with_approval(self) -> None:
        metadata = ToolMetadata(
            name="delete_resource_group",
            description="Delete an Azure resource group.",
            safety_class=SafetyClass.CONTROLLED_ACTION,
            minimum_rbac_role="Contributor",
            owner_module="src.tools.resource_mgmt",
            docs_reference="docs/security-rbac.md",
        )

        policy_result, result = execute_with_policy(
            tool_metadata=metadata,
            has_explicit_approval=True,
            callback=lambda: "approved",
        )

        self.assertTrue(policy_result.allowed)
        self.assertEqual(policy_result.reason, "approved")
        self.assertEqual(result, "approved")


if __name__ == "__main__":
    unittest.main()
