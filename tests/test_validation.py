from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.validation import (
    AzureLocationInput,
    AzureResourceIdInput,
    AzureScopeInput,
    BlobTransferInput,
    PaginationInput,
    ResourceGroupInput,
    StorageAccountCreateInput,
    VirtualMachineTargetInput,
)


class ValidationTestCase(unittest.TestCase):
    def test_resource_group_validation_accepts_valid_value(self) -> None:
        model = ResourceGroupInput(resource_group="rg-prod-01")
        self.assertEqual(model.resource_group, "rg-prod-01")

    def test_resource_group_validation_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            ResourceGroupInput(resource_group=" ")

    def test_pagination_validation(self) -> None:
        self.assertEqual(PaginationInput(limit=3).limit, 3)
        with self.assertRaises(ValidationError):
            PaginationInput(limit=0)

    def test_scope_and_resource_id_validation(self) -> None:
        scope = AzureScopeInput(scope="/subscriptions/abc/resourceGroups/rg1")
        resource_id = AzureResourceIdInput(resource_id="/subscriptions/abc/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/st1")

        self.assertTrue(scope.scope.startswith("/subscriptions/"))
        self.assertTrue(resource_id.resource_id.startswith("/subscriptions/"))

        with self.assertRaises(ValidationError):
            AzureScopeInput(scope="subscription/abc")
        with self.assertRaises(ValidationError):
            AzureResourceIdInput(resource_id="resourceGroups/rg1")

    def test_location_validation(self) -> None:
        model = AzureLocationInput(location="EastUS2")
        self.assertEqual(model.location, "eastus2")

        with self.assertRaises(ValidationError):
            AzureLocationInput(location="invalid location")

    def test_virtual_machine_target_validation(self) -> None:
        model = VirtualMachineTargetInput(resource_group="rg-a", vm_name="vm-a")
        self.assertEqual(model.resource_group, "rg-a")
        self.assertEqual(model.vm_name, "vm-a")

        with self.assertRaises(ValidationError):
            VirtualMachineTargetInput(resource_group="rg-a", vm_name="")

    def test_storage_create_validation(self) -> None:
        model = StorageAccountCreateInput(resource_group="rg-a", account_name="stacc2", location="EastUS")
        self.assertEqual(model.account_name, "stacc2")
        self.assertEqual(model.location, "eastus")

        with self.assertRaises(ValidationError):
            StorageAccountCreateInput(resource_group="rg-a", account_name="UPPERCASE")

    def test_blob_transfer_validation(self) -> None:
        model = BlobTransferInput(
            resource_group="rg-a",
            account_name="stacc2",
            container_name="container-a",
            blob_name="path/file.txt",
        )
        self.assertEqual(model.container_name, "container-a")

        with self.assertRaises(ValidationError):
            BlobTransferInput(
                resource_group="rg-a",
                account_name="stacc2",
                container_name="Invalid.Container",
                blob_name="x",
            )


if __name__ == "__main__":
    unittest.main()
