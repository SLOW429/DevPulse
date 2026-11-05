from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import (
    Alert,
    AlertRule,
    AlertRuleState,
    AlertStatus,
    NotificationDelivery,
    NotificationStatus,
)
from app.models.device import Device
from app.models.metric import Metric
from app.services import alert_service
from app.worker import run_alert_worker

PASSWORD = "a-long-password-1"


def _create_user_and_device(
    client: TestClient, email: str
) -> tuple[str, int, str]:
    assert client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD},
    ).status_code == 201
    login = client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    token = login.json()["access_token"]
    device = client.post(
        "/devices",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "alert-test-host"},
    ).json()
    return token, device["device"]["id"], device["agent_key"]


def _add_metric(
    db: Session, device_id: int, received_at: datetime, cpu_percent: float
) -> Metric:
    metric = Metric(
        device_id=device_id,
        collected_at=received_at,
        received_at=received_at,
        cpu_percent=cpu_percent,
        ram_percent=40,
        disk_percent=50,
        net_bytes_sent=100,
        net_bytes_recv=200,
        uptime_seconds=1000,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def test_rule_validation_and_device_owner_scope(client: TestClient) -> None:
    owner_token, device_id, _ = _create_user_and_device(client, "alerts-owner@example.com")
    other_token, _, _ = _create_user_and_device(client, "alerts-other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    invalid = client.post(
        "/alerts/rules",
        headers=owner_headers,
        json={"name": "CPU", "metric": "cpu"},
    )
    foreign_device = client.post(
        "/alerts/rules",
        headers=other_headers,
        json={
            "name": "CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 80,
        },
    )
    valid = client.post(
        "/alerts/rules",
        headers=owner_headers,
        json={
            "name": "CPU high",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 80,
            "consecutive_violations": 2,
        },
    )

    assert invalid.status_code == 422
    assert foreign_device.status_code == 422
    assert valid.status_code == 201
    rule_id = valid.json()["id"]
    assert client.get("/alerts/rules", headers=other_headers).json() == []
    assert client.patch(
        f"/alerts/rules/{rule_id}",
        headers=other_headers,
        json={"enabled": False},
    ).status_code == 404


def test_consecutive_violations_fire_once_and_condition_resolves(
    client: TestClient, db: Session, monkeypatch
) -> None:
    token, device_id, _ = _create_user_and_device(client, "evaluation@example.com")
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr("test-token"))
    monkeypatch.setattr(settings, "telegram_chat_id", "test-chat")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "Sustained CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gte",
            "threshold": 80,
            "evaluation_interval_seconds": 5,
            "consecutive_violations": 2,
        },
    )
    assert created.status_code == 201
    start = datetime.now(UTC) - timedelta(seconds=30)
    _add_metric(db, device_id, start, 90)
    _add_metric(db, device_id, start + timedelta(seconds=6), 91)

    assert alert_service.evaluate_pending_metrics(db) == 1
    assert alert_service.evaluate_pending_metrics(db) == 1
    assert alert_service.evaluate_pending_metrics(db) == 0
    incidents = list(db.scalars(select(Alert)))
    assert len(incidents) == 1
    assert incidents[0].status == AlertStatus.OPEN
    assert incidents[0].observed_value == 91
    fired = db.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.alert_id == incidents[0].id,
            NotificationDelivery.event_type == "fired",
        )
    )
    assert fired.status == NotificationStatus.PENDING

    _add_metric(db, device_id, start + timedelta(seconds=12), 92)
    assert alert_service.evaluate_pending_metrics(db) == 1
    assert len(list(db.scalars(select(Alert)))) == 1

    _add_metric(db, device_id, start + timedelta(seconds=18), 30)
    assert alert_service.evaluate_pending_metrics(db) == 1
    db.refresh(incidents[0])
    assert incidents[0].status == AlertStatus.RESOLVED
    assert incidents[0].resolved_at is not None
    assert db.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.alert_id == incidents[0].id,
            NotificationDelivery.event_type == "resolved",
        )
    ) is not None


def test_notification_failures_retry_and_do_not_leak_details(
    client: TestClient, db: Session, monkeypatch, caplog
) -> None:
    token, device_id, _ = _create_user_and_device(client, "retry@example.com")
    monkeypatch.setattr(
        settings, "telegram_bot_token", SecretStr("sensitive-token")
    )
    monkeypatch.setattr(settings, "telegram_chat_id", "sensitive-chat")
    monkeypatch.setattr(settings, "alert_notification_max_attempts", 2)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "CPU high",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 80,
        },
    )
    _add_metric(db, device_id, datetime.now(UTC), 99)
    alert_service.evaluate_pending_metrics(db)

    def fail_delivery(*_args) -> None:
        raise RuntimeError("https://api.telegram.org/botsecret/sendMessage")

    monkeypatch.setattr(alert_service, "send_telegram_notification", fail_delivery)
    assert alert_service.dispatch_due_notifications(db) == 0
    delivery = db.scalar(select(NotificationDelivery))
    assert delivery.status == NotificationStatus.PENDING
    assert delivery.attempts == 1
    assert delivery.last_error == "telegram_delivery_failed"
    assert "sensitive" not in repr(delivery)

    delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    alert_service.dispatch_due_notifications(db)
    db.refresh(delivery)
    assert delivery.status == NotificationStatus.FAILED
    assert delivery.attempts == 2
    assert "sensitive-token" not in caplog.text
    assert "sensitive-chat" not in caplog.text
    response = client.get(
        "/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "sensitive-token" not in response.text
    assert "sensitive-chat" not in response.text


def test_missing_telegram_configuration_disables_delivery_without_failure(
    client: TestClient, db: Session, monkeypatch
) -> None:
    token, device_id, _ = _create_user_and_device(
        client, "telegram-disabled@example.com"
    )
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "telegram_chat_id", None)
    client.post(
        "/alerts/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "High CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 70,
        },
    )
    _add_metric(db, device_id, datetime.now(UTC), 99)
    alert_service.evaluate_pending_metrics(db)

    assert alert_service.dispatch_due_notifications(db) == 0
    delivery = db.scalar(select(NotificationDelivery))
    assert delivery.status == NotificationStatus.DISABLED
    assert delivery.last_error == "telegram_not_configured"


def test_disabling_and_deleting_rule_resolves_incident_and_preserves_history(
    client: TestClient, db: Session
) -> None:
    token, device_id, _ = _create_user_and_device(client, "rule-lifecycle@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    rule = client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "High CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 70,
        },
    ).json()
    _add_metric(db, device_id, datetime.now(UTC), 95)
    alert_service.evaluate_pending_metrics(db)

    disabled = client.patch(
        f"/alerts/rules/{rule['id']}",
        headers=headers,
        json={"enabled": False},
    )
    history = client.get("/alerts?active_only=false", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert history.json()["items"][0]["status"] == "resolved"
    assert history.json()["items"][0]["rule_name"] == "High CPU"

    assert client.delete(
        f"/alerts/rules/{rule['id']}", headers=headers
    ).status_code == 204
    preserved = client.get("/alerts?active_only=false", headers=headers)
    assert preserved.json()["total"] == 1
    assert preserved.json()["items"][0]["rule_id"] is None


def test_stale_samples_do_not_fire_alerts(client: TestClient, db: Session) -> None:
    token, device_id, _ = _create_user_and_device(client, "stale-alert@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "High CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 70,
        },
    )
    old = datetime.now(UTC) - timedelta(
        seconds=settings.device_offline_after_seconds + 10
    )
    _add_metric(db, device_id, old, 99)

    alert_service.evaluate_pending_metrics(db)

    assert db.scalar(select(Alert)) is None


def test_evaluator_rolls_back_partial_work_and_retries_metric(
    client: TestClient, db: Session, monkeypatch
) -> None:
    _, device_id, _ = _create_user_and_device(client, "evaluation-retry@example.com")
    metric = _add_metric(db, device_id, datetime.now(UTC), 99)

    def fail_evaluation(*_args, **_kwargs) -> None:
        raise RuntimeError("evaluation failure")

    monkeypatch.setattr(alert_service, "_evaluate_rule", fail_evaluation)
    token = _request_owner_token(client, "evaluation-retry@example.com")
    client.post(
        "/alerts/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "High CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 70,
        },
    )
    db.expire_all()
    assert alert_service.evaluate_pending_metrics(db) == 0
    db.refresh(metric)
    assert metric.alerts_evaluated_at is None
    assert metric.alert_evaluation_attempts == 1
    assert metric.alert_evaluation_error == "evaluation_failed"
    assert metric.next_alert_evaluation_at is not None
    assert db.scalar(select(Alert)) is None


def _request_owner_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_worker_starts_and_stops_cleanly(monkeypatch) -> None:
    import threading

    stop_event = threading.Event()
    called = threading.Event()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def rollback(self) -> None:
            raise AssertionError("Unexpected worker rollback")

    def run_one_task(_db) -> None:
        called.set()
        stop_event.set()

    monkeypatch.setattr("app.worker.SessionLocal", FakeSession)
    monkeypatch.setattr("app.worker.WORKERS", (run_one_task,))
    thread = threading.Thread(target=run_alert_worker, args=(stop_event,))
    thread.start()
    thread.join(timeout=2)

    assert called.is_set()
    assert not thread.is_alive()


def test_agent_ingestion_persists_alert_job_for_background_processing(
    client: TestClient, db: Session
) -> None:
    token, device_id, agent_key = _create_user_and_device(
        client, "async-ingest@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}
    rule = client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "High CPU",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 70,
        },
    )
    assert rule.status_code == 201

    ingestion = client.post(
        "/agent/metrics",
        headers={"Authorization": f"Bearer {agent_key}"},
        json={
            "collected_at": datetime.now(UTC).isoformat(),
            "cpu_percent": 99,
            "ram_percent": 40,
            "disk_percent": 50,
            "net_bytes_sent": 100,
            "net_bytes_recv": 200,
            "uptime_seconds": 1000,
        },
    )

    assert ingestion.status_code == 201
    recovered_db = Session(db.get_bind())
    try:
        metric = recovered_db.get(Metric, ingestion.json()["id"])
        assert metric is not None
        assert metric.alerts_evaluated_at is None
        assert alert_service.evaluate_pending_metrics(recovered_db) == 1
        assert recovered_db.scalar(select(Alert)).status == AlertStatus.OPEN
    finally:
        recovered_db.close()


def test_offline_rule_waits_for_grace_period_and_fires(client: TestClient, db: Session) -> None:
    token, device_id, _ = _create_user_and_device(client, "offline-alert@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "Host unavailable",
            "metric": "device_offline",
            "threshold": 30,
        },
    )
    assert response.status_code == 201

    device = db.get(Device, device_id)
    assert alert_service.evaluate_offline_rules(db) == 1
    assert db.scalar(select(Alert)) is None
    device.created_at = datetime.now(UTC) - timedelta(
        seconds=40
    )
    state = db.scalar(
        select(AlertRuleState).where(AlertRuleState.rule_id == response.json()["id"])
    )
    state.last_evaluated_at = datetime.now(UTC) - timedelta(seconds=40)
    db.commit()
    assert alert_service.evaluate_offline_rules(db) == 1
    incident = db.scalar(select(Alert))
    assert incident.status == AlertStatus.OPEN
    assert incident.metric_name == "device_offline"
    assert incident.threshold == 30


def test_alert_history_is_owner_scoped_and_paginated(client: TestClient, db: Session) -> None:
    owner_token, device_id, _ = _create_user_and_device(client, "history-owner@example.com")
    other_token, _, _ = _create_user_and_device(client, "history-other@example.com")
    headers = {"Authorization": f"Bearer {owner_token}"}
    client.post(
        "/alerts/rules",
        headers=headers,
        json={
            "name": "CPU high",
            "device_id": device_id,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 80,
        },
    )
    _add_metric(db, device_id, datetime.now(UTC), 99)
    alert_service.evaluate_pending_metrics(db)

    own = client.get("/alerts?limit=1&offset=0&active_only=true", headers=headers)
    other = client.get(
        "/alerts",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert len(own.json()["items"]) == 1
    assert own.json()["items"][0]["device_name"] == "alert-test-host"
    assert own.json()["items"][0]["status"] == "firing"
    assert other.json()["total"] == 0
