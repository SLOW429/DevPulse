import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import websocket_tickets


PASSWORD = "a-long-password-1"


def _login(client: TestClient) -> str:
    email = "dashboard@example.com"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD},
    ).status_code == 201
    response = client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    return response.json()["access_token"]


def test_dashboard_requires_authentication(client: TestClient) -> None:
    assert client.get("/dashboard").status_code == 401
    assert client.post("/realtime/ticket").status_code == 401


def test_dashboard_snapshot_lists_owned_devices(client: TestClient) -> None:
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/devices", headers=headers, json={"name": "dashboard-host"})

    response = client.get("/dashboard", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["devices"]) == 1
    device = response.json()["devices"][0]
    assert device["name"] == "dashboard-host"
    assert device["status"] == "unknown"
    assert device["latest_metric"] is None


def test_websocket_ticket_is_single_use_and_streams_dashboard(
    client: TestClient,
) -> None:
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    ticket_response = client.post("/realtime/ticket", headers=headers)
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["ticket"]

    with client.websocket_connect(f"/ws/dashboard?ticket={ticket}") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["devices"] == []

    with pytest.raises(WebSocketDisconnect) as disconnected:
        with client.websocket_connect(f"/ws/dashboard?ticket={ticket}"):
            pass
    assert disconnected.value.code == 4401


def test_websocket_rejects_untrusted_origins(client: TestClient) -> None:
    token = _login(client)
    ticket = client.post(
        "/realtime/ticket",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["ticket"]

    with pytest.raises(WebSocketDisconnect) as disconnected:
        with client.websocket_connect(
            f"/ws/dashboard?ticket={ticket}",
            headers={"origin": "https://untrusted.example"},
        ):
            pass
    assert disconnected.value.code == 4403


def test_websocket_ticket_expiration(monkeypatch) -> None:
    monkeypatch.setattr(websocket_tickets, "_TICKET_LIFETIME_SECONDS", 0)

    ticket, expires_in = websocket_tickets.issue_websocket_ticket(user_id=1)

    assert expires_in == 0
    assert websocket_tickets.consume_websocket_ticket(ticket) is None
