from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_device_id_collected_at", "device_id", "collected_at"),
        Index(
            "ix_metrics_alert_evaluation_due",
            "alerts_evaluated_at",
            "next_alert_evaluation_at",
            "id",
            postgresql_where=text("alerts_evaluated_at IS NULL"),
            sqlite_where=text("alerts_evaluated_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    net_bytes_sent: Mapped[int] = mapped_column(BigInteger)
    net_bytes_recv: Mapped[int] = mapped_column(BigInteger)
    uptime_seconds: Mapped[int] = mapped_column(BigInteger)
    alerts_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alert_evaluation_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    alert_evaluation_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_alert_evaluation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )