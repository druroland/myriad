"""Location model for network segments."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myriad.models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Network location/segment (e.g., home-lan, vps-frankfurt)."""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    network_cidr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    hosts: Mapped[list["Host"]] = relationship(  # noqa: F821
        "Host", back_populates="location", cascade="all, delete-orphan"
    )
    hypervisors: Mapped[list["Hypervisor"]] = relationship(  # noqa: F821
        "Hypervisor", back_populates="location", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Location {self.id}: {self.name}>"
