"""Hypervisor and VM models for libvirt management."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myriad.models.base import Base, TimestampMixin


class HypervisorStatus(str, Enum):
    """Hypervisor connection status."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


class VMState(str, Enum):
    """Virtual machine state (matches libvirt states)."""

    RUNNING = "running"
    PAUSED = "paused"
    SHUTDOWN = "shutdown"
    SHUTOFF = "shutoff"
    CRASHED = "crashed"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class Hypervisor(Base, TimestampMixin):
    """KVM/libvirt hypervisor host."""

    __tablename__ = "hypervisors"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # SSH connection info
    ssh_host: Mapped[str] = mapped_column(String(255), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ssh_user: Mapped[str] = mapped_column(String(50), default="root", nullable=False)
    ssh_key_ref: Mapped[str] = mapped_column(String(100), nullable=False)

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
        return f"<Hypervisor {self.id}: {self.name}>"


class VirtualMachine(Base, TimestampMixin):
    """Virtual machine managed by a hypervisor."""

    __tablename__ = "virtual_machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Hypervisor reference
    hypervisor_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("hypervisors.id"), nullable=False
    )
    hypervisor: Mapped[Hypervisor] = relationship("Hypervisor", back_populates="virtual_machines")

    # State
    state: Mapped[VMState] = mapped_column(String(20), default=VMState.UNKNOWN, nullable=False)

    # Resources
    vcpus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tracking
    last_state_change: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    snapshots: Mapped[list["VMSnapshot"]] = relationship(
        "VMSnapshot", back_populates="virtual_machine", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VirtualMachine {self.uuid}: {self.name}>"


class VMSnapshot(Base, TimestampMixin):
    """Virtual machine snapshot."""

    __tablename__ = "vm_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # VM reference
    vm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("virtual_machines.id"), nullable=False
    )
    virtual_machine: Mapped[VirtualMachine] = relationship(
        "VirtualMachine", back_populates="snapshots"
    )

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)
    parent_snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<VMSnapshot {self.id}: {self.name}>"
