"""Host schemas for validation and responses."""

from datetime import datetime

from pydantic import BaseModel, Field

from myriad.models import DiscoverySource, HostStatus, HostType


class HostBase(BaseModel):
    """Base host fields."""

    mac_address: str = Field(..., pattern=r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
    hostname: str | None = None
    display_name: str | None = None
    ip_address: str | None = None
    host_type: HostType = HostType.UNKNOWN
    notes: str | None = None


class HostCreate(HostBase):
    """Host creation data."""

    location_id: str | None = None


class HostUpdate(BaseModel):
    """Host update data (all fields optional)."""

    hostname: str | None = None
    display_name: str | None = None
    ip_address: str | None = None
    host_type: HostType | None = None
    location_id: str | None = None
    notes: str | None = None


class HostResponse(HostBase):
    """Host response data."""

    id: int
    status: HostStatus
    discovery_source: DiscoverySource
    location_id: str | None
    is_static_lease: bool
    lease_expires: datetime | None
    vendor: str | None
    model: str | None
    first_seen: datetime | None
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def effective_name(self) -> str:
        """Get the best available name for this host."""
        return self.display_name or self.hostname or self.mac_address


class HostListResponse(BaseModel):
    """Paginated host list response."""

    items: list[HostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class HostSyncResult(BaseModel):
    """Result of a host sync operation."""

    created: int
    updated: int
    source: str
    timestamp: datetime
