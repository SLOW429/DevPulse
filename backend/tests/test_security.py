import time

import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_verifies_and_is_not_plain_text() -> None:
    hashed = hash_password("S3cret!pass")

    assert hashed != "S3cret!pass"
    assert verify_password("S3cret!pass", hashed) is True


def test_wrong_password_is_rejected() -> None:
    hashed = hash_password("S3cret!pass")

    assert verify_password("wrong-password", hashed) is False


def test_same_password_produces_different_hashes() -> None:
    assert hash_password("same") != hash_password("same")


def test_access_token_roundtrip() -> None:
    token = create_access_token("42")

    assert decode_access_token(token) == "42"


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("42")

    assert decode_access_token(token + "x") is None


def test_token_signed_with_other_key_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "1", "exp": time.time() + 60},
        "a-different-key-that-is-long-enough-32b",
        algorithm="HS256",
    )

    assert decode_access_token(forged) is None


def test_expired_token_is_rejected() -> None:
    token = create_access_token("42", expires_minutes=-1)

    assert decode_access_token(token) is None