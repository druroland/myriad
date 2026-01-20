"""Hypervisor and VM models for Proxmox and libvirt management."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myriad.models.base import Base, TimestampMixin


class HypervisorType(str, Enum):
    """Type of hypervisor."""

    PROXMOX = "proxmox"
    LIBVIRT = "libvirt"  # Legacy/future SSH-based


class HypervisorStatus(str, Enum):
    """Hypervisor connection status."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


class VMType(str, Enum):
    """Type of virtual machine."""

    QEMU = "qemu"  # Full virtualization
    LXC = "lxc"  # Linux container


class VMState(str, Enum):
    """Virtual machine state."""

    RUNNING = "running"
    PAUSED = "paused"
    SHUTDOWN = "shutdown"
    SHUTOFF = "shutoff"
    STOPPED = "stopped"  # Proxmox term for powered off
    CRASHED = "crashed"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class Hypervisor(Base, TimestampMixin):
    """Hypervisor host (Proxmox or libvirt)."""

    __tablename__ = "hypervisors"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Hypervisor type
    hypervisor_type: Mapped[HypervisorType] = mapped_column(
        String(20), default=HypervisorType.PROXMOX, nullable=False
    )

    # API connection info (Proxmox)
    api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pve_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # SSH connection info (legacy/libvirt - now optional)
    ssh_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssh_port: Mapped[int | None] = mapped_column(Integer, default=22, nullable=True)
    ssh_user: Mapped[str | None] = mapped_column(String(50), default="root", nullable=True)
    ssh_key_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[HypervisorStatus] = mapped_column(
        String(20), default=HypervisorStatus.UNKNOWN, nullable=False
    )
    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Location reference
    location_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("locations.id"), nullable=True
    )
    location: Mapped["Location | None"] = relationship("Location", back_populates="hypervisors")  # noqa: F821

    # Relationships
    virtual_machines: Mapped[list["VirtualMachine"]] = relationship(
        "VirtualMachine", back_populates="hypervisor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Hypervisor {self.id}: {self.name} ({self.hypervisor_type})>"


class VirtualMachine(Base, TimestampMixin):
    """Virtual machine managed by a hypervisor."""

    __tablename__ = "virtual_machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Proxmox-specific identifiers
    vmid: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    vm_type: Mapped[VMType | None] = mapped_column(String(10), nullable=True)

    # Hypervisor reference
    hypervisor_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("hypervisors.id"), nullable=False
    )
    hypervisor: Mapped[Hypervisor] = relationship("Hypervisor", back_populates="virtual_machines")

    # Host link (via MAC address discovery)
    host_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hosts.id"), nullable=True)
    host: Mapped["Host | None"] = relationship("Host", back_populates="virtual_machine")  # noqa: F821

    # State
    state: Mapped[VMState] = mapped_column(String(20), default=VMState.UNKNOWN, nullable=False)

    # Resources
    vcpus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disk_gb: Mapped[float | None] = mapped_column(Integer, nullable=True)  # Total disk size

    # Network - JSON array of MAC addresses
    mac_addresses: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Runtime info
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # Comma-separated

    # Tracking
    last_state_change: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    snapshots: Mapped[list["VMSnapshot"]] = relationship(
        "VMSnapshot", back_populates="virtual_machine", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        vm_type_str = f" ({self.vm_type})" if self.vm_type else ""
        return f"<VirtualMachine {self.vmid or self.uuid}: {self.name}{vm_type_str}>"


class VMSnapshot(Base, TimestampMixin):
    """Virtual machine snapshot."""

    __tablename__ = "vm_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # VM reference
    vm_id: Mapped[int] = mapped_column(Integer, ForeignKey("virtual_machines.id"), nullable=False)
    virtual_machine: Mapped[VirtualMachine] = relationship(
        "VirtualMachine", back_populates="snapshots"
    )

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)
    parent_snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<VMSnapshot {self.id}: {self.name}>"
