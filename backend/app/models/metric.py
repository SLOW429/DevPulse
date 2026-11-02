from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_device_id_collected_at", "device_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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