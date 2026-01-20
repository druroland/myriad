"""Host service for managing discovered hosts."""

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.models import DiscoverySource, Host, HostStatus
from myriad.schemas import HostCreate, HostUpdate

logger = logging.getLogger(__name__)


class HostService:
    """Service for host CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        location_id: str | None = None,
        status: HostStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Host], int]:
        """Get all hosts with optional filtering."""
        query = select(Host)

        if location_id:
            query = query.where(Host.location_id == location_id)
        if status:
            query = query.where(Host.status == status)

        # Get total count
        count_query = select(func.count(Host.id))
        if location_id:
            count_query = count_query.where(Host.location_id == location_id)
        if status:
            count_query = count_query.where(Host.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(Host.last_seen.desc().nullslast(), Host.hostname)
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        hosts = list(result.scalars().all())

        return hosts, total

    async def get_by_id(self, host_id: int) -> Host | None:
        """Get a host by ID."""
        result = await self.db.execute(select(Host).where(Host.id == host_id))
        return result.scalar_one_or_none()

    async def get_by_mac(self, mac_address: str) -> Host | None:
        """Get a host by MAC address."""
        normalized_mac = self._normalize_mac(mac_address)
        result = await self.db.execute(select(Host).where(Host.mac_address == normalized_mac))
        return result.scalar_one_or_none()

    async def create(self, data: HostCreate) -> Host:
        """Create a new host."""
        host = Host(
            mac_address=self._normalize_mac(data.mac_address),
            hostname=data.hostname,
            display_name=data.display_name,
            ip_address=data.ip_address,
            host_type=data.host_type,
            location_id=data.location_id,
            notes=data.notes,
            discovery_source=DiscoverySource.MANUAL,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        self.db.add(host)
        await self.db.flush()
        return host

    async def update(self, host: Host, data: HostUpdate) -> Host:
        """Update an existing host."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(host, field, value)

        await self.db.flush()
        return host

    async def delete(self, host: Host) -> None:
        """Delete a host."""
        self.db.delete(host)  # delete() is sync in SQLAlchemy 2.0
        await self.db.flush()

    async def upsert_from_discovery(
        self,
        mac_address: str,
        ip_address: str,
        hostname: str | None,
        source: DiscoverySource,
        is_static: bool = False,
        lease_expires: datetime | None = None,
        location_id: str | None = None,
    ) -> tuple[Host, bool]:
        """Create or update a host from discovery.

        Returns (host, created) where created is True if a new host was created.
        """
        normalized_mac = self._normalize_mac(mac_address)
        existing = await self.get_by_mac(normalized_mac)

        now = datetime.utcnow()

        if existing:
            # Update existing host
            existing.ip_address = ip_address
            existing.is_static_lease = is_static
            existing.lease_expires = lease_expires
            existing.last_seen = now
            existing.status = HostStatus.ONLINE

            # Only update hostname if we have one and don't have a display_name
            if hostname and not existing.display_name:
                existing.hostname = hostname

            # Only update location if not manually set
            if location_id and not existing.location_id:
                existing.location_id = location_id

            await self.db.flush()
            return existing, False

        # Create new host
        host = Host(
            mac_address=normalized_mac,
            hostname=hostname,
            ip_address=ip_address,
            discovery_source=source,
            is_static_lease=is_static,
            lease_expires=lease_expires,
            location_id=location_id,
            status=HostStatus.ONLINE,
            first_seen=now,
            last_seen=now,
        )
        self.db.add(host)
        await self.db.flush()
        return host, True

    async def get_stats(self) -> dict:
        """Get host statistics."""
        total_result = await self.db.execute(select(func.count(Host.id)))
        total = total_result.scalar_one()

        online_result = await self.db.execute(
            select(func.count(Host.id)).where(Host.status == HostStatus.ONLINE)
        )
        online = online_result.scalar_one()

        static_result = await self.db.execute(
            select(func.count(Host.id)).where(Host.is_static_lease == True)  # noqa: E712
        )
        static = static_result.scalar_one()

        return {
            "total": total,
            "online": online,
            "offline": total - online,
            "static_leases": static,
            "dynamic_leases": total - static,
        }

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """Normalize MAC address to lowercase with colons.

        Args:
            mac: MAC address in any common format

        Returns:
            Normalized MAC address (lowercase, colon-separated)

        Raises:
            ValueError: If MAC address format is invalid
        """
        mac = mac.lower().replace("-", ":").replace(".", ":")
        parts = mac.split(":")

        if len(parts) != 6:
            # Try removing all separators and rebuilding
            clean = mac.replace(":", "")
            if len(clean) == 12:
                parts = [clean[i : i + 2] for i in range(0, 12, 2)]
            else:
                raise ValueError(f"Invalid MAC address format: {mac}")

        # Validate each part is valid hex
        for part in parts:
            if len(part) != 2 or not all(c in "0123456789abcdef" for c in part):
                raise ValueError(f"Invalid MAC address format: {mac}")

        return ":".join(parts)
