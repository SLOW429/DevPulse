from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token
from app.models.user import User

EMAIL = "login@example.com"
PASSWORD = "a-long-password-1"


def _register(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 201


def test_login_returns_valid_token(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) is not None


def test_login_is_case_insensitive_on_email(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", data={"username": EMAIL.upper(), "password": PASSWORD}
    )

    assert response.status_code == 200


def test_wrong_password_returns_401(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/login", data={"username": EMAIL, "password": "wrong-password-123"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_unknown_email_returns_same_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login", data={"username": "nobody@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_login(client: TestClient, db: Session) -> None:
    _register(client)
    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()

    response = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})

    assert response.status_code == 401


def test_current_user_requires_authentication(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_returns_profile(client: TestClient) -> None:
    _register(client)
    login_response = client.post(
        "/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    assert response.json()["role"] == "viewer"
    assert "hashed_password" not in response.json()


def test_current_user_rejects_invalid_subject(client: TestClient) -> None:
    token = create_access_token("not-a-user-id")

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_inactive_account(
    client: TestClient, db: Session
) -> None:
    _register(client)
    login_response = client.post(
        "/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )
    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"