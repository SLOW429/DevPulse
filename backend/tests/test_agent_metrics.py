import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.metric import Metric

PASSWORD = "a-long-password-1"


def _create_device(client: TestClient, email: str) -> tuple[str, str, int]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    login = client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    user_token = login.json()["access_token"]
    response = client.post(
        "/devices",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "test-monitor"},
    )
    body = response.json()
    return user_token, body["agent_key"], body["device"]["id"]


def _metric_payload(collected_at: str | None = None) -> dict[str, object]:
    return {
        "collected_at": collected_at or datetime.now(UTC).isoformat(),
        "cpu_percent": 23.5,
        "ram_percent": 61.2,
        "disk_percent": 72.0,
        "net_bytes_sent": 1024,
        "net_bytes_recv": 2048,
        "uptime_seconds": 86400,
    }


def test_metrics_are_persisted_and_update_device_heartbeat(
    client: TestClient, db: Session
) -> None:
    user_token, agent_key, device_id = _create_device(client, "metric-owner@example.com")

    response = client.post(
        "/agent/metrics",
        headers={"Authorization": f"Bearer {agent_key}"},
        json=_metric_payload(),
    )

    assert response.status_code == 201
    assert response.json()["device_id"] == device_id
    assert response.json()["cpu_percent"] == 23.5
    assert db.scalar(select(Metric).where(Metric.device_id == device_id)) is not None
    device = db.get(Device, device_id)
    assert device.status.value == "online"
    assert device.last_seen_at is not None

    history = client.get(
        f"/devices/{device_id}/metrics",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == response.json()["id"]

    dashboard = client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert dashboard.status_code == 200
    dashboard_device = dashboard.json()["devices"][0]
    assert dashboard_device["latest_metric"]["id"] == response.json()["id"]
    assert dashboard_device["latest_metric"]["cpu_percent"] == 23.5


def test_metrics_require_valid_agent_credentials(client: TestClient) -> None:
    response = client.post(
        "/agent/metrics",
        headers={"Authorization": "Bearer dp_invalid_key"},
        json=_metric_payload(),
    )

    assert response.status_code == 401


def test_metrics_reject_percentages_out_of_range(client: TestClient) -> None:
    _, agent_key, _ = _create_device(client, "range-owner@example.com")
    payload = _metric_payload()
    payload["cpu_percent"] = 101

    response = client.post(
        "/agent/metrics",
        headers={"Authorization": f"Bearer {agent_key}"},
        json=payload,
    )

    assert response.status_code == 422


def test_metrics_reject_negative_counters(client: TestClient) -> None:
    _, agent_key, _ = _create_device(client, "counter-owner@example.com")
    payload = _metric_payload()
    payload["net_bytes_sent"] = -1

    response = client.post(
        "/agent/metrics",
        headers={"Authorization": f"Bearer {agent_key}"},
        json=payload,
    )

    assert response.status_code == 422


def test_metrics_require_aware_non_future_timestamps(client: TestClient) -> None:
    _, agent_key, _ = _create_device(client, "timestamp-owner@example.com")
    headers = {"Authorization": f"Bearer {agent_key}"}

    naive = client.post(
        "/agent/metrics",
        headers=headers,
        json=_metric_payload(datetime.now().isoformat()),
    )
    future = client.post(
        "/agent/metrics",
        headers=headers,
        json=_metric_payload(
            (datetime.now(UTC) + timedelta(minutes=6)).isoformat()
        ),
    )

    assert naive.status_code == 422
    assert future.status_code == 422


def test_metrics_reject_non_finite_percentages(client: TestClient) -> None:
    _, agent_key, _ = _create_device(client, "finite-owner@example.com")
    payload = _metric_payload()
    payload["ram_percent"] = float("nan")

    response = client.post(
        "/agent/metrics",
        headers={
            "Authorization": f"Bearer {agent_key}",
            "Content-Type": "application/json",
        },
        content=json.dumps(payload, allow_nan=True),
    )

    assert response.status_code == 422
