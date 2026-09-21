from __future__ import annotations

import base64
import os
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from azure.core.exceptions import HttpResponseError

from src.tools import compute, keyvault, network, resource_mgmt, storage


@dataclass
class FakeClients:
    resource: object
    compute: object
    storage: object


class FakeResourceGroups:
    def list(self):
        return [
            SimpleNamespace(id="/rg/1", name="rg-a", location="eastus", tags={"env": "dev"}),
            SimpleNamespace(id="/rg/2", name="rg-b", location="westus", tags={"env": "test"}),
        ]


class FakeVirtualMachines:
    def list(self, resource_group: str):
        if resource_group != "rg-a":
            raise AssertionError("unexpected resource group")
        return [
            SimpleNamespace(
                id="/vm/1",
                name="vm-a",
                location="eastus",
                type="Microsoft.Compute/virtualMachines",
                tags={},
            ),
            SimpleNamespace(
                id="/vm/2",
                name="vm-b",
                location="eastus",
                type="Microsoft.Compute/virtualMachines",
                tags={},
            ),
        ]

    def instance_view(self, resource_group: str, vm_name: str):
        if resource_group != "rg-a" or vm_name != "vm-a":
            raise AssertionError("unexpected vm target")
        return SimpleNamespace(
            statuses=[
                SimpleNamespace(code="ProvisioningState/succeeded", display_status="Provisioning succeeded"),
                SimpleNamespace(code="PowerState/running", display_status="VM running"),
            ]
        )

    def begin_start(self, resource_group: str, vm_name: str):
        if resource_group != "rg-a" or vm_name != "vm-a":
            raise AssertionError("unexpected vm target")
        return SimpleNamespace(name="start-operation")

    def begin_power_off(self, resource_group: str, vm_name: str):
        if resource_group != "rg-a" or vm_name != "vm-a":
            raise AssertionError("unexpected vm target")
        return SimpleNamespace(name="stop-operation")


class FakeStorageAccounts:
    def list_by_resource_group(self, resource_group: str):
        if resource_group != "rg-a":
            raise AssertionError("unexpected resource group")
        return [
            SimpleNamespace(
                id="/st/1",
                name="stacc1",
                location="eastus",
                kind="StorageV2",
                sku=SimpleNamespace(name="Standard_LRS"),
                tags={"env": "dev"},
            )
        ]

    def begin_create(self, resource_group: str, account_name: str, payload: dict):
        if resource_group != "rg-a" or account_name != "stacc2":
            raise AssertionError("unexpected storage create target")
        if payload.get("location") != "eastus":
            raise AssertionError("unexpected location")
        return SimpleNamespace(name="create-storage-operation")


class FakeNetworkCollection:
    def list(self, resource_group: str):
        if resource_group != "rg-a":
            raise AssertionError("unexpected network resource group")
        return [SimpleNamespace(id="/network/1", name="net-a", location="eastus", tags={})]

    def begin_create_or_update(self, resource_group: str, name: str, payload: dict):
        if resource_group != "rg-a" or name != "pip-a":
            raise AssertionError("unexpected public IP target")
        return SimpleNamespace(name="public-ip-operation", payload=payload)


class FakeVaults:
    def list_by_resource_group(self, resource_group: str):
        if resource_group != "rg-a":
            raise AssertionError("unexpected vault resource group")
        return [
            SimpleNamespace(
                id="/vault/1",
                name="vault-a",
                location="eastus",
                vault_uri="https://vault-a.vault.azure.net/",
                sku=SimpleNamespace(name="standard"),
                tenant_id="tenant-1",
                tags={"env": "test"},
            )
        ]


class _FakeBlobDownload:
    def __init__(self, content: bytes):
        self._content = content

    def readall(self) -> bytes:
        return self._content


class _FakeBlobContainerClient:
    def __init__(self):
        self.uploaded: dict[str, bytes] = {}

    def upload_blob(self, blob_name: str, payload: bytes, overwrite: bool = False):
        self.uploaded[blob_name] = payload
        return SimpleNamespace(etag="etag-1", overwrite=overwrite)

    def download_blob(self, blob_name: str):
        value = self.uploaded.get(blob_name, b"")
        return _FakeBlobDownload(value)


class _FakeBlobServiceClient:
    def __init__(self):
        self.container = _FakeBlobContainerClient()

    def get_container_client(self, container_name: str):
        if container_name != "container-a":
            raise AssertionError("unexpected container")
        return self.container


class ToolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {
                "AZURE_SUBSCRIPTION_ID": "sub-123",
                "MAX_RESULTS": "50",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    def _fake_clients(self) -> FakeClients:
        return FakeClients(
            resource=SimpleNamespace(resource_groups=FakeResourceGroups()),
            compute=SimpleNamespace(virtual_machines=FakeVirtualMachines()),
            storage=SimpleNamespace(storage_accounts=FakeStorageAccounts()),
        )

    def _fake_network_clients(self):
        clients = self._fake_clients()
        clients.network = SimpleNamespace(
            virtual_networks=FakeNetworkCollection(),
            network_security_groups=FakeNetworkCollection(),
            public_ip_addresses=FakeNetworkCollection(),
        )
        clients.keyvault = SimpleNamespace(vaults=FakeVaults())
        return clients

    def test_list_resource_groups_success(self) -> None:
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = resource_mgmt.list_resource_groups(limit=1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["resource_groups"][0]["name"], "rg-a")

    def test_list_virtual_machines_success(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = compute.list_virtual_machines(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["virtual_machines"][0]["name"], "vm-a")

    def test_list_storage_accounts_success(self) -> None:
        with patch.object(storage.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = storage.list_storage_accounts(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["storage_accounts"][0]["sku"], "Standard_LRS")

    def test_list_virtual_machines_validates_resource_group(self) -> None:
        result = compute.list_virtual_machines(resource_group="   ")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_list_storage_accounts_validates_resource_group(self) -> None:
        result = storage.list_storage_accounts(resource_group="")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_tool_error_is_sanitized(self) -> None:
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", side_effect=RuntimeError("sensitive internal message")):
            result = resource_mgmt.list_resource_groups()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "UNEXPECTED_ERROR")
        self.assertNotIn("sensitive", result["error"]["message"].lower())

    def test_timeout_error_is_sanitized(self) -> None:
        with patch.object(resource_mgmt, "run_with_timeout", side_effect=TimeoutError("late")):
            with patch.object(resource_mgmt.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
                result = resource_mgmt.list_resource_groups(limit=10)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TIMEOUT")

    def test_throttling_error_is_sanitized(self) -> None:
        throttled_error = HttpResponseError("Too many requests", status_code=429)
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", side_effect=throttled_error):
            result = resource_mgmt.list_resource_groups(limit=10)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "THROTTLED")

    def test_authorization_error_is_sanitized(self) -> None:
        forbidden_error = HttpResponseError("Forbidden", status_code=403)
        with patch.object(resource_mgmt.azure_clients, "get_azure_clients", side_effect=forbidden_error):
            result = resource_mgmt.list_resource_groups(limit=10)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "AUTHORIZATION_FAILED")

    def test_get_virtual_machine_status_success(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = compute.get_virtual_machine_status(resource_group="rg-a", vm_name="vm-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["power_state"], "running")
        self.assertEqual(result["vm_name"], "vm-a")

    def test_start_virtual_machine_requires_approval(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", side_effect=AssertionError("should not call azure")):
            result = compute.start_virtual_machine(resource_group="rg-a", vm_name="vm-a", has_explicit_approval=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_start_virtual_machine_with_approval(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = compute.start_virtual_machine(resource_group="rg-a", vm_name="vm-a", has_explicit_approval=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_stop_virtual_machine_with_approval(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = compute.stop_virtual_machine(resource_group="rg-a", vm_name="vm-a", has_explicit_approval=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_stop_virtual_machine_requires_approval(self) -> None:
        with patch.object(compute.azure_clients, "get_azure_clients", side_effect=AssertionError("should not call azure")):
            result = compute.stop_virtual_machine(resource_group="rg-a", vm_name="vm-a", has_explicit_approval=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_create_storage_account_requires_approval(self) -> None:
        with patch.object(storage.azure_clients, "get_azure_clients", side_effect=AssertionError("should not call azure")):
            result = storage.create_storage_account(
                resource_group="rg-a",
                account_name="stacc2",
                location="eastus",
                has_explicit_approval=False,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_create_storage_account_with_approval(self) -> None:
        with patch.object(storage.azure_clients, "get_azure_clients", return_value=self._fake_clients()):
            result = storage.create_storage_account(
                resource_group="rg-a",
                account_name="stacc2",
                location="eastus",
                has_explicit_approval=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_upload_blob_content_requires_approval(self) -> None:
        with patch.object(storage, "_build_blob_service_client", side_effect=AssertionError("should not build client")):
            result = storage.upload_blob_content(
                resource_group="rg-a",
                account_name="stacc2",
                container_name="container-a",
                blob_name="a.txt",
                content_base64=base64.b64encode(b"hello").decode("ascii"),
                has_explicit_approval=False,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_upload_blob_content_with_approval(self) -> None:
        blob_service = _FakeBlobServiceClient()
        with patch.object(storage, "_build_blob_service_client", return_value=blob_service):
            result = storage.upload_blob_content(
                resource_group="rg-a",
                account_name="stacc2",
                container_name="container-a",
                blob_name="a.txt",
                content_base64=base64.b64encode(b"hello").decode("ascii"),
                has_explicit_approval=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes_uploaded"], 5)

    def test_download_blob_content_with_approval(self) -> None:
        blob_service = _FakeBlobServiceClient()
        blob_service.container.upload_blob("a.txt", b"hello", overwrite=True)

        with patch.object(storage, "_build_blob_service_client", return_value=blob_service):
            result = storage.download_blob_content(
                resource_group="rg-a",
                account_name="stacc2",
                container_name="container-a",
                blob_name="a.txt",
                has_explicit_approval=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes_downloaded"], 5)
        self.assertEqual(base64.b64decode(result["content_base64"]), b"hello")

    def test_download_blob_content_requires_approval(self) -> None:
        with patch.object(storage, "_build_blob_service_client", side_effect=AssertionError("should not build client")):
            result = storage.download_blob_content(
                resource_group="rg-a",
                account_name="stacc2",
                container_name="container-a",
                blob_name="a.txt",
                has_explicit_approval=False,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_list_virtual_networks_success(self) -> None:
        with patch.object(network.azure_clients, "get_azure_clients", return_value=self._fake_network_clients()):
            result = network.list_virtual_networks(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["virtual_networks"][0]["name"], "net-a")

    def test_list_network_security_groups_success(self) -> None:
        with patch.object(network.azure_clients, "get_azure_clients", return_value=self._fake_network_clients()):
            result = network.list_network_security_groups(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["network_security_groups"][0]["name"], "net-a")

    def test_list_public_ip_addresses_success(self) -> None:
        with patch.object(network.azure_clients, "get_azure_clients", return_value=self._fake_network_clients()):
            result = network.list_public_ip_addresses(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["public_ip_addresses"][0]["name"], "net-a")

    def test_create_public_ip_requires_approval(self) -> None:
        with patch.object(network.azure_clients, "get_azure_clients", side_effect=AssertionError("should not call azure")):
            result = network.create_public_ip_address(
                resource_group="rg-a",
                public_ip_name="pip-a",
                location="eastus",
                has_explicit_approval=False,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "APPROVAL_REQUIRED")

    def test_create_public_ip_with_approval(self) -> None:
        with patch.object(network.azure_clients, "get_azure_clients", return_value=self._fake_network_clients()):
            result = network.create_public_ip_address(
                resource_group="rg-a",
                public_ip_name="pip-a",
                location="eastus",
                has_explicit_approval=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")

    def test_list_key_vaults_returns_metadata_only(self) -> None:
        with patch.object(keyvault.azure_clients, "get_azure_clients", return_value=self._fake_network_clients()):
            result = keyvault.list_key_vaults(resource_group="rg-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["key_vaults"][0]["name"], "vault-a")
        self.assertNotIn("secrets", result["key_vaults"][0])


if __name__ == "__main__":
    unittest.main()
