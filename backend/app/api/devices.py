from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.device import Device
from app.models.user import User
from app.schemas.device import AgentCredential, DeviceCreate, DeviceRead
from app.schemas.metric import MetricRead
from app.services.device_service import (
    get_owned_device,
    list_device_metrics,
    list_devices,
    register_device,
    revoke_device_credential,
    rotate_device_credential,
)

router = APIRouter(prefix="/devices", tags=["Devices"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _owned_device(db: Session, user: User, device_id: int) -> Device:
    device = get_owned_device(db, user.id, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post(
    "",
    response_model=AgentCredential,
    status_code=status.HTTP_201_CREATED,
)
def create_device(
    data: DeviceCreate,
    db: Database,
    user: CurrentUser,
) -> AgentCredential:
    device, credential = register_device(db, user, data)
    return AgentCredential(device=DeviceRead.model_validate(device), agent_key=credential)


@router.get("", response_model=list[DeviceRead])
def read_devices(db: Database, user: CurrentUser) -> list[DeviceRead]:
    return [DeviceRead.model_validate(device) for device in list_devices(db, user.id)]


@router.get("/{device_id}", response_model=DeviceRead)
def read_device(device_id: int, db: Database, user: CurrentUser) -> DeviceRead:
    device = _owned_device(db, user, device_id)
    return DeviceRead.model_validate(device)


@router.get("/{device_id}/metrics", response_model=list[MetricRead])
def read_device_metrics(
    device_id: int,
    db: Database,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MetricRead]:
    device = _owned_device(db, user, device_id)
    metrics = list_device_metrics(db, device.id, limit)
    return [MetricRead.model_validate(metric) for metric in metrics]


@router.post(
    "/{device_id}/credentials",
    response_model=AgentCredential,
)
def rotate_credential(
    device_id: int,
    db: Database,
    user: CurrentUser,
) -> AgentCredential:
    device = _owned_device(db, user, device_id)
    device, credential = rotate_device_credential(db, device)
    return AgentCredential(device=DeviceRead.model_validate(device), agent_key=credential)


@router.delete(
    "/{device_id}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_credential(device_id: int, db: Database, user: CurrentUser) -> Response:
    device = _owned_device(db, user, device_id)
    revoke_device_credential(db, device)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
