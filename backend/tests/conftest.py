from collections.abc import Generator
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

settings.alerts_worker_enabled = False

TEST_DB_NAME = f"{settings.postgres_db}_test"

test_database_url = os.getenv("TEST_DATABASE_URL")
if test_database_url in {"sqlite://", "sqlite:///:memory:"}:
    test_engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    database_url = (
        settings.database_url.set(database=TEST_DB_NAME)
        if test_database_url is None
        else test_database_url
    )
    test_engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _database() -> Generator[None, None, None]:
    """Create all tables before each test and drop them after."""
    if test_engine.dialect.name == "sqlite":
        assert test_engine.url.database in (None, ":memory:")
    else:
        assert test_engine.url.database is not None
        assert test_engine.url.database.endswith(
            "_test"
        ), "Refusing to run on a non-test database"

    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()