from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import DeviceStatus


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    os: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def require_nonblank_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: UUID
    name: str
    hostname: str | None
    os: str | None
    status: DeviceStatus
    last_seen_at: datetime | None
    created_at: datetime


class AgentCredential(BaseModel):
    device: DeviceRead
    agent_key: str


class AgentHeartbeat(BaseModel):
    agent_id: UUID
    status: DeviceStatus
    last_seen_at: datetime
