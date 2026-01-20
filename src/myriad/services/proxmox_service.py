"""Proxmox service for VM synchronization."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from myriad.config import Settings
from myriad.integrations.proxmox import ProxmoxClient, ProxmoxVM
from myriad.models import (
    Host,
    Hypervisor,
    HypervisorStatus,
    HypervisorType,
    VirtualMachine,
    VMSnapshot,
    VMState,
    VMType,
)

logger = logging.getLogger(__name__)


@dataclass
class ProxmoxSyncResult:
    """Result of a Proxmox sync operation."""

    hypervisor_id: str
    vms_created: int
    vms_updated: int
    vms_removed: int
    hosts_linked: int
    snapshots_synced: int
    timestamp: datetime
    error: str | None = None


class ProxmoxService:
    """Service for syncing VMs from Proxmox hypervisors."""

    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings

    async def sync_proxmox(self, integration_id: str) -> ProxmoxSyncResult:
        """Sync VMs from a specific Proxmox integration.

        Args:
            integration_id: The ID of the Proxmox integration to sync from

        Returns:
            ProxmoxSyncResult with counts of changes made
        """
        # Find the integration config
        config = None
        for proxmox_config in self.settings.integrations.proxmox:
            if proxmox_config.id == integration_id:
                config = proxmox_config
                break

        if not config:
            raise ValueError(f"Proxmox integration '{integration_id}' not found")

        # Get credentials
        cred_parts = config.credential_ref.split(".")
        if len(cred_parts) != 2 or cred_parts[0] != "proxmox":
            raise ValueError(f"Invalid credential reference: {config.credential_ref}")

        cred_key = cred_parts[1]
        credentials = self.settings.secrets.proxmox.get(cred_key)
        if not credentials:
            raise ValueError(f"Credentials '{config.credential_ref}' not found")

        timestamp = datetime.utcnow()

        try:
            async with ProxmoxClient(config, credentials) as client:
                # Test connection
                if not await client.test_connection():
                    raise ConnectionError(f"Failed to connect to Proxmox at {config.base_url}")

                # Get Proxmox version
                pve_version = await client.get_version()

                # Ensure hypervisor record exists
                hypervisor = await self._ensure_hypervisor(
                    integration_id=integration_id,
                    name=integration_id,
                    api_url=config.base_url,
                    credential_ref=config.credential_ref,
                    location_id=config.location_id,
                    pve_version=pve_version,
                    node_name=config.node,
                )

                # Get all VMs
                pve_vms = await client.get_all_vms()
                logger.info(f"Found {len(pve_vms)} VMs from Proxmox {integration_id}")

                vms_created = 0
                vms_updated = 0
                hosts_linked = 0
                snapshots_synced = 0
                active_vm_ids = set()

                for pve_vm in pve_vms:
                    # Upsert VM
                    vm, created = await self._upsert_vm(hypervisor, pve_vm)
                    active_vm_ids.add(vm.id)

                    if created:
                        vms_created += 1
                    else:
                        vms_updated += 1

                    # Link to hosts via MAC addresses
                    for mac in pve_vm.mac_addresses:
                        linked = await self._link_vm_to_host(vm, mac, config.location_id)
                        if linked:
                            hosts_linked += 1

                    # Sync snapshots
                    snap_count = await self._sync_snapshots(client, vm, pve_vm)
                    snapshots_synced += snap_count

                # Clean up stale VMs
                vms_removed = await self._cleanup_stale_vms(hypervisor.id, active_vm_ids)

                # Update hypervisor status
                hypervisor.status = HypervisorStatus.ONLINE
                hypervisor.last_sync = timestamp
                hypervisor.last_error = None

                await self.db.commit()

                return ProxmoxSyncResult(
                    hypervisor_id=integration_id,
                    vms_created=vms_created,
                    vms_updated=vms_updated,
                    vms_removed=vms_removed,
                    hosts_linked=hosts_linked,
                    snapshots_synced=snapshots_synced,
                    timestamp=timestamp,
                )

        except Exception as e:
            logger.error(f"Proxmox sync failed for {integration_id}: {e}")

            # Update hypervisor status to error
            hypervisor = await self._get_hypervisor(integration_id)
            if hypervisor:
                hypervisor.status = HypervisorStatus.ERROR
                hypervisor.last_error = str(e)
                await self.db.commit()

            return ProxmoxSyncResult(
                hypervisor_id=integration_id,
                vms_created=0,
                vms_updated=0,
                vms_removed=0,
                hosts_linked=0,
                snapshots_synced=0,
                timestamp=timestamp,
                error=str(e),
            )

    async def sync_all_proxmox(self) -> list[ProxmoxSyncResult]:
        """Sync from all configured Proxmox instances."""
        results = []

        for config in self.settings.integrations.proxmox:
            result = await self.sync_proxmox(config.id)
            results.append(result)

        return results

    async def _get_hypervisor(self, hypervisor_id: str) -> Hypervisor | None:
        """Get hypervisor by ID."""
        result = await self.db.execute(select(Hypervisor).where(Hypervisor.id == hypervisor_id))
        return result.scalar_one_or_none()

    async def _ensure_hypervisor(
        self,
        integration_id: str,
        name: str,
        api_url: str,
        credential_ref: str,
        location_id: str | None,
        pve_version: str | None,
        node_name: str | None,
    ) -> Hypervisor:
        """Ensure a hypervisor record exists, creating if needed."""
        hypervisor = await self._get_hypervisor(integration_id)

        if hypervisor:
            # Update existing
            hypervisor.api_url = api_url
            hypervisor.credential_ref = credential_ref
            hypervisor.pve_version = pve_version
            hypervisor.node_name = node_name
            if location_id:
                hypervisor.location_id = location_id
        else:
            # Create new
            hypervisor = Hypervisor(
                id=integration_id,
                name=name,
                hypervisor_type=HypervisorType.PROXMOX,
                api_url=api_url,
                credential_ref=credential_ref,
                location_id=location_id,
                pve_version=pve_version,
                node_name=node_name,
                status=HypervisorStatus.UNKNOWN,
            )
            self.db.add(hypervisor)

        await self.db.flush()
        return hypervisor

    async def _upsert_vm(
        self, hypervisor: Hypervisor, pve_vm: ProxmoxVM
    ) -> tuple[VirtualMachine, bool]:
        """Create or update a VM record.

        Returns (vm, created) where created is True if a new VM was created.
        """
        # Look up by UUID (which we generate from node+vmid)
        uuid = pve_vm.uuid
        result = await self.db.execute(select(VirtualMachine).where(VirtualMachine.uuid == uuid))
        vm = result.scalar_one_or_none()

        # Map Proxmox status to VMState
        state = self._map_status_to_state(pve_vm.status)
        vm_type = VMType.LXC if pve_vm.vm_type == "lxc" else VMType.QEMU

        # Serialize MAC addresses as JSON
        mac_json = json.dumps(pve_vm.mac_addresses) if pve_vm.mac_addresses else None

        # Calculate memory in MB
        memory_mb = None
        if pve_vm.maxmem:
            memory_mb = pve_vm.maxmem // (1024 * 1024)

        # Calculate disk in GB
        disk_gb = None
        if pve_vm.maxdisk:
            disk_gb = pve_vm.maxdisk / (1024 * 1024 * 1024)

        if vm:
            # Update existing
            old_state = vm.state
            vm.name = pve_vm.name
            vm.vmid = pve_vm.vmid
            vm.vm_type = vm_type
            vm.state = state
            vm.vcpus = None  # Proxmox doesn't expose this in cluster/resources
            vm.memory_mb = memory_mb
            vm.disk_gb = disk_gb
            vm.mac_addresses = mac_json
            vm.uptime_seconds = pve_vm.uptime
            vm.tags = pve_vm.tags

            # Track state changes
            if old_state != state:
                vm.last_state_change = datetime.utcnow()

            await self.db.flush()
            return vm, False

        # Create new
        vm = VirtualMachine(
            uuid=uuid,
            name=pve_vm.name,
            vmid=pve_vm.vmid,
            vm_type=vm_type,
            hypervisor_id=hypervisor.id,
            state=state,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            mac_addresses=mac_json,
            uptime_seconds=pve_vm.uptime,
            tags=pve_vm.tags,
        )
        self.db.add(vm)
        await self.db.flush()
        return vm, True

    async def _link_vm_to_host(
        self, vm: VirtualMachine, mac_address: str, location_id: str | None
    ) -> bool:
        """Link a VM to a Host by MAC address.

        Returns True if a new link was created.
        """
        # Normalize MAC
        mac = mac_address.lower()

        # Find host with this MAC
        result = await self.db.execute(select(Host).where(Host.mac_address == mac))
        host = result.scalar_one_or_none()

        if not host:
            return False

        # Check if already linked
        if vm.host_id == host.id:
            return False

        # Link the VM to the host
        vm.host_id = host.id
        await self.db.flush()

        logger.debug(f"Linked VM {vm.name} to host {host.effective_name} via MAC {mac}")
        return True

    async def _sync_snapshots(
        self, client: ProxmoxClient, vm: VirtualMachine, pve_vm: ProxmoxVM
    ) -> int:
        """Sync snapshots for a VM.

        Returns the number of snapshots synced.
        """
        try:
            snapshots = await client.get_vm_snapshots(pve_vm.node, pve_vm.vmid, pve_vm.vm_type)
        except Exception as e:
            logger.debug(f"Failed to get snapshots for VM {vm.name}: {e}")
            return 0

        if not snapshots:
            return 0

        synced = 0

        # Get existing snapshots for this VM
        result = await self.db.execute(select(VMSnapshot).where(VMSnapshot.vm_id == vm.id))
        existing_by_name = {s.name: s for s in result.scalars().all()}

        seen_names = set()

        for snap_data in snapshots:
            name = snap_data.get("name")
            if not name:
                continue

            seen_names.add(name)

            if name in existing_by_name:
                # Update existing
                existing = existing_by_name[name]
                existing.description = snap_data.get("description")
                existing.parent_snapshot_name = snap_data.get("parent")
            else:
                # Create new
                snapshot = VMSnapshot(
                    name=name,
                    vm_id=vm.id,
                    description=snap_data.get("description"),
                    parent_snapshot_name=snap_data.get("parent"),
                )
                self.db.add(snapshot)
                synced += 1

        # Remove snapshots that no longer exist
        for name, snapshot in existing_by_name.items():
            if name not in seen_names:
                await self.db.delete(snapshot)

        await self.db.flush()
        return synced

    async def _cleanup_stale_vms(self, hypervisor_id: str, active_vm_ids: set[int]) -> int:
        """Remove VMs that are no longer present on the hypervisor.

        Returns the number of VMs removed.
        """
        result = await self.db.execute(
            select(VirtualMachine)
            .where(VirtualMachine.hypervisor_id == hypervisor_id)
            .options(selectinload(VirtualMachine.snapshots))
        )
        all_vms = list(result.scalars().all())

        removed = 0
        for vm in all_vms:
            if vm.id not in active_vm_ids:
                logger.info(f"Removing stale VM: {vm.name} (no longer on hypervisor)")
                await self.db.delete(vm)
                removed += 1

        await self.db.flush()
        return removed

    @staticmethod
    def _map_status_to_state(status: str) -> VMState:
        """Map Proxmox status to VMState enum."""
        status_map = {
            "running": VMState.RUNNING,
            "stopped": VMState.STOPPED,
            "paused": VMState.PAUSED,
            "suspended": VMState.SUSPENDED,
        }
        return status_map.get(status.lower(), VMState.UNKNOWN)

    async def get_all_vms(
        self,
        hypervisor_id: str | None = None,
        state: VMState | None = None,
        vm_type: VMType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[VirtualMachine], int]:
        """Get all VMs with optional filtering."""
        from sqlalchemy import func

        query = select(VirtualMachine).options(
            selectinload(VirtualMachine.hypervisor),
            selectinload(VirtualMachine.host),
        )

        # Build filters
        filters = []
        if hypervisor_id:
            filters.append(VirtualMachine.hypervisor_id == hypervisor_id)
        if state:
            filters.append(VirtualMachine.state == state)
        if vm_type:
            filters.append(VirtualMachine.vm_type == vm_type)

        for f in filters:
            query = query.where(f)

        # Get total count
        count_query = select(func.count(VirtualMachine.id))
        for f in filters:
            count_query = count_query.where(f)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(VirtualMachine.name)
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        vms = list(result.scalars().all())

        return vms, total

    async def get_vm_by_id(self, vm_id: int) -> VirtualMachine | None:
        """Get a VM by ID."""
        result = await self.db.execute(
            select(VirtualMachine)
            .where(VirtualMachine.id == vm_id)
            .options(
                selectinload(VirtualMachine.hypervisor),
                selectinload(VirtualMachine.host),
                selectinload(VirtualMachine.snapshots),
            )
        )
        return result.scalar_one_or_none()

    async def get_hypervisors(self) -> list[Hypervisor]:
        """Get all hypervisors."""
        result = await self.db.execute(select(Hypervisor).order_by(Hypervisor.name))
        return list(result.scalars().all())

    async def get_vm_stats(self) -> dict:
        """Get VM statistics."""
        from sqlalchemy import func

        total_result = await self.db.execute(select(func.count(VirtualMachine.id)))
        total = total_result.scalar_one()

        running_result = await self.db.execute(
            select(func.count(VirtualMachine.id)).where(VirtualMachine.state == VMState.RUNNING)
        )
        running = running_result.scalar_one()

        qemu_result = await self.db.execute(
            select(func.count(VirtualMachine.id)).where(VirtualMachine.vm_type == VMType.QEMU)
        )
        qemu = qemu_result.scalar_one()

        lxc_result = await self.db.execute(
            select(func.count(VirtualMachine.id)).where(VirtualMachine.vm_type == VMType.LXC)
        )
        lxc = lxc_result.scalar_one()

        return {
            "total": total,
            "running": running,
            "stopped": total - running,
            "qemu": qemu,
            "lxc": lxc,
        }
