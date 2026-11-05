from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.agent_security import (
    create_agent_credential,
    verify_agent_credential,
)
from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.models.metric import Metric
from app.models.user import User
from app.schemas.device import DeviceCreate
from app.schemas.metric import MetricCreate


def register_device(db: Session, owner: User, data: DeviceCreate) -> tuple[Device, str]:
    credential, prefix, digest = create_agent_credential()
    device = Device(
        name=data.name,
        hostname=data.hostname,
        os=data.os,
        owner_id=owner.id,
        api_key_prefix=prefix,
        api_key_hash=digest,
        status=DeviceStatus.UNKNOWN,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device, credential


def list_devices(db: Session, owner_id: int) -> list[Device]:
    devices = list(
        db.scalars(select(Device).where(Device.owner_id == owner_id).order_by(Device.id))
    )
    _refresh_statuses(db, devices)
    return devices


def get_owned_device(db: Session, owner_id: int, device_id: int) -> Device | None:
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == owner_id)
    )
    if device is not None:
        _refresh_statuses(db, [device])
    return device


def rotate_device_credential(
    db: Session, device: Device
) -> tuple[Device, str]:
    credential, prefix, digest = create_agent_credential()
    device.api_key_prefix = prefix
    device.api_key_hash = digest
    device.credential_revoked_at = None
    device.last_seen_at = None
    device.status = DeviceStatus.UNKNOWN
    db.commit()
    db.refresh(device)
    return device, credential


def revoke_device_credential(db: Session, device: Device) -> None:
    device.credential_revoked_at = datetime.now(UTC)
    device.status = DeviceStatus.OFFLINE
    db.commit()


def authenticate_agent(db: Session, credential: str) -> Device | None:
    parts = credential.split("_", maxsplit=2)
    if len(parts) != 3 or parts[0] != "dp" or not parts[1] or not parts[2]:
        return None

    device = db.scalar(
        select(Device).where(Device.api_key_prefix == parts[1])
    )
    if (
        device is None
        or device.credential_revoked_at is not None
        or not verify_agent_credential(credential, device.api_key_hash)
    ):
        return None
    return device


def record_heartbeat(db: Session, device: Device) -> datetime:
    now = datetime.now(UTC)
    device.last_seen_at = now
    device.status = DeviceStatus.ONLINE
    db.commit()
    return now


def record_metric(db: Session, device: Device, data: MetricCreate) -> Metric:
    metric = Metric(device_id=device.id, **data.model_dump())
    device.last_seen_at = datetime.now(UTC)
    device.status = DeviceStatus.ONLINE
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def list_device_metrics(db: Session, device_id: int, limit: int) -> list[Metric]:
    statement = (
        select(Metric)
        .where(Metric.device_id == device_id)
        .order_by(Metric.collected_at.desc(), Metric.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def _refresh_statuses(db: Session, devices: list[Device]) -> None:
    now = datetime.now(UTC)
    offline_before = now - timedelta(seconds=settings.device_offline_after_seconds)
    changed = False

    for device in devices:
        last_seen = device.last_seen_at
        if last_seen is None:
            new_status = (
                DeviceStatus.OFFLINE
                if device.credential_revoked_at is not None
                else DeviceStatus.UNKNOWN
            )
        elif device.credential_revoked_at is not None:
            new_status = DeviceStatus.OFFLINE
        else:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            new_status = (
                DeviceStatus.ONLINE
                if last_seen >= offline_before
                else DeviceStatus.OFFLINE
            )
        if device.status != new_status:
            device.status = new_status
            changed = True

    if changed:
        db.commit()
