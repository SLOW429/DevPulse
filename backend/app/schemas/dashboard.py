from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.device import DeviceStatus
from app.schemas.metric import MetricRead


class DashboardDevice(BaseModel):
    id: int
    agent_id: UUID
    name: str
    hostname: str | None
    os: str | None
    status: DeviceStatus
    last_seen_at: datetime | None
    latest_metric: MetricRead | None


class DashboardSnapshot(BaseModel):
    generated_at: datetime
    devices: list[DashboardDevice]


class WebSocketTicket(BaseModel):
    ticket: str
    expires_in: int
