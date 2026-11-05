from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

# Used to spend similar time when the email doesn't exist (mitigates user enumeration by timing).
_DUMMY_HASH = hash_password("dummy-password-for-timing-only")


class EmailAlreadyRegisteredError(Exception):
    """Raised when trying to register an email that already exists."""


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, data: UserCreate) -> User:
    """Create a new viewer user. Raises EmailAlreadyRegisteredError on duplicates."""
    if get_user_by_email(db, data.email) is not None:
        raise EmailAlreadyRegisteredError(data.email)

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.VIEWER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyRegisteredError(data.email) from None
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if credentials are valid and the account is active, else None."""
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user