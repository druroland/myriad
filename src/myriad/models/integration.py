"""Integration configuration models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from myriad.models.base import Base, TimestampMixin


class IntegrationType(str, Enum):
    """Type of integration."""

    OPNSENSE = "opnsense"
    UNIFI = "unifi"


class IntegrationStatus(str, Enum):
    """Integration connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNKNOWN = "unknown"


class Integration(Base, TimestampMixin):
    """External service integration configuration."""

    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    integration_type: Mapped[IntegrationType] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Connection info
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(100), nullable=False)

    # Status
    status: Mapped[IntegrationStatus] = mapped_column(
        String(20), default=IntegrationStatus.UNKNOWN, nullable=False
    )
    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Type-specific config (stored as JSON string)
    extra_config: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Integration {self.id}: {self.integration_type}>"


class AuditLog(Base):
    """Audit log for tracking actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Actor
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Action
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Details
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<AuditLog {self.id}: {self.action}>"
