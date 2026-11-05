import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.alert import (
    Alert,
    AlertMetric,
    AlertOperator,
    AlertRule,
    AlertRuleState,
    AlertSeverity,
    AlertStatus,
    NotificationDelivery,
    NotificationStatus,
)
from app.models.device import Device
from app.models.metric import Metric
from app.schemas.alerts import AlertRuleCreate, AlertRuleUpdate

logger = logging.getLogger(__name__)

METRIC_FIELDS = {
    AlertMetric.CPU: "cpu_percent",
    AlertMetric.RAM: "ram_percent",
    AlertMetric.DISK: "disk_percent",
}


class TelegramNotConfiguredError(Exception):
    pass


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_owned_rule(db: Session, owner_id: int, rule_id: int) -> AlertRule | None:
    return db.scalar(
        select(AlertRule).where(
            AlertRule.id == rule_id, AlertRule.owner_id == owner_id
        )
    )


def list_rules(db: Session, owner_id: int) -> list[AlertRule]:
    return list(
        db.scalars(
            select(AlertRule)
            .where(AlertRule.owner_id == owner_id)
            .order_by(AlertRule.created_at.desc(), AlertRule.id.desc())
        )
    )


def _validate_device_scope(
    db: Session, owner_id: int, device_id: int | None
) -> None:
    if device_id is not None and db.scalar(
        select(Device.id).where(
            Device.id == device_id, Device.owner_id == owner_id
        )
    ) is None:
        raise ValueError("device not found")


def create_rule(db: Session, owner_id: int, data: AlertRuleCreate) -> AlertRule:
    _validate_device_scope(db, owner_id, data.device_id)
    values = data.model_dump()
    if data.metric == AlertMetric.DEVICE_OFFLINE and data.threshold is None:
        values["threshold"] = float(settings.device_offline_after_seconds)
    rule = AlertRule(owner_id=owner_id, **values)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session, rule: AlertRule, data: AlertRuleUpdate
) -> AlertRule:
    values = data.model_dump(exclude_unset=True)
    if "metric" in values and values["metric"] != rule.metric:
        if values["metric"] == AlertMetric.DEVICE_OFFLINE:
            values.setdefault("operator", None)
            values.setdefault(
                "threshold", float(settings.device_offline_after_seconds)
            )
    if "name" in values:
        if values["name"] is None:
            raise ValueError("name cannot be blank")
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise ValueError("name cannot be blank")
    if "device_id" in values:
        _validate_device_scope(db, rule.owner_id, values["device_id"])

    merged = {
        "name": values.get("name", rule.name),
        "device_id": values.get("device_id", rule.device_id),
        "metric": values.get("metric", rule.metric),
        "operator": values.get("operator", rule.operator),
        "threshold": values.get("threshold", rule.threshold),
        "severity": values.get("severity", rule.severity),
        "evaluation_interval_seconds": values.get(
            "evaluation_interval_seconds", rule.evaluation_interval_seconds
        ),
        "consecutive_violations": values.get(
            "consecutive_violations", rule.consecutive_violations
        ),
        "enabled": values.get("enabled", rule.enabled),
    }
    validated = AlertRuleCreate.model_validate(merged)
    state_fields = (
        "device_id",
        "metric",
        "operator",
        "threshold",
        "severity",
        "evaluation_interval_seconds",
        "consecutive_violations",
        "enabled",
    )
    configuration_changed = any(
        getattr(rule, field) != getattr(validated, field)
        for field in state_fields
    )
    if configuration_changed:
        reason = "Rule disabled" if rule.enabled and not validated.enabled else "Rule updated"
        resolve_rule_incidents(db, rule, datetime.now(UTC), reason)
        db.execute(
            delete(AlertRuleState).where(AlertRuleState.rule_id == rule.id)
        )
    for key, value in validated.model_dump().items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule: AlertRule) -> None:
    resolve_rule_incidents(db, rule, datetime.now(UTC), "Rule deleted")
    db.execute(
        update(Alert).where(Alert.rule_id == rule.id).values(rule_id=None)
    )
    db.execute(
        delete(AlertRuleState).where(AlertRuleState.rule_id == rule.id)
    )
    db.delete(rule)
    db.commit()


def resolve_rule_incidents(
    db: Session, rule: AlertRule, resolved_at: datetime, reason: str
) -> None:
    incidents = list(
        db.scalars(
            select(Alert).where(
                Alert.rule_id == rule.id,
                Alert.status != AlertStatus.RESOLVED,
            )
        )
    )
    for incident in incidents:
        _resolve_incident(db, incident, resolved_at, reason)


def _compare(value: float, operator: AlertOperator, threshold: float) -> bool:
    return {
        AlertOperator.GT: value > threshold,
        AlertOperator.GTE: value >= threshold,
        AlertOperator.LT: value < threshold,
        AlertOperator.LTE: value <= threshold,
    }[operator]


def _get_state(db: Session, rule_id: int, device_id: int) -> AlertRuleState:
    state = db.scalar(
        select(AlertRuleState).where(
            AlertRuleState.rule_id == rule_id,
            AlertRuleState.device_id == device_id,
        )
        .with_for_update()
    )
    if state is None:
        state = AlertRuleState(rule_id=rule_id, device_id=device_id)
        db.add(state)
        db.flush()
    return state


def _active_incident(
    db: Session, rule_id: int, device_id: int
) -> Alert | None:
    return db.scalar(
        select(Alert).where(
            Alert.rule_id == rule_id,
            Alert.device_id == device_id,
            Alert.status != AlertStatus.RESOLVED,
        )
        .with_for_update()
    )


def _queue_notification(db: Session, incident: Alert, event_type: str) -> None:
    db.add(
        NotificationDelivery(
            alert_id=incident.id,
            event_type=event_type,
            status=NotificationStatus.PENDING,
            next_attempt_at=datetime.now(UTC),
        )
    )


def _fire_incident(
    db: Session,
    rule: AlertRule,
    device: Device,
    observed: float,
    triggered_at: datetime,
) -> None:
    threshold = (
        rule.threshold or settings.device_offline_after_seconds
        if rule.metric == AlertMetric.DEVICE_OFFLINE
        else rule.threshold
    )
    label = "Device offline" if rule.metric == AlertMetric.DEVICE_OFFLINE else (
        f"{rule.metric.value.upper()} {rule.operator.value} {rule.threshold:g}%"
    )
    incident = Alert(
        device_id=device.id,
        rule_id=rule.id,
        rule_name=rule.name,
        metric_name=rule.metric.value,
        threshold=threshold,
        observed_value=observed,
        severity=rule.severity,
        status=AlertStatus.OPEN,
        message=f"{device.name}: {label} (observed {observed:g})",
        triggered_at=triggered_at,
    )
    db.add(incident)
    db.flush()
    _queue_notification(db, incident, "fired")


def _resolve_incident(
    db: Session, incident: Alert, resolved_at: datetime, reason: str
) -> None:
    if incident.status == AlertStatus.RESOLVED:
        return
    incident.status = AlertStatus.RESOLVED
    incident.resolved_at = resolved_at
    incident.message = f"{incident.message} — {reason}"
    _queue_notification(db, incident, "resolved")


def _evaluate_rule(
    db: Session,
    rule: AlertRule,
    device: Device,
    value: float,
    evaluated_at: datetime,
    metric_id: int | None,
) -> None:
    state = _get_state(db, rule.id, device.id)
    evaluated_at = _aware(evaluated_at)
    if (
        state.last_evaluated_at is not None
        and (evaluated_at - _aware(state.last_evaluated_at)).total_seconds()
        < rule.evaluation_interval_seconds
    ):
        state.last_evaluated_metric_id = metric_id
        return

    state.last_evaluated_at = evaluated_at
    state.last_evaluated_metric_id = metric_id
    is_violating = (
        True
        if rule.metric == AlertMetric.DEVICE_OFFLINE
        else _compare(value, rule.operator, rule.threshold)
    )
    incident = _active_incident(db, rule.id, device.id)
    if is_violating:
        state.consecutive_count += 1
        if (
            incident is None
            and state.consecutive_count >= rule.consecutive_violations
        ):
            _fire_incident(db, rule, device, value, evaluated_at)
    else:
        state.consecutive_count = 0
        if incident is not None:
            _resolve_incident(db, incident, evaluated_at, "Condition cleared")


def evaluate_pending_metrics(
    db: Session, batch_size: int | None = None
) -> int:
    now = datetime.now(UTC)
    size = batch_size or settings.alert_worker_batch_size
    older_metric = aliased(Metric)
    older_unevaluated_metric = exists(
        select(1).where(
            older_metric.device_id == Metric.device_id,
            older_metric.id < Metric.id,
            older_metric.alerts_evaluated_at.is_(None),
        )
    )
    pending = list(
        db.scalars(
            select(Metric)
            .where(
                Metric.alerts_evaluated_at.is_(None),
                or_(
                    Metric.next_alert_evaluation_at.is_(None),
                    Metric.next_alert_evaluation_at <= now,
                ),
                ~older_unevaluated_metric,
            )
            .order_by(Metric.id)
            .limit(size)
            .with_for_update(skip_locked=True)
        )
    )
    processed = 0
    for metric in pending:
        try:
            with db.begin_nested():
                device = db.get(Device, metric.device_id)
                if device is not None:
                    received_at = _aware(metric.received_at)
                    collected_at = _aware(metric.collected_at)
                    metric_age = (
                        now - min(received_at, collected_at)
                    ).total_seconds()
                    is_stale = metric_age > settings.device_offline_after_seconds
                    rules = list(
                        db.scalars(
                            select(AlertRule).where(
                                AlertRule.owner_id == device.owner_id,
                                AlertRule.enabled.is_(True),
                                (AlertRule.device_id.is_(None))
                                | (AlertRule.device_id == device.id),
                                AlertRule.metric.in_(
                                    [AlertMetric.CPU, AlertMetric.RAM, AlertMetric.DISK]
                                ),
                            )
                        )
                    )
                    if not is_stale:
                        for rule in rules:
                            value = getattr(metric, METRIC_FIELDS[rule.metric])
                            _evaluate_rule(
                                db, rule, device, value, received_at, metric.id
                            )
                    else:
                        for rule in rules:
                            state = _get_state(db, rule.id, device.id)
                            state.consecutive_count = 0
                metric.alerts_evaluated_at = now
                metric.alert_evaluation_error = None
                metric.next_alert_evaluation_at = None
            processed += 1
        except Exception as exc:
            logger.error(
                "alert_metric_evaluation_failed",
                extra={"metric_id": metric.id, "error_type": type(exc).__name__},
            )
            metric.alert_evaluation_attempts += 1
            metric.alert_evaluation_error = "evaluation_failed"
            metric.next_alert_evaluation_at = datetime.now(UTC) + timedelta(
                seconds=min(60, 2 ** min(metric.alert_evaluation_attempts, 6))
            )
    if pending:
        db.commit()
    return processed


def evaluate_offline_rules(db: Session, batch_size: int | None = None) -> int:
    now = datetime.now(UTC)
    size = batch_size or settings.alert_worker_batch_size
    rules = list(
        db.scalars(
            select(AlertRule)
            .where(
                AlertRule.enabled.is_(True),
                AlertRule.metric == AlertMetric.DEVICE_OFFLINE,
            )
            .order_by(AlertRule.id)
            .limit(size)
            .with_for_update(skip_locked=True)
        )
    )
    evaluated = 0
    for rule in rules:
        devices_query = select(Device).where(Device.owner_id == rule.owner_id)
        if rule.device_id is not None:
            devices_query = devices_query.where(Device.id == rule.device_id)
        for device in db.scalars(devices_query):
            last_seen = device.last_seen_at or device.created_at
            age = max(0.0, (now - _aware(last_seen)).total_seconds())
            offline_after = rule.threshold or settings.device_offline_after_seconds
            offline = (
                age >= offline_after
                or device.credential_revoked_at is not None
            )
            if device.last_seen_at is None and (
                now - _aware(device.created_at)
            ).total_seconds() < offline_after:
                offline = False
            state = _get_state(db, rule.id, device.id)
            if (
                state.last_evaluated_at is not None
                and (now - _aware(state.last_evaluated_at)).total_seconds()
                < rule.evaluation_interval_seconds
            ):
                continue
            state.last_evaluated_at = now
            state.last_evaluated_metric_id = None
            state.consecutive_count = state.consecutive_count + 1 if offline else 0
            incident = _active_incident(db, rule.id, device.id)
            if offline:
                if (
                    incident is None
                    and state.consecutive_count >= rule.consecutive_violations
                ):
                    _fire_incident(db, rule, device, age, now)
            elif incident is not None:
                _resolve_incident(db, incident, now, "Device is online")
            evaluated += 1
    if rules:
        db.commit()
    return evaluated


def _due_deliveries(
    db: Session, now: datetime
) -> list[NotificationDelivery]:
    stale_sending_before = now - timedelta(
        seconds=settings.alert_notification_sending_timeout_seconds
    )
    return list(
        db.scalars(
            select(NotificationDelivery)
            .where(
                (
                    (NotificationDelivery.status == NotificationStatus.PENDING)
                    & (
                        (NotificationDelivery.next_attempt_at.is_(None))
                        | (NotificationDelivery.next_attempt_at <= now)
                    )
                )
                | (
                    (NotificationDelivery.status == NotificationStatus.SENDING)
                    & or_(
                        NotificationDelivery.sending_at.is_(None),
                        NotificationDelivery.sending_at <= stale_sending_before,
                    )
                )
            )
            .order_by(NotificationDelivery.created_at, NotificationDelivery.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
    )


def send_telegram_notification(delivery: NotificationDelivery, incident: Alert, device: Device) -> None:
    import json
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if (
        token is None
        or not token.get_secret_value().strip()
        or not chat_id
        or not chat_id.strip()
    ):
        raise TelegramNotConfiguredError
    event = "fired" if delivery.event_type == "fired" else "resolved"
    body = {
        "chat_id": chat_id,
        "text": (
            f"DevPulse alert {event}: {incident.severity.value.upper()}\n"
            f"Device: {device.name}\n"
            f"Condition: {incident.rule_name or incident.metric_name}\n"
            f"Observed: {incident.observed_value}\n"
            f"Message: {incident.message}"
        ),
    }
    request = Request(
        f"https://api.telegram.org/bot{token.get_secret_value()}/sendMessage",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.telegram_api_timeout_seconds) as response:
            result = json.loads(response.read())
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("telegram_delivery_failed") from exc
    if not result.get("ok"):
        raise RuntimeError("telegram_delivery_failed")


def dispatch_due_notifications(
    db: Session, batch_size: int | None = None
) -> int:
    size = batch_size or settings.alert_worker_batch_size
    sent = 0
    for _ in range(size):
        now = datetime.now(UTC)
        deliveries = _due_deliveries(db, now)
        if not deliveries:
            break
        delivery = deliveries[0]
        delivery.status = NotificationStatus.SENDING
        delivery.sending_at = now
        delivery.attempts += 1
        db.commit()

        incident = db.get(Alert, delivery.alert_id)
        device = db.get(Device, incident.device_id) if incident else None
        if incident is None or device is None:
            delivery.status = NotificationStatus.FAILED
            delivery.last_error = "related_record_missing"
            db.commit()
            continue
        try:
            send_telegram_notification(delivery, incident, device)
        except TelegramNotConfiguredError:
            delivery.status = NotificationStatus.DISABLED
            delivery.last_error = "telegram_not_configured"
            delivery.sending_at = None
            delivery.next_attempt_at = None
        except Exception as exc:
            delivery.last_error = "telegram_delivery_failed"
            delivery.sending_at = None
            if delivery.attempts >= settings.alert_notification_max_attempts:
                delivery.status = NotificationStatus.FAILED
                delivery.next_attempt_at = None
            else:
                delivery.status = NotificationStatus.PENDING
                delay = settings.alert_notification_retry_base_seconds * (
                    2 ** (delivery.attempts - 1)
                )
                delivery.next_attempt_at = now + timedelta(
                    seconds=min(delay, 3600)
                )
            logger.warning(
                "alert_notification_delivery_failed",
                extra={
                    "delivery_id": delivery.id,
                    "attempt": delivery.attempts,
                    "error_type": type(exc).__name__,
                    "status": delivery.status.value,
                },
            )
        else:
            delivery.status = NotificationStatus.DELIVERED
            delivery.delivered_at = datetime.now(UTC)
            delivery.sending_at = None
            delivery.next_attempt_at = None
            delivery.last_error = None
            sent += 1
        db.commit()
    return sent


def list_alerts(
    db: Session,
    owner_id: int,
    limit: int,
    offset: int,
    active_only: bool | None,
    severity: AlertSeverity | None,
    device_id: int | None,
) -> tuple[list[Alert], int]:
    statement = (
        select(Alert)
        .join(Device, Device.id == Alert.device_id)
        .where(Device.owner_id == owner_id)
    )
    if active_only is True:
        statement = statement.where(Alert.status != AlertStatus.RESOLVED)
    elif active_only is False:
        statement = statement.where(Alert.status == AlertStatus.RESOLVED)
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if device_id is not None:
        statement = statement.where(Alert.device_id == device_id)
    count = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    incidents = list(
        db.scalars(
            statement.options(
                selectinload(Alert.notifications),
                selectinload(Alert.device),
            )
            .order_by(Alert.triggered_at.desc(), Alert.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return incidents, count
