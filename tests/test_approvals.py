from __future__ import annotations

import unittest
from datetime import timedelta

from src.approvals import InMemoryApprovalStore
from src.policies import build_approval_plan


class ApprovalStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_approval_plan(
            tool_name="delete_azure_resource",
            scope="/subscriptions/sub-1",
            target={"resource_id": "/subscriptions/sub-1/resourceGroups/rg-a"},
            payload={"api_version": "2024-01-01"},
            ttl_seconds=120,
        )
        self.store = InMemoryApprovalStore()
        self.store.issue(self.plan)

    def test_consumes_matching_approval_once(self) -> None:
        approved = self.store.consume(
            self.plan.approval_id,
            self.plan.tool_name,
            self.plan.scope,
            self.plan.target,
            self.plan.payload,
        )
        replay = self.store.consume(
            self.plan.approval_id,
            self.plan.tool_name,
            self.plan.scope,
            self.plan.target,
            self.plan.payload,
        )

        self.assertTrue(approved.allowed)
        self.assertEqual(replay.reason, "approval_already_consumed")

    def test_rejects_mismatched_request_and_expired_approval(self) -> None:
        mismatch = self.store.consume(
            self.plan.approval_id,
            self.plan.tool_name,
            self.plan.scope,
            self.plan.target,
            {"api_version": "2024-02-01"},
        )
        expired = self.store.consume(
            self.plan.approval_id,
            self.plan.tool_name,
            self.plan.scope,
            self.plan.target,
            self.plan.payload,
            now=self.plan.expires_at + timedelta(seconds=1),
        )

        self.assertEqual(mismatch.reason, "approval_request_mismatch")
        self.assertEqual(expired.reason, "approval_expired")


if __name__ == "__main__":
    unittest.main()
