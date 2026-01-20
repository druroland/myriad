"""Add Proxmox support to hypervisors and VMs.

Revision ID: 002_proxmox_support
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_proxmox_support"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("hypervisors") as batch_op:
        # Add new Proxmox-specific columns
        batch_op.add_column(
            sa.Column("hypervisor_type", sa.String(20), nullable=False, server_default="proxmox")
        )
        batch_op.add_column(sa.Column("api_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("credential_ref", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("node_name", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("pve_version", sa.String(50), nullable=True))

        # Make SSH fields nullable (they were required before)
        batch_op.alter_column("ssh_host", existing_type=sa.String(255), nullable=True)
        batch_op.alter_column("ssh_port", existing_type=sa.Integer, nullable=True)
        batch_op.alter_column("ssh_user", existing_type=sa.String(50), nullable=True)
        batch_op.alter_column("ssh_key_ref", existing_type=sa.String(100), nullable=True)

    with op.batch_alter_table("virtual_machines") as batch_op:
        # Add new Proxmox-specific columns
        batch_op.add_column(sa.Column("vmid", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("vm_type", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("host_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("mac_addresses", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("uptime_seconds", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("tags", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("disk_gb", sa.Integer, nullable=True))

        # Create foreign key for host_id
        batch_op.create_foreign_key(
            "fk_virtual_machines_host_id",
            "hosts",
            ["host_id"],
            ["id"],
        )

        # Create index on vmid for faster lookups
        batch_op.create_index("ix_virtual_machines_vmid", ["vmid"])


def downgrade() -> None:
    with op.batch_alter_table("virtual_machines") as batch_op:
        batch_op.drop_index("ix_virtual_machines_vmid")
        batch_op.drop_constraint("fk_virtual_machines_host_id", type_="foreignkey")
        batch_op.drop_column("disk_gb")
        batch_op.drop_column("tags")
        batch_op.drop_column("uptime_seconds")
        batch_op.drop_column("mac_addresses")
        batch_op.drop_column("host_id")
        batch_op.drop_column("vm_type")
        batch_op.drop_column("vmid")

    with op.batch_alter_table("hypervisors") as batch_op:
        # Restore SSH fields as required (note: this may fail if data is null)
        batch_op.alter_column("ssh_key_ref", existing_type=sa.String(100), nullable=False)
        batch_op.alter_column("ssh_user", existing_type=sa.String(50), nullable=False)
        batch_op.alter_column("ssh_port", existing_type=sa.Integer, nullable=False)
        batch_op.alter_column("ssh_host", existing_type=sa.String(255), nullable=False)

        batch_op.drop_column("pve_version")
        batch_op.drop_column("node_name")
        batch_op.drop_column("credential_ref")
        batch_op.drop_column("api_url")
        batch_op.drop_column("hypervisor_type")
