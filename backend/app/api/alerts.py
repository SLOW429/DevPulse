from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.alert import Alert, AlertMetric, AlertSeverity, AlertStatus
from app.models.device import Device
from app.models.user import User
from app.schemas.alerts import (
    AlertPage,
    AlertRead,
    AlertState,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
)
from app.services.alert_service import (
    create_rule,
    delete_rule,
    get_owned_rule,
    list_alerts,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _read_alert(alert: Alert) -> AlertRead:
    try:
        metric = AlertMetric(alert.metric_name)
    except ValueError:
        metric = None
    return AlertRead(
        id=alert.id,
        rule_id=alert.rule_id,
        rule_name=alert.rule_name,
        device_id=alert.device_id,
        device_name=alert.device.name,
        metric=metric,
        metric_name=alert.metric_name,
        severity=alert.severity,
        status=(
            AlertState.RESOLVED
            if alert.status == AlertStatus.RESOLVED
            else AlertState.FIRING
        ),
        threshold=alert.threshold,
        observed_value=alert.observed_value,
        message=alert.message,
        triggered_at=alert.triggered_at,
        resolved_at=alert.resolved_at,
        notifications=alert.notifications,
    )


@router.get("/rules", response_model=list[AlertRuleRead])
def read_rules(db: Database, user: CurrentUser) -> list[AlertRuleRead]:
    return [AlertRuleRead.model_validate(rule) for rule in list_rules(db, user.id)]


@router.post(
    "/rules",
    response_model=AlertRuleRead,
    status_code=status.HTTP_201_CREATED,
)
def add_rule(
    data: AlertRuleCreate, db: Database, user: CurrentUser
) -> AlertRuleRead:
    try:
        rule = create_rule(db, user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AlertRuleRead.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=AlertRuleRead)
def edit_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    db: Database,
    user: CurrentUser,
) -> AlertRuleRead:
    rule = get_owned_rule(db, user.id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    try:
        rule = update_rule(db, rule, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AlertRuleRead.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_rule(rule_id: int, db: Database, user: CurrentUser) -> Response:
    rule = get_owned_rule(db, user.id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    delete_rule(db, rule)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=AlertPage)
def read_alerts(
    db: Database,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    active_only: bool | None = None,
    severity: AlertSeverity | None = None,
    device_id: int | None = Query(default=None, gt=0),
) -> AlertPage:
    if device_id is not None and db.query(Device.id).filter(
        Device.id == device_id, Device.owner_id == user.id
    ).first() is None:
        raise HTTPException(status_code=404, detail="Device not found")
    alerts, total = list_alerts(
        db, user.id, limit, offset, active_only, severity, device_id
    )
    return AlertPage(
        items=[_read_alert(alert) for alert in alerts],
        total=total,
        limit=limit,
        offset=offset,
    )
