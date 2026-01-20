"""Sync service for integrating with external sources."""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from myriad.config import Settings
from myriad.integrations.opnsense import OPNsenseClient
from myriad.models import DiscoverySource
from myriad.schemas import HostSyncResult
from myriad.services.host_service import HostService

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing hosts from external sources."""

    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings
        self.host_service = HostService(db)

    async def sync_opnsense(self, integration_id: str) -> HostSyncResult:
        """Sync hosts from an OPNsense instance.

        Args:
            integration_id: The ID of the OPNsense integration to sync from

        Returns:
            HostSyncResult with counts of created and updated hosts
        """
        # Find the integration config
        config = None
        for opnsense_config in self.settings.integrations.opnsense:
            if opnsense_config.id == integration_id:
                config = opnsense_config
                break

        if not config:
            raise ValueError(f"OPNsense integration '{integration_id}' not found")

        # Get credentials
        cred_parts = config.credential_ref.split(".")
        if len(cred_parts) != 2 or cred_parts[0] != "opnsense":
            raise ValueError(f"Invalid credential reference: {config.credential_ref}")

        cred_key = cred_parts[1]
        credentials = self.settings.secrets.opnsense.get(cred_key)
        if not credentials:
            raise ValueError(f"Credentials '{config.credential_ref}' not found")

        created = 0
        updated = 0

        async with OPNsenseClient(config, credentials) as client:
            # Test connection first
            if not await client.test_connection():
                raise ConnectionError(f"Failed to connect to OPNsense at {config.base_url}")

            # Get all hosts (leases + static mappings)
            hosts = await client.get_all_hosts()
            logger.info(f"Found {len(hosts)} hosts from OPNsense {integration_id}")

            for lease in hosts:
                host, was_created = await self.host_service.upsert_from_discovery(
                    mac_address=lease.mac_address,
                    ip_address=lease.ip_address,
                    hostname=lease.hostname,
                    source=DiscoverySource.OPNSENSE_DHCP,
                    is_static=lease.is_static,
                    lease_expires=lease.ends,
                    location_id=config.location_id,
                )

                if was_created:
                    created += 1
                    logger.debug(f"Created host: {host.mac_address} ({host.hostname})")
                else:
                    updated += 1

        return HostSyncResult(
            created=created,
            updated=updated,
            source=f"opnsense:{integration_id}",
            timestamp=datetime.utcnow(),
        )

    async def sync_all_opnsense(self) -> list[HostSyncResult]:
        """Sync from all configured OPNsense instances."""
        results = []

        for config in self.settings.integrations.opnsense:
            try:
                result = await self.sync_opnsense(config.id)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to sync from OPNsense {config.id}: {e}")
                results.append(
                    HostSyncResult(
                        created=0,
                        updated=0,
                        source=f"opnsense:{config.id}",
                        timestamp=datetime.utcnow(),
                    )
                )

        return results
