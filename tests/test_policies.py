from __future__ import annotations

import unittest

from src.policies import execute_with_policy
from src.tool_registry import SafetyClass, ToolMetadata, get_tool_metadata


class PoliciesTestCase(unittest.TestCase):
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
