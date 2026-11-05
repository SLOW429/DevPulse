import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertMetric(str, enum.Enum):
    CPU = "cpu"
    RAM = "ram"
    DISK = "disk"
    DEVICE_OFFLINE = "device_offline"


class AlertOperator(str, enum.Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    DISABLED = "disabled"
    FAILED = "failed"


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        Index("ix_alert_rules_owner_enabled", "owner_id", "enabled"),
        Index("ix_alert_rules_device_id", "device_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    metric: Mapped[AlertMetric] = mapped_column(
        Enum(
            AlertMetric,
            name="alert_metric",
            values_callable=lambda e: [item.value for item in e],
        )
    )
    operator: Mapped[AlertOperator | None] = mapped_column(
        Enum(
            AlertOperator,
            name="alert_operator",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=True,
    )
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda e: [item.value for item in e],
        )
    )
    evaluation_interval_seconds: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30"
    )
    consecutive_violations: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertRuleState(Base):
    __tablename__ = "alert_rule_states"
    __table_args__ = (
        UniqueConstraint("rule_id", "device_id", name="uq_alert_rule_state_device"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    consecutive_count: Mapped[int] = mapped_column(Integer, default=0)
    last_evaluated_metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("metrics.id", ondelete="SET NULL"), nullable=True
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_device_id_status", "device_id", "status"),
        Index("ix_alerts_rule_device", "rule_id", "device_id"),
        Index(
            "uq_alerts_active_rule_device",
            "rule_id",
            "device_id",
            unique=True,
            postgresql_where=text("status <> 'resolved' AND rule_id IS NOT NULL"),
            sqlite_where=text("status <> 'resolved' AND rule_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True
    )
    rule_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(50))
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(
            AlertStatus,
            name="alert_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AlertStatus.OPEN,
    )
    message: Mapped[str] = mapped_column(Text)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device: Mapped["Device"] = relationship()
    notifications: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="NotificationDelivery.id",
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("alert_id", "event_type", name="uq_notification_alert_event"),
        Index("ix_notification_deliveries_due", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status",
            values_callable=lambda e: [item.value for item in e],
        ),
        default=NotificationStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sending_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    alert: Mapped[Alert] = relationship(back_populates="notifications")