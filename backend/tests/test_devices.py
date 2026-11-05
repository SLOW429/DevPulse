from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device

PASSWORD = "a-long-password-1"


def _token(client: TestClient, email: str) -> str:
    registered = client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert registered.status_code == 201
    response = client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _register_device(client: TestClient, token: str) -> dict[str, object]:
    response = client.post(
        "/devices",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "edge-host", "hostname": "edge.example", "os": "Linux"},
    )
    assert response.status_code == 201
    return response.json()


def test_device_management_requires_user_authentication(client: TestClient) -> None:
    assert client.get("/devices").status_code == 401
    assert client.post("/devices", json={"name": "host"}).status_code == 401


def test_registration_issues_one_time_secret_and_unique_agent_id(
    client: TestClient, db: Session
) -> None:
    token = _token(client, "owner@example.com")

    response = _register_device(client, token)
    device_data = response["device"]
    agent_key = response["agent_key"]
    device = db.scalar(select(Device).where(Device.id == device_data["id"]))

    assert device_data["status"] == "unknown"
    assert device_data["agent_id"]
    assert agent_key.startswith(f"dp_{device.api_key_prefix}_")
    assert device.api_key_hash != agent_key
    assert "agent_key" not in client.get(
        "/devices", headers={"Authorization": f"Bearer {token}"}
    ).json()[0]


def test_heartbeat_updates_status_and_revoked_credentials_are_rejected(
    client: TestClient,
) -> None:
    token = _token(client, "heartbeat@example.com")
    device = _register_device(client, token)
    agent_key = device["agent_key"]
    agent_headers = {"Authorization": f"Bearer {agent_key}"}

    heartbeat = client.post("/agent/heartbeat", headers=agent_headers, json={})
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "online"
    assert heartbeat.json()["agent_id"] == device["device"]["agent_id"]

    revoked = client.delete(
        f"/devices/{device['device']['id']}/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoked.status_code == 204
    rejected = client.post("/agent/heartbeat", headers=agent_headers, json={})
    assert rejected.status_code == 401
    devices = client.get(
        "/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert devices.json()[0]["status"] == "offline"


def test_rotating_credentials_invalidates_old_key_and_accepts_new_key(
    client: TestClient,
) -> None:
    token = _token(client, "rotate@example.com")
    device = _register_device(client, token)
    client.post(
        "/agent/heartbeat",
        headers={"Authorization": f"Bearer {device['agent_key']}"},
        json={},
    )
    rotated = client.post(
        f"/devices/{device['device']['id']}/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert rotated.status_code == 200
    assert rotated.json()["device"]["agent_id"] == device["device"]["agent_id"]
    assert rotated.json()["device"]["status"] == "unknown"
    assert rotated.json()["device"]["last_seen_at"] is None
    assert client.post(
        "/agent/heartbeat",
        headers={"Authorization": f"Bearer {device['agent_key']}"},
        json={},
    ).status_code == 401
    assert client.post(
        "/agent/heartbeat",
        headers={"Authorization": f"Bearer {rotated.json()['agent_key']}"},
        json={},
    ).status_code == 200


def test_device_access_is_limited_to_its_owner(client: TestClient) -> None:
    owner_token = _token(client, "device-owner@example.com")
    other_token = _token(client, "other-owner@example.com")
    device = _register_device(client, owner_token)

    response = client.get(
        f"/devices/{device['device']['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_unseen_device_becomes_offline_after_timeout(
    client: TestClient, db: Session
) -> None:
    token = _token(client, "offline@example.com")
    device = _register_device(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/agent/heartbeat",
        headers={"Authorization": f"Bearer {device['agent_key']}"},
        json={},
    )
    db.expire_all()
    stored = db.scalar(select(Device).where(Device.id == device["device"]["id"]))
    stored.last_seen_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()

    response = client.get("/devices", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "offline"
    assert stored.status.value == "offline"
