from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User, UserRole

VALID_PASSWORD = "a-long-password-1"


def test_register_creates_viewer_and_hides_hash(client: TestClient, db: Session) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "viewer"
    assert "hashed_password" not in body
    assert "password" not in body

    user = db.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert user.role == UserRole.VIEWER
    assert user.hashed_password != VALID_PASSWORD
    assert verify_password(VALID_PASSWORD, user.hashed_password)


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": VALID_PASSWORD}

    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_register_email_is_case_insensitive(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "case@example.com", "password": VALID_PASSWORD},
    )

    response = client.post(
        "/auth/register",
        json={"email": "CASE@Example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 409


def test_register_short_password_returns_422(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_register_invalid_email_returns_422(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": VALID_PASSWORD},
    )

    assert response.status_code == 422


def test_register_cannot_choose_admin_role(client: TestClient, db: Session) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "sneaky@example.com", "password": VALID_PASSWORD, "role": "admin"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "viewer"