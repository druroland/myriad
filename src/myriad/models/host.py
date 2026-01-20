"""Host model for discovered and managed devices."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myriad.models.base import Base, TimestampMixin


class HostType(str, Enum):
    """Type of host device."""

    UNKNOWN = "unknown"
    SERVER = "server"
    WORKSTATION = "workstation"
    LAPTOP = "laptop"
    PHONE = "phone"
    TABLET = "tablet"
    IOT = "iot"
    NETWORK = "network"
    PRINTER = "printer"
    MEDIA = "media"
    GAMING = "gaming"
    APPLIANCE = "appliance"


class HostStatus(str, Enum):
    """Host status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class DiscoverySource(str, Enum):
    """How the host was discovered."""

    MANUAL = "manual"
    OPNSENSE_DHCP = "opnsense_dhcp"
    UNIFI = "unifi"


class Host(Base, TimestampMixin):
    """Discovered or manually added host device."""

    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mac_address: Mapped[str] = mapped_column(String(17), unique=True, nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    host_type: Mapped[HostType] = mapped_column(
        String(20), default=HostType.UNKNOWN, nullable=False
    )
    status: Mapped[HostStatus] = mapped_column(
        String(20), default=HostStatus.UNKNOWN, nullable=False
    )
    discovery_source: Mapped[DiscoverySource] = mapped_column(
        String(20), default=DiscoverySource.MANUAL, nullable=False
    )

    # Location reference
    location_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("locations.id"), nullable=True
    )
    location: Mapped["Location | None"] = relationship("Location", back_populates="hosts")  # noqa: F821

    # DHCP lease info
    is_static_lease: Mapped[bool] = mapped_column(default=False, nullable=False)
    lease_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Vendor/hardware info
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tracking
    first_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Unifi enrichment data (stored as JSON-compatible fields)
    unifi_client_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # VM link (if this host is a virtual machine)
    virtual_machine: Mapped["VirtualMachine | None"] = relationship(  # noqa: F821
        "VirtualMachine", back_populates="host", uselist=False
    )

    def __repr__(self) -> str:
        name = self.display_name or self.hostname or self.mac_address
        return f"<Host {self.id}: {name}>"

    @property
    def effective_name(self) -> str:
        """Get the best available name for this host."""
        return self.display_name or self.hostname or self.mac_address
