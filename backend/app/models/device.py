import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    hostname: Mapped[str | None] = mapped_column(String(255))
    os: Mapped[str | None] = mapped_column(String(100))
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    api_key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            name="device_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DeviceStatus.UNKNOWN,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )