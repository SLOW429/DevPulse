import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_device_id_status", "device_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    metric_name: Mapped[str] = mapped_column(String(50))
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