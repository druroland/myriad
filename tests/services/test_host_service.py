"""Tests for the HostService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.models import DiscoverySource, Host, HostStatus
from myriad.schemas import HostCreate, HostUpdate
from myriad.services import HostService


class TestMacNormalization:
    """Tests for MAC address normalization."""

    def test_normalize_lowercase_colons(self):
        """MAC already in correct format should be unchanged."""
        result = HostService._normalize_mac("aa:bb:cc:dd:ee:ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_uppercase_colons(self):
        """Uppercase MAC should be lowercased."""
        result = HostService._normalize_mac("AA:BB:CC:DD:EE:FF")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_dashes(self):
        """MAC with dashes should use colons."""
        result = HostService._normalize_mac("aa-bb-cc-dd-ee-ff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_no_separators(self):
        """MAC without separators should be split correctly."""
        result = HostService._normalize_mac("aabbccddeeff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_normalize_cisco_format(self):
        """MAC in Cisco format (dots) should be normalized."""
        result = HostService._normalize_mac("aabb.ccdd.eeff")
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_invalid_mac_too_short(self):
        """MAC that's too short should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid MAC address"):
            HostService._normalize_mac("aa:bb:cc")

    def test_invalid_mac_too_long(self):
        """MAC that's too long should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid MAC address"):
            HostService._normalize_mac("aa:bb:cc:dd:ee:ff:00")

    def test_invalid_mac_bad_hex(self):
        """MAC with invalid hex characters should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid MAC address"):
            HostService._normalize_mac("gg:hh:ii:jj:kk:ll")


class TestHostServiceCRUD:
    """Tests for HostService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_host(self, db: AsyncSession):
        """Test creating a new host."""
        service = HostService(db)
        data = HostCreate(mac_address="aa:bb:cc:dd:ee:ff")

        host = await service.create(data)

        assert host.id is not None
        assert host.mac_address == "aa:bb:cc:dd:ee:ff"
        assert host.discovery_source == DiscoverySource.MANUAL
        assert host.first_seen is not None
        assert host.last_seen is not None

    @pytest.mark.asyncio
    async def test_create_host_normalizes_mac(self, db: AsyncSession):
        """Test that MAC is normalized on create."""
        service = HostService(db)
        data = HostCreate(mac_address="AA-BB-CC-DD-EE-FF")

        host = await service.create(data)

        assert host.mac_address == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_get_by_id(self, db: AsyncSession):
        """Test getting a host by ID."""
        service = HostService(db)
        data = HostCreate(mac_address="11:22:33:44:55:66")
        created = await service.create(data)
        await db.flush()

        found = await service.get_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.mac_address == "11:22:33:44:55:66"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db: AsyncSession):
        """Test getting a nonexistent host returns None."""
        service = HostService(db)

        found = await service.get_by_id(99999)

        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_mac(self, db: AsyncSession):
        """Test getting a host by MAC address."""
        service = HostService(db)
        data = HostCreate(mac_address="aa:11:bb:22:cc:33")
        await service.create(data)
        await db.flush()

        # Should find with same format
        found = await service.get_by_mac("aa:11:bb:22:cc:33")
        assert found is not None

        # Should also find with different format (normalized)
        found2 = await service.get_by_mac("AA-11-BB-22-CC-33")
        assert found2 is not None
        assert found2.mac_address == "aa:11:bb:22:cc:33"

    @pytest.mark.asyncio
    async def test_update_host(self, db: AsyncSession):
        """Test updating a host."""
        service = HostService(db)
        data = HostCreate(mac_address="aa:bb:cc:dd:ee:ff")
        host = await service.create(data)
        await db.flush()

        update_data = HostUpdate(
            display_name="My Server",
            notes="Important server",
        )
        updated = await service.update(host, update_data)

        assert updated.display_name == "My Server"
        assert updated.notes == "Important server"
        assert updated.mac_address == "aa:bb:cc:dd:ee:ff"  # Unchanged

    @pytest.mark.asyncio
    async def test_delete_host(self, db: AsyncSession):
        """Test deleting a host."""
        service = HostService(db)
        data = HostCreate(mac_address="de:le:te:me:00:00")
        host = await service.create(data)
        await db.flush()
        host_id = host.id

        await service.delete(host)
        await db.flush()

        found = await service.get_by_id(host_id)
        assert found is None


class TestHostServiceUpsert:
    """Tests for HostService upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new_host(self, db: AsyncSession):
        """Test upsert creates a new host when none exists."""
        service = HostService(db)

        host, created = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.100",
            hostname="new-host",
            source=DiscoverySource.OPNSENSE_DHCP,
        )

        assert created is True
        assert host.mac_address == "aa:bb:cc:dd:ee:ff"
        assert host.ip_address == "192.168.1.100"
        assert host.hostname == "new-host"
        assert host.status == HostStatus.ONLINE
        assert host.discovery_source == DiscoverySource.OPNSENSE_DHCP

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_host(self, db: AsyncSession):
        """Test upsert updates an existing host."""
        service = HostService(db)

        # Create initial host
        host1, created1 = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.100",
            hostname="old-host",
            source=DiscoverySource.OPNSENSE_DHCP,
        )
        await db.flush()
        assert created1 is True

        # Upsert same MAC with new IP
        host2, created2 = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.200",  # New IP
            hostname="old-host",
            source=DiscoverySource.OPNSENSE_DHCP,
        )

        assert created2 is False
        assert host1.id == host2.id
        assert host2.ip_address == "192.168.1.200"

    @pytest.mark.asyncio
    async def test_upsert_preserves_display_name(self, db: AsyncSession):
        """Test upsert doesn't overwrite display_name with hostname."""
        service = HostService(db)

        # Create host with display name
        host1, _ = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.100",
            hostname="dhcp-hostname",
            source=DiscoverySource.OPNSENSE_DHCP,
        )
        await db.flush()

        # Set display name manually
        host1.display_name = "My Custom Name"
        await db.flush()

        # Upsert with different hostname
        host2, _ = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="192.168.1.100",
            hostname="new-dhcp-hostname",
            source=DiscoverySource.OPNSENSE_DHCP,
        )

        # Display name should be preserved
        assert host2.display_name == "My Custom Name"
        # Hostname should NOT be updated since display_name is set
        assert host2.hostname == "dhcp-hostname"


class TestHostServiceStats:
    """Tests for HostService statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, db: AsyncSession):
        """Test stats with no hosts."""
        service = HostService(db)

        stats = await service.get_stats()

        assert stats["total"] == 0
        assert stats["online"] == 0
        assert stats["offline"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_hosts(self, db: AsyncSession):
        """Test stats with various hosts."""
        service = HostService(db)

        # Create some hosts
        host1, _ = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:01",
            ip_address="192.168.1.1",
            hostname="host1",
            source=DiscoverySource.OPNSENSE_DHCP,
            is_static=True,
        )

        host2, _ = await service.upsert_from_discovery(
            mac_address="aa:bb:cc:dd:ee:02",
            ip_address="192.168.1.2",
            hostname="host2",
            source=DiscoverySource.OPNSENSE_DHCP,
            is_static=False,
        )
        await db.flush()

        # Make one offline
        host2.status = HostStatus.OFFLINE
        await db.flush()

        stats = await service.get_stats()

        assert stats["total"] == 2
        assert stats["online"] == 1
        assert stats["offline"] == 1
        assert stats["static_leases"] == 1
        assert stats["dynamic_leases"] == 1
