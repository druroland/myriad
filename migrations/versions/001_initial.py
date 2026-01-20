"""Initial database schema.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Locations
    op.create_table(
        "locations",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("network_cidr", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_login", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )

    # Hosts
    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.String(17), unique=True, nullable=False, index=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("host_type", sa.String(20), default="unknown", nullable=False),
        sa.Column("status", sa.String(20), default="unknown", nullable=False),
        sa.Column("discovery_source", sa.String(20), default="manual", nullable=False),
        sa.Column("location_id", sa.String(50), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("is_static_lease", sa.Boolean, default=False, nullable=False),
        sa.Column("lease_expires", sa.DateTime, nullable=True),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("first_seen", sa.DateTime, nullable=True),
        sa.Column("last_seen", sa.DateTime, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("unifi_client_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Hypervisors
    op.create_table(
        "hypervisors",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ssh_host", sa.String(255), nullable=False),
        sa.Column("ssh_port", sa.Integer, default=22, nullable=False),
        sa.Column("ssh_user", sa.String(50), default="root", nullable=False),
        sa.Column("ssh_key_ref", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), default="unknown", nullable=False),
        sa.Column("last_sync", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("location_id", sa.String(50), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Virtual Machines
    op.create_table(
        "virtual_machines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hypervisor_id", sa.String(50), sa.ForeignKey("hypervisors.id"), nullable=False),
        sa.Column("state", sa.String(20), default="unknown", nullable=False),
        sa.Column("vcpus", sa.Integer, nullable=True),
        sa.Column("memory_mb", sa.Integer, nullable=True),
        sa.Column("last_state_change", sa.DateTime, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # VM Snapshots
    op.create_table(
        "vm_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("virtual_machines.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_current", sa.Boolean, default=False, nullable=False),
        sa.Column("parent_snapshot_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Integrations
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("integration_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("credential_ref", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), default="unknown", nullable=False),
        sa.Column("last_sync", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("extra_config", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Audit Log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, default=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("integrations")
    op.drop_table("vm_snapshots")
    op.drop_table("virtual_machines")
    op.drop_table("hypervisors")
    op.drop_table("hosts")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("locations")
