from datetime import UTC, datetime, timedelta
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    collected_at: datetime
    received_at: datetime
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    net_bytes_sent: int
    net_bytes_recv: int
    uptime_seconds: int

    @field_validator("collected_at", "received_at", mode="before")
    @classmethod
    def normalize_output_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class MetricCreate(BaseModel):
    collected_at: datetime
    cpu_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    ram_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    disk_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    net_bytes_sent: int = Field(ge=0, le=9_223_372_036_854_775_807)
    net_bytes_recv: int = Field(ge=0, le=9_223_372_036_854_775_807)
    uptime_seconds: int = Field(ge=0, le=9_223_372_036_854_775_807)

    @field_validator("collected_at")
    @classmethod
    def require_recent_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must include a timezone")
        value = value.astimezone(UTC)
        if value > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("collected_at cannot be more than 5 minutes in the future")
        return value

    @field_validator("cpu_percent", "ram_percent", "disk_percent")
    @classmethod
    def require_finite_percentages(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("metric percentages must be finite")
        return value
