from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.models.metric import Metric
from app.models.user import User
from app.schemas.dashboard import DashboardDevice, DashboardSnapshot
from app.schemas.device import DeviceRead
from app.schemas.metric import MetricRead


def get_dashboard_snapshot(db: Session, owner_id: int) -> DashboardSnapshot | None:
    user = db.get(User, owner_id)
    if user is None or not user.is_active:
        return None

    latest_metric_id = (
        select(Metric.id)
        .where(Metric.device_id == Device.id)
        .order_by(Metric.collected_at.desc(), Metric.id.desc())
        .limit(1)
        .correlate(Device)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Device, Metric)
        .outerjoin(Metric, Metric.id == latest_metric_id)
        .where(Device.owner_id == owner_id)
        .order_by(Device.id)
    ).all()
    now = datetime.now(UTC)
    offline_before = now.timestamp() - settings.device_offline_after_seconds
    dashboard_devices: list[DashboardDevice] = []
    status_changed = False

    for device, latest_metric in rows:
        previous_status = device.status
        if device.credential_revoked_at is not None:
            device.status = DeviceStatus.OFFLINE
        elif device.last_seen_at is None:
            device.status = DeviceStatus.UNKNOWN
        else:
            last_seen = device.last_seen_at
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            device.status = (
                DeviceStatus.ONLINE
                if last_seen.timestamp() >= offline_before
                else DeviceStatus.OFFLINE
            )
        status_changed = status_changed or device.status != previous_status

        dashboard_devices.append(
            DashboardDevice(
                **DeviceRead.model_validate(device).model_dump(),
                latest_metric=(
                    MetricRead.model_validate(latest_metric)
                    if latest_metric is not None
                    else None
                ),
            )
        )

    if status_changed:
        db.commit()

    return DashboardSnapshot(generated_at=now, devices=dashboard_devices)
