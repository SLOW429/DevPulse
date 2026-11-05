"""add stable agent identity and credential revocation timestamp

Revision ID: c2f59e4a6d31
Revises: 0149aaa00b25
Create Date: 2026-11-05
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "c2f59e4a6d31"
down_revision: Union[str, Sequence[str], None] = "0149aaa00b25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("agent_id", sa.String(length=36), nullable=True))
    op.add_column(
        "devices",
        sa.Column("credential_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    connection = op.get_bind()
    devices = sa.table(
        "devices",
        sa.column("id", sa.Integer),
        sa.column("agent_id", sa.String),
    )
    if connection.dialect.name == "postgresql":
        connection.execute(
            devices.update()
            .where(devices.c.agent_id.is_(None))
            .values(agent_id=sa.cast(sa.func.gen_random_uuid(), sa.String()))
        )
    else:
        device_ids = connection.execute(
            sa.select(devices.c.id).where(devices.c.agent_id.is_(None))
        )
        for (device_id,) in device_ids:
            connection.execute(
                devices.update()
                .where(devices.c.id == device_id)
                .values(agent_id=str(uuid4()))
            )

    with op.batch_alter_table("devices") as batch_op:
        batch_op.alter_column("agent_id", existing_type=sa.String(length=36), nullable=False)
    op.create_index("ix_devices_agent_id", "devices", ["agent_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_devices_agent_id", table_name="devices")
    op.drop_column("devices", "credential_revoked_at")
    op.drop_column("devices", "agent_id")
