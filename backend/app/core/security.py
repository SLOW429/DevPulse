from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plain-text password with Argon2."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if the password matches the Argon2 hash."""
    try:
        return _password_hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT whose `sub` claim identifies the user."""
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the token's subject, or None if it is invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return payload.get("sub")