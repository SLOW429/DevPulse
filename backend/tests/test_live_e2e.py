import json
import os
import subprocess
import sys
import time
from pathlib import Path
from secrets import token_urlsafe
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from websockets.sync.client import connect

from app.core.config import settings

API_URL = os.getenv("DEVPULSE_E2E_API_URL", "").rstrip("/")
DATABASE_URL = os.getenv("POSTGRES_E2E_URL")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_CONFIGURED = bool(
    settings.telegram_bot_token
    and settings.telegram_bot_token.get_secret_value().strip()
    and settings.telegram_chat_id
    and settings.telegram_chat_id.strip()
)
E2E_ENABLED = bool(API_URL and DATABASE_URL)
pytestmark = pytest.mark.skipif(
    not E2E_ENABLED,
    reason=(
        "Set DEVPULSE_E2E_API_URL and POSTGRES_E2E_URL to run real "
        "infrastructure end-to-end checks"
    ),
)


def _request(
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, object] | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, object]:
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urlencode(form).encode()
    request = Request(
        f"{API_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:
            data = response.read()
    except HTTPError as exc:
        raise AssertionError(
            f"{method} {path} returned HTTP {exc.code}: "
            f"{exc.read().decode(errors='replace')}"
        ) from exc
    return json.loads(data) if data else {}


def _run_real_agent(api_url: str, agent_key: str) -> None:
    environment = os.environ.copy()
    environment["DEVPULSE_API_URL"] = api_url
    environment["DEVPULSE_AGENT_KEY"] = agent_key
    subprocess.run(
        [sys.executable, "-m", "agent.main", "--once"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _wait_for_incident(
    token: str, rule_id: int, expected_status: str, timeout: int = 120
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        page = _request(
            "/alerts?limit=100",
            token=token,
        )
        incidents = page.get("items", [])
        match = next(
            (
                incident
                for incident in incidents
                if incident["rule_id"] == rule_id
                and incident["status"] == expected_status
            ),
            None,
        )
        if match is not None:
            return match
        time.sleep(1)
    raise AssertionError(
        f"Timed out waiting for rule {rule_id} to become {expected_status}"
    )


def _wait_for_delivery(
    token: str,
    alert_id: int,
    event_type: str,
    expected_status: str,
    timeout: int = 120,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        page = _request("/alerts?limit=100", token=token)
        incident = next(
            (item for item in page.get("items", []) if item["id"] == alert_id),
            None,
        )
        if incident is not None:
            deliveries = [
                item
                for item in incident["notifications"]
                if item["event_type"] == event_type
            ]
            if deliveries and deliveries[0]["status"] == expected_status:
                assert len(deliveries) == 1
                return
            if deliveries and deliveries[0]["status"] in {
                "failed",
                "disabled",
            }:
                raise AssertionError(
                    f"Notification {event_type} ended with "
                    f"{deliveries[0]['status']}, expected {expected_status}"
                )
        time.sleep(1)
    raise AssertionError(
        f"Timed out waiting for notification {event_type} status "
        f"{expected_status}"
    )


def _websocket_uri(ticket: str) -> str:
    parsed = urlsplit(API_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit(
        (scheme, parsed.netloc, "/ws/dashboard", urlencode({"ticket": ticket}), "")
    )


def _verify_websocket_update(
    token: str,
    device_id: int,
    previous_metric_id: int,
    agent_key: str,
) -> None:
    ticket = _request(
        "/realtime/ticket",
        method="POST",
        token=token,
    )["ticket"]
    with connect(_websocket_uri(ticket), open_timeout=10, close_timeout=2) as socket:
        initial = json.loads(socket.recv(timeout=10))
        initial_device = next(
            item for item in initial["devices"] if item["id"] == device_id
        )
        assert initial_device["latest_metric"]["id"] == previous_metric_id
        _run_real_agent(API_URL, agent_key)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            snapshot = json.loads(socket.recv(timeout=10))
            device = next(
                item for item in snapshot["devices"] if item["id"] == device_id
            )
            latest = device["latest_metric"]
            if latest and latest["id"] != previous_metric_id:
                return
        raise AssertionError("Authenticated WebSocket did not publish new metrics")


def test_real_agent_postgres_alert_and_telegram_flow() -> None:
    assert DATABASE_URL is not None
    database_name = make_url(DATABASE_URL).database
    if not database_name or not database_name.endswith("_e2e_test"):
        pytest.fail("POSTGRES_E2E_URL must target a dedicated *_e2e_test database")

    email = f"e2e-{token_urlsafe(12)}@example.com"
    password = token_urlsafe(32)
    _request(
        "/auth/register",
        method="POST",
        payload={"email": email, "password": password},
    )
    token = _request(
        "/auth/login",
        method="POST",
        form={"username": email, "password": password},
    )["access_token"]
    enrollment = _request(
        "/devices",
        method="POST",
        token=token,
        payload={"name": "live-e2e-agent"},
    )
    device = enrollment["device"]
    agent_key = enrollment["agent_key"]
    rule = _request(
        "/alerts/rules",
        method="POST",
        token=token,
        payload={
            "name": "E2E agent offline",
            "device_id": device["id"],
            "metric": "device_offline",
            "threshold": 5,
            "evaluation_interval_seconds": 5,
            "consecutive_violations": 1,
        },
    )

    _run_real_agent(API_URL, agent_key)

    deadline = time.monotonic() + 30
    dashboard = {}
    while time.monotonic() < deadline:
        dashboard = _request("/dashboard", token=token)
        current = next(
            (item for item in dashboard["devices"] if item["id"] == device["id"]),
            None,
        )
        if current and current["latest_metric"]:
            break
        time.sleep(1)
    else:
        raise AssertionError("Real agent metrics did not reach the dashboard")

    metric = current["latest_metric"]
    for field in (
        "cpu_percent",
        "ram_percent",
        "disk_percent",
        "net_bytes_sent",
        "net_bytes_recv",
        "uptime_seconds",
    ):
        assert metric[field] >= 0

    engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            stored = connection.execute(
                sa.text(
                    "SELECT cpu_percent, ram_percent, disk_percent, "
                    "net_bytes_sent, net_bytes_recv, uptime_seconds "
                    "FROM metrics WHERE device_id = :device "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"device": device["id"]},
            ).mappings().one()
            assert dict(stored) == {
                key: metric[key]
                for key in (
                    "cpu_percent",
                    "ram_percent",
                    "disk_percent",
                    "net_bytes_sent",
                    "net_bytes_recv",
                    "uptime_seconds",
                )
            }
    finally:
        engine.dispose()

    _verify_websocket_update(token, device["id"], metric["id"], agent_key)

    firing = _wait_for_incident(token, rule["id"], "firing")
    delivery_status = "delivered" if TELEGRAM_CONFIGURED else "disabled"
    _wait_for_delivery(token, firing["id"], "fired", delivery_status)

    _run_real_agent(API_URL, agent_key)
    resolved = _wait_for_incident(token, rule["id"], "resolved")
    assert resolved["id"] == firing["id"]
    _wait_for_delivery(token, firing["id"], "resolved", delivery_status)
