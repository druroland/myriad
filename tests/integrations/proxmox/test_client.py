"""Tests for the Proxmox API client."""

import pytest

from myriad.config import ProxmoxCredentials, ProxmoxIntegrationConfig
from myriad.integrations.proxmox import ProxmoxClient, ProxmoxVM


class TestProxmoxVM:
    """Tests for ProxmoxVM dataclass."""

    def test_uuid_generation(self):
        """Test UUID generation from node and vmid."""
        vm = ProxmoxVM(
            vmid=100,
            name="test-vm",
            node="pve",
            vm_type="qemu",
            status="running",
        )

        uuid = vm.uuid

        # Should be a valid UUID-like format
        assert len(uuid) == 36
        assert uuid.count("-") == 4
        # Should be deterministic
        assert vm.uuid == uuid

    def test_uuid_different_for_different_vmids(self):
        """Test that different vmids produce different UUIDs."""
        vm1 = ProxmoxVM(vmid=100, name="vm1", node="pve", vm_type="qemu", status="running")
        vm2 = ProxmoxVM(vmid=101, name="vm2", node="pve", vm_type="qemu", status="running")

        assert vm1.uuid != vm2.uuid

    def test_uuid_different_for_different_nodes(self):
        """Test that different nodes produce different UUIDs."""
        vm1 = ProxmoxVM(vmid=100, name="vm1", node="pve1", vm_type="qemu", status="running")
        vm2 = ProxmoxVM(vmid=100, name="vm1", node="pve2", vm_type="qemu", status="running")

        assert vm1.uuid != vm2.uuid


class TestMacAddressExtraction:
    """Tests for MAC address extraction from Proxmox config."""

    def setup_method(self):
        """Set up test fixtures."""
        config = ProxmoxIntegrationConfig(
            id="test",
            base_url="https://localhost:8006",
            credential_ref="proxmox.test",
        )
        credentials = ProxmoxCredentials(
            token_id="test@pam!test",
            token_secret="test-secret",
        )
        self.client = ProxmoxClient(config, credentials)

    def test_extract_qemu_mac_virtio_format(self):
        """Test extracting MAC from QEMU virtio format."""
        config = {
            "net0": "virtio=BC:24:11:AA:BB:CC,bridge=vmbr0",
        }

        macs = self.client._extract_mac_addresses(config, "qemu")

        assert len(macs) == 1
        assert macs[0] == "bc:24:11:aa:bb:cc"

    def test_extract_qemu_mac_macaddr_format(self):
        """Test extracting MAC from QEMU macaddr= format."""
        config = {
            "net0": "model=virtio,macaddr=BC:24:11:AA:BB:CC,bridge=vmbr0",
        }

        macs = self.client._extract_mac_addresses(config, "qemu")

        assert len(macs) == 1
        assert macs[0] == "bc:24:11:aa:bb:cc"

    def test_extract_lxc_mac_hwaddr_format(self):
        """Test extracting MAC from LXC hwaddr format."""
        config = {
            "net0": "name=eth0,hwaddr=BC:24:11:AA:BB:CC,bridge=vmbr0",
        }

        macs = self.client._extract_mac_addresses(config, "lxc")

        assert len(macs) == 1
        assert macs[0] == "bc:24:11:aa:bb:cc"

    def test_extract_multiple_nics(self):
        """Test extracting MACs from multiple network interfaces."""
        config = {
            "net0": "name=eth0,hwaddr=BC:24:11:AA:BB:CC,bridge=vmbr0",
            "net1": "name=eth1,hwaddr=BC:24:11:DD:EE:FF,bridge=vmbr1",
        }

        macs = self.client._extract_mac_addresses(config, "lxc")

        assert len(macs) == 2
        assert "bc:24:11:aa:bb:cc" in macs
        assert "bc:24:11:dd:ee:ff" in macs

    def test_extract_no_network_config(self):
        """Test with no network configuration."""
        config = {
            "memory": 2048,
            "cores": 2,
        }

        macs = self.client._extract_mac_addresses(config, "qemu")

        assert len(macs) == 0

    def test_extract_skips_non_net_keys(self):
        """Test that non-net keys are skipped."""
        config = {
            "net0": "name=eth0,hwaddr=BC:24:11:AA:BB:CC,bridge=vmbr0",
            "network": "some-other-setting",
            "netmask": "255.255.255.0",
        }

        macs = self.client._extract_mac_addresses(config, "lxc")

        assert len(macs) == 1


class TestMacNormalization:
    """Tests for MAC address normalization."""

    def setup_method(self):
        """Set up test fixtures."""
        config = ProxmoxIntegrationConfig(
            id="test",
            base_url="https://localhost:8006",
            credential_ref="proxmox.test",
        )
        credentials = ProxmoxCredentials(
            token_id="test@pam!test",
            token_secret="test-secret",
        )
        self.client = ProxmoxClient(config, credentials)

    def test_normalize_already_lowercase(self):
        """MAC already in correct format should be unchanged."""
        result = self.client._normalize_mac("aa:bb:cc:dd:ee:ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_uppercase(self):
        """Uppercase MAC should be lowercased."""
        result = self.client._normalize_mac("AA:BB:CC:DD:EE:FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_dashes(self):
        """MAC with dashes should use colons."""
        result = self.client._normalize_mac("aa-bb-cc-dd-ee-ff")
        assert result == "aa:bb:cc:dd:ee:ff"


class TestStatusMapping:
    """Tests for status to state mapping."""

    def test_map_running(self):
        """Test mapping 'running' status."""
        from myriad.models import VMState
        from myriad.services.proxmox_service import ProxmoxService

        result = ProxmoxService._map_status_to_state("running")
        assert result == VMState.RUNNING

    def test_map_stopped(self):
        """Test mapping 'stopped' status."""
        from myriad.models import VMState
        from myriad.services.proxmox_service import ProxmoxService

        result = ProxmoxService._map_status_to_state("stopped")
        assert result == VMState.STOPPED

    def test_map_unknown(self):
        """Test mapping unknown status."""
        from myriad.models import VMState
        from myriad.services.proxmox_service import ProxmoxService

        result = ProxmoxService._map_status_to_state("weird-status")
        assert result == VMState.UNKNOWN

    def test_map_case_insensitive(self):
        """Test that mapping is case insensitive."""
        from myriad.models import VMState
        from myriad.services.proxmox_service import ProxmoxService

        result = ProxmoxService._map_status_to_state("RUNNING")
        assert result == VMState.RUNNING
