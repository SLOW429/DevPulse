from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.device import Device
from app.schemas.device import AgentHeartbeat
from app.schemas.metric import MetricCreate, MetricRead
from app.services.device_service import (
    authenticate_agent,
    record_heartbeat,
    record_metric,
)

router = APIRouter(prefix="/agent", tags=["Monitoring Agent"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_device(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Session = Depends(get_db),
) -> Device:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    device = authenticate_agent(db, credentials.credentials)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device


AuthenticatedDevice = Annotated[Device, Depends(get_authenticated_device)]
Database = Annotated[Session, Depends(get_db)]


@router.post("/heartbeat", response_model=AgentHeartbeat)
def heartbeat(device: AuthenticatedDevice, db: Database) -> AgentHeartbeat:
    last_seen_at = record_heartbeat(db, device)
    return AgentHeartbeat(
        agent_id=device.agent_id,
        status=device.status,
        last_seen_at=last_seen_at,
    )


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
def ingest_metrics(
    data: MetricCreate, device: AuthenticatedDevice, db: Database
) -> MetricRead:
    return MetricRead.model_validate(record_metric(db, device, data))
