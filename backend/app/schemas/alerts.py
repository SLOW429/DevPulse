from datetime import UTC, datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.alert import (
    AlertMetric,
    AlertOperator,
    AlertSeverity,
    NotificationStatus,
)


class AlertState(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_id: int | None = Field(default=None, gt=0)
    metric: AlertMetric
    operator: AlertOperator | None = None
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    severity: AlertSeverity = AlertSeverity.WARNING
    evaluation_interval_seconds: int = Field(default=30, ge=5, le=3600)
    consecutive_violations: int = Field(default=1, ge=1, le=10)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name cannot be blank")
        if self.metric == AlertMetric.DEVICE_OFFLINE:
            if self.operator is not None:
                raise ValueError("device_offline rules cannot have an operator")
            if self.threshold is not None and not 1 <= self.threshold <= 86400:
                raise ValueError("offline threshold must be between 1 and 86400 seconds")
        else:
            if self.operator is None or self.threshold is None:
                raise ValueError("metric rules require both an operator and threshold")
            if not 0 <= self.threshold <= 100:
                raise ValueError("metric threshold must be between 0 and 100 percent")
        return self


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    device_id: int | None = Field(default=None, gt=0)
    metric: AlertMetric | None = None
    operator: AlertOperator | None = None
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    severity: AlertSeverity | None = None
    evaluation_interval_seconds: int | None = Field(default=None, ge=5, le=3600)
    consecutive_violations: int | None = Field(default=None, ge=1, le=10)
    enabled: bool | None = None


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    device_id: int | None
    name: str
    metric: AlertMetric
    operator: AlertOperator | None
    threshold: float | None
    severity: AlertSeverity
    evaluation_interval_seconds: int
    consecutive_violations: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _utc(value)


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    status: NotificationStatus
    attempts: int
    next_attempt_at: datetime | None
    delivered_at: datetime | None
    last_error: str | None
    created_at: datetime

    @field_validator(
        "next_attempt_at", "delivered_at", "created_at", mode="before"
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None


class AlertRead(BaseModel):
    id: int
    rule_id: int | None
    rule_name: str | None
    device_id: int
    device_name: str
    metric: AlertMetric | None
    metric_name: str
    severity: AlertSeverity
    status: AlertState
    threshold: float | None
    observed_value: float | None
    message: str
    triggered_at: datetime
    resolved_at: datetime | None
    notifications: list[NotificationRead]

    @field_validator("triggered_at", "resolved_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None


class AlertPage(BaseModel):
    items: list[AlertRead]
    total: int
    limit: int
    offset: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
