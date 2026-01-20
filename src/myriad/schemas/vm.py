"""VM schemas for validation and responses."""

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from myriad.models import HypervisorStatus, HypervisorType, VMState, VMType


class HypervisorResponse(BaseModel):
    """Hypervisor response data."""

    id: str
    name: str
    hypervisor_type: HypervisorType
    api_url: str | None
    node_name: str | None
    pve_version: str | None
    status: HypervisorStatus
    last_sync: datetime | None
    last_error: str | None
    location_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VMResponse(BaseModel):
    """VM response data."""

    id: int
    uuid: str
    name: str
    vmid: int | None
    vm_type: VMType | None
    hypervisor_id: str
    host_id: int | None
    state: VMState
    vcpus: int | None
    memory_mb: int | None
    disk_gb: float | None
    mac_addresses: str | None  # JSON string
    uptime_seconds: int | None
    tags: str | None
    last_state_change: datetime | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def mac_list(self) -> list[str]:
        """Parse MAC addresses from JSON string."""
        if not self.mac_addresses:
            return []
        try:
            return json.loads(self.mac_addresses)
        except (json.JSONDecodeError, TypeError):
            return []

    @computed_field
    @property
    def memory_gb(self) -> float | None:
        """Memory in GB for display."""
        if self.memory_mb is None:
            return None
        return round(self.memory_mb / 1024, 1)

    @computed_field
    @property
    def uptime_display(self) -> str | None:
        """Human-readable uptime."""
        if self.uptime_seconds is None:
            return None

        seconds = self.uptime_seconds
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class VMDetailResponse(VMResponse):
    """VM detail response with relationships."""

    hypervisor: HypervisorResponse | None = None
    snapshots: list["VMSnapshotResponse"] = []


class VMSnapshotResponse(BaseModel):
    """VM snapshot response data."""

    id: int
    name: str
    description: str | None
    is_current: bool
    parent_snapshot_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VMListResponse(BaseModel):
    """Paginated VM list response."""

    items: list[VMResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VMSyncResult(BaseModel):
    """Result of a VM sync operation."""

    hypervisor_id: str
    vms_created: int
    vms_updated: int
    vms_removed: int
    hosts_linked: int
    snapshots_synced: int
    timestamp: datetime
    error: str | None = None


class VMStatsResponse(BaseModel):
    """VM statistics response."""

    total: int
    running: int
    stopped: int
    qemu: int
    lxc: int


# Update forward references
VMDetailResponse.model_rebuild()
