from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.tools import governance


class GovernanceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "sub-123"})
        self.env.start()
        assignment = SimpleNamespace(id="/role/1", name="role-1", principal_id="principal", role_definition_id="/definition", scope="/subscriptions/sub-123", principal_type="ServicePrincipal")
        definition = SimpleNamespace(id="/policy/1", name="policy-1", display_name="Policy", policy_type="BuiltIn", mode="All", description="safe")
        policy_assignment = SimpleNamespace(id="/assignment/1", name="assignment-1", display_name="Assignment", policy_definition_id="/policy/1", scope="/subscriptions/sub-123", enforcement_mode="Default")
        self.clients = SimpleNamespace(authorization=SimpleNamespace(role_assignments=SimpleNamespace(list_for_scope=lambda scope, filter: [assignment])), policy=SimpleNamespace(policy_definitions=SimpleNamespace(list_by_subscription=lambda: [definition]), policy_assignments=SimpleNamespace(list_for_scope=lambda scope: [policy_assignment])))
        compliance = SimpleNamespace(resource_id="/resource/1", resource_group="rg-a", resource_type="Microsoft.Compute/virtualMachines", compliance_state="Compliant", policy_assignment_id="/assignment/1", policy_definition_id="/policy/1", timestamp="now")
        self.clients.policy_insights = SimpleNamespace(policy_states=SimpleNamespace(list_query_results_for_subscription=lambda subscription, state, top: SimpleNamespace(value=[compliance]), list_query_results_for_resource_group=lambda subscription, group, state, top: SimpleNamespace(value=[compliance])))

    def tearDown(self) -> None:
        self.env.stop()

    def test_lists_bounded_governance_metadata(self) -> None:
        with patch.object(governance.azure_clients, "get_azure_clients", return_value=self.clients):
            scope = "/subscriptions/sub-123"
            self.assertTrue(governance.list_role_assignments(scope)["ok"])
            self.assertTrue(governance.list_policy_definitions(scope)["ok"])
            self.assertTrue(governance.list_policy_assignments(scope)["ok"])
            self.assertTrue(governance.list_policy_compliance_states(scope)["ok"])

    def test_rejects_foreign_subscription_scope_before_azure(self) -> None:
        with patch.object(governance.azure_clients, "get_azure_clients", side_effect=AssertionError("Azure must not be called")):
            result = governance.list_role_assignments("/subscriptions/other")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")
