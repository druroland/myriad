"""Tests for the ProxmoxService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.config import (
    IntegrationsConfig,
    ProxmoxCredentials,
    ProxmoxIntegrationConfig,
    SecretsConfig,
    Settings,
)
from myriad.integrations.proxmox import ProxmoxVM
from myriad.models import (
    Host,
    Hypervisor,
    HypervisorStatus,
    HypervisorType,
    VirtualMachine,
    VMState,
    VMType,
)
from myriad.services import ProxmoxService


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings with Proxmox integration."""
    return Settings(
        integrations=IntegrationsConfig(
            proxmox=[
                ProxmoxIntegrationConfig(
                    id="proxmox-test",
                    base_url="https://192.168.1.10:8006",
                    credential_ref="proxmox.test",
                    location_id="home-lan",
                    verify_ssl=False,
                )
            ]
        ),
        secrets=SecretsConfig(
            proxmox={
                "test": ProxmoxCredentials(
                    token_id="root@pam!myriad",
                    token_secret="test-secret-uuid",
                )
            }
        ),
    )


class TestProxmoxServiceConfig:
    """Tests for ProxmoxService configuration handling."""

    @pytest.mark.asyncio
    async def test_sync_invalid_integration_id(self, db: AsyncSession, mock_settings: Settings):
        """Test sync with invalid integration ID raises error."""
        service = ProxmoxService(db, mock_settings)

        with pytest.raises(ValueError, match="not found"):
            await service.sync_proxmox("nonexistent-integration")

    @pytest.mark.asyncio
    async def test_sync_invalid_credential_ref(self, db: AsyncSession):
        """Test sync with invalid credential reference raises error."""
        settings = Settings(
            integrations=IntegrationsConfig(
                proxmox=[
                    ProxmoxIntegrationConfig(
                        id="proxmox-test",
                        base_url="https://localhost:8006",
                        credential_ref="invalid.format.ref",  # Invalid format
                    )
                ]
            ),
            secrets=SecretsConfig(),
        )
        service = ProxmoxService(db, settings)

        with pytest.raises(ValueError, match="Invalid credential reference"):
            await service.sync_proxmox("proxmox-test")

    @pytest.mark.asyncio
    async def test_sync_missing_credentials(self, db: AsyncSession):
        """Test sync with missing credentials raises error."""
        settings = Settings(
            integrations=IntegrationsConfig(
                proxmox=[
                    ProxmoxIntegrationConfig(
                        id="proxmox-test",
                        base_url="https://localhost:8006",
                        credential_ref="proxmox.missing",
                    )
                ]
            ),
            secrets=SecretsConfig(),
        )
        service = ProxmoxService(db, settings)

        with pytest.raises(ValueError, match="not found"):
            await service.sync_proxmox("proxmox-test")


class TestProxmoxServiceHypervisor:
    """Tests for ProxmoxService hypervisor management."""

    @pytest.mark.asyncio
    async def test_ensure_hypervisor_creates_new(self, db: AsyncSession, mock_settings: Settings):
        """Test that ensure_hypervisor creates a new hypervisor."""
        service = ProxmoxService(db, mock_settings)

        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )

        assert hypervisor.id == "test-proxmox"
        assert hypervisor.name == "Test Proxmox"
        assert hypervisor.hypervisor_type == HypervisorType.PROXMOX
        assert hypervisor.api_url == "https://192.168.1.10:8006"
        assert hypervisor.pve_version == "8.4.14"
        assert hypervisor.status == HypervisorStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_ensure_hypervisor_updates_existing(
        self, db: AsyncSession, mock_settings: Settings
    ):
        """Test that ensure_hypervisor updates an existing hypervisor."""
        service = ProxmoxService(db, mock_settings)

        # Create first
        hypervisor1 = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.0",
            node_name=None,
        )
        await db.flush()

        # Update
        hypervisor2 = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",  # Updated version
            node_name="pve",
        )

        assert hypervisor1.id == hypervisor2.id
        assert hypervisor2.pve_version == "8.4.14"
        assert hypervisor2.node_name == "pve"


class TestProxmoxServiceVM:
    """Tests for ProxmoxService VM management."""

    @pytest.mark.asyncio
    async def test_upsert_vm_creates_new(self, db: AsyncSession, mock_settings: Settings):
        """Test that upsert_vm creates a new VM."""
        service = ProxmoxService(db, mock_settings)

        # Create hypervisor first
        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        pve_vm = ProxmoxVM(
            vmid=100,
            name="test-vm",
            node="pve",
            vm_type="qemu",
            status="running",
            maxmem=2147483648,  # 2GB
            maxdisk=10737418240,  # 10GB
            uptime=3600,
            mac_addresses=["bc:24:11:aa:bb:cc"],
        )

        vm, created = await service._upsert_vm(hypervisor, pve_vm)

        assert created is True
        assert vm.name == "test-vm"
        assert vm.vmid == 100
        assert vm.vm_type == VMType.QEMU
        assert vm.state == VMState.RUNNING
        assert vm.memory_mb == 2048
        assert vm.uptime_seconds == 3600

    @pytest.mark.asyncio
    async def test_upsert_vm_updates_existing(self, db: AsyncSession, mock_settings: Settings):
        """Test that upsert_vm updates an existing VM."""
        service = ProxmoxService(db, mock_settings)

        # Create hypervisor
        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        # Create initial VM
        pve_vm = ProxmoxVM(
            vmid=100,
            name="test-vm",
            node="pve",
            vm_type="qemu",
            status="running",
            maxmem=2147483648,
        )
        vm1, created1 = await service._upsert_vm(hypervisor, pve_vm)
        await db.flush()
        assert created1 is True

        # Update VM
        pve_vm.status = "stopped"
        pve_vm.maxmem = 4294967296  # 4GB
        vm2, created2 = await service._upsert_vm(hypervisor, pve_vm)

        assert created2 is False
        assert vm1.id == vm2.id
        assert vm2.state == VMState.STOPPED
        assert vm2.memory_mb == 4096

    @pytest.mark.asyncio
    async def test_upsert_lxc_container(self, db: AsyncSession, mock_settings: Settings):
        """Test creating an LXC container."""
        service = ProxmoxService(db, mock_settings)

        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        pve_vm = ProxmoxVM(
            vmid=101,
            name="pihole",
            node="pve",
            vm_type="lxc",
            status="running",
        )

        vm, created = await service._upsert_vm(hypervisor, pve_vm)

        assert created is True
        assert vm.vm_type == VMType.LXC


class TestProxmoxServiceHostLinking:
    """Tests for VM-to-Host linking."""

    @pytest.mark.asyncio
    async def test_link_vm_to_host(self, db: AsyncSession, mock_settings: Settings):
        """Test linking a VM to a host by MAC address."""
        service = ProxmoxService(db, mock_settings)

        # Create a host
        host = Host(
            mac_address="bc:24:11:aa:bb:cc",
            hostname="test-host",
        )
        db.add(host)
        await db.flush()

        # Create hypervisor and VM
        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        pve_vm = ProxmoxVM(
            vmid=100,
            name="test-vm",
            node="pve",
            vm_type="qemu",
            status="running",
            mac_addresses=["bc:24:11:aa:bb:cc"],
        )
        vm, _ = await service._upsert_vm(hypervisor, pve_vm)
        await db.flush()

        # Link VM to host
        linked = await service._link_vm_to_host(vm, "bc:24:11:aa:bb:cc", "home-lan")

        assert linked is True
        assert vm.host_id == host.id

    @pytest.mark.asyncio
    async def test_link_vm_no_matching_host(self, db: AsyncSession, mock_settings: Settings):
        """Test linking when no host matches the MAC address."""
        service = ProxmoxService(db, mock_settings)

        # Create hypervisor and VM (no host with matching MAC)
        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        pve_vm = ProxmoxVM(
            vmid=100,
            name="test-vm",
            node="pve",
            vm_type="qemu",
            status="running",
        )
        vm, _ = await service._upsert_vm(hypervisor, pve_vm)
        await db.flush()

        # Try to link with non-existent MAC
        linked = await service._link_vm_to_host(vm, "aa:bb:cc:dd:ee:ff", "home-lan")

        assert linked is False
        assert vm.host_id is None


class TestProxmoxServiceStats:
    """Tests for VM statistics."""

    @pytest.mark.asyncio
    async def test_get_vm_stats_empty(self, db: AsyncSession, mock_settings: Settings):
        """Test stats with no VMs."""
        service = ProxmoxService(db, mock_settings)

        stats = await service.get_vm_stats()

        assert stats["total"] == 0
        assert stats["running"] == 0
        assert stats["stopped"] == 0
        assert stats["qemu"] == 0
        assert stats["lxc"] == 0

    @pytest.mark.asyncio
    async def test_get_vm_stats_with_vms(self, db: AsyncSession, mock_settings: Settings):
        """Test stats with various VMs."""
        service = ProxmoxService(db, mock_settings)

        # Create hypervisor
        hypervisor = await service._ensure_hypervisor(
            integration_id="test-proxmox",
            name="Test Proxmox",
            api_url="https://192.168.1.10:8006",
            credential_ref="proxmox.test",
            location_id="home-lan",
            pve_version="8.4.14",
            node_name=None,
        )
        await db.flush()

        # Create VMs
        vm1 = VirtualMachine(
            uuid="00000000-0000-0000-0001-000000000001",
            name="vm1",
            vmid=100,
            vm_type=VMType.QEMU,
            hypervisor_id=hypervisor.id,
            state=VMState.RUNNING,
        )
        vm2 = VirtualMachine(
            uuid="00000000-0000-0000-0001-000000000002",
            name="vm2",
            vmid=101,
            vm_type=VMType.LXC,
            hypervisor_id=hypervisor.id,
            state=VMState.RUNNING,
        )
        vm3 = VirtualMachine(
            uuid="00000000-0000-0000-0001-000000000003",
            name="vm3",
            vmid=102,
            vm_type=VMType.QEMU,
            hypervisor_id=hypervisor.id,
            state=VMState.STOPPED,
        )
        db.add_all([vm1, vm2, vm3])
        await db.flush()

        stats = await service.get_vm_stats()

        assert stats["total"] == 3
        assert stats["running"] == 2
        assert stats["stopped"] == 1
        assert stats["qemu"] == 2
        assert stats["lxc"] == 1
