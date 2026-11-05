"""add alert rules, evaluation queue, and notification delivery

Revision ID: 8d4a20c7f1be
Revises: c2f59e4a6d31
Create Date: 2026-11-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8d4a20c7f1be"
down_revision: Union[str, Sequence[str], None] = "c2f59e4a6d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


alert_metric = postgresql.ENUM(
    "cpu", "ram", "disk", "device_offline", name="alert_metric", create_type=False
)
alert_operator = postgresql.ENUM(
    "gt", "gte", "lt", "lte", name="alert_operator", create_type=False
)
alert_severity = postgresql.ENUM(
    "info", "warning", "critical", name="alert_severity", create_type=False
)
alert_status = postgresql.ENUM(
    "open", "acknowledged", "resolved", name="alert_status", create_type=False
)
notification_status = postgresql.ENUM(
    "pending", "sending", "delivered", "disabled", "failed",
    name="notification_status", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        alert_metric.create(bind, checkfirst=True)
        alert_operator.create(bind, checkfirst=True)
        notification_status.create(bind, checkfirst=True)

    op.add_column(
        "metrics",
        sa.Column("alerts_evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "metrics",
        sa.Column(
            "alert_evaluation_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "metrics",
        sa.Column("alert_evaluation_error", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "metrics",
        sa.Column(
            "next_alert_evaluation_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_index(
        "ix_metrics_alert_evaluation_due",
        "metrics",
        ["alerts_evaluated_at", "next_alert_evaluation_at", "id"],
        postgresql_where=sa.text("alerts_evaluated_at IS NULL"),
        sqlite_where=sa.text("alerts_evaluated_at IS NULL"),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("metric", alert_metric, nullable=False),
        sa.Column("operator", alert_operator, nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column(
            "evaluation_interval_seconds",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column(
            "consecutive_violations",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_rules_owner_id", "alert_rules", ["owner_id"])
    op.create_index("ix_alert_rules_owner_enabled", "alert_rules", ["owner_id", "enabled"])
    op.create_index("ix_alert_rules_device_id", "alert_rules", ["device_id"])

    op.create_table(
        "alert_rule_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("consecutive_count", sa.Integer(), nullable=False),
        sa.Column("last_evaluated_metric_id", sa.BigInteger(), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_evaluated_metric_id"], ["metrics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "device_id", name="uq_alert_rule_state_device"),
    )
    op.create_index("ix_alert_rule_states_rule_id", "alert_rule_states", ["rule_id"])
    op.create_index("ix_alert_rule_states_device_id", "alert_rule_states", ["device_id"])

    op.add_column("alerts", sa.Column("rule_id", sa.Integer(), nullable=True))
    op.add_column("alerts", sa.Column("rule_name", sa.String(length=120), nullable=True))
    op.add_column("alerts", sa.Column("threshold", sa.Float(), nullable=True))
    op.add_column("alerts", sa.Column("observed_value", sa.Float(), nullable=True))
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.create_foreign_key(
            "fk_alerts_rule_id_alert_rules",
            "alert_rules",
            ["rule_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_alerts_rule_device", "alerts", ["rule_id", "device_id"])
    op.create_index(
        "uq_alerts_active_rule_device",
        "alerts",
        ["rule_id", "device_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'resolved' AND rule_id IS NOT NULL"),
        sqlite_where=sa.text("status <> 'resolved' AND rule_id IS NOT NULL"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sending_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "event_type", name="uq_notification_alert_event"),
    )
    op.create_index(
        "ix_notification_deliveries_alert_id", "notification_deliveries", ["alert_id"]
    )
    op.create_index(
        "ix_notification_deliveries_due",
        "notification_deliveries",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_due", table_name="notification_deliveries")
    op.drop_index(
        "ix_notification_deliveries_alert_id", table_name="notification_deliveries"
    )
    op.drop_table("notification_deliveries")
    op.drop_index("uq_alerts_active_rule_device", table_name="alerts")
    op.drop_index("ix_alerts_rule_device", table_name="alerts")
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_constraint("fk_alerts_rule_id_alert_rules", type_="foreignkey")
    op.drop_column("alerts", "observed_value")
    op.drop_column("alerts", "threshold")
    op.drop_column("alerts", "rule_name")
    op.drop_column("alerts", "rule_id")
    op.drop_index("ix_alert_rule_states_device_id", table_name="alert_rule_states")
    op.drop_index("ix_alert_rule_states_rule_id", table_name="alert_rule_states")
    op.drop_table("alert_rule_states")
    op.drop_index("ix_alert_rules_device_id", table_name="alert_rules")
    op.drop_index("ix_alert_rules_owner_enabled", table_name="alert_rules")
    op.drop_index("ix_alert_rules_owner_id", table_name="alert_rules")
    op.drop_table("alert_rules")
    op.drop_index("ix_metrics_alert_evaluation_due", table_name="metrics")
    op.drop_column("metrics", "next_alert_evaluation_at")
    op.drop_column("metrics", "alert_evaluation_error")
    op.drop_column("metrics", "alert_evaluation_attempts")
    op.drop_column("metrics", "alerts_evaluated_at")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        notification_status.drop(bind, checkfirst=True)
        alert_operator.drop(bind, checkfirst=True)
        alert_metric.drop(bind, checkfirst=True)
