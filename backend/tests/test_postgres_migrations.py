import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.services.alert_service import _due_deliveries

POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set POSTGRES_INTEGRATION_URL to a disposable empty PostgreSQL database",
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"
INITIAL_REVISION = "0149aaa00b25"


def _migration_config(connection: sa.Connection) -> Config:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["connection"] = connection
    return config


def test_fresh_migration_and_existing_data_upgrade() -> None:
    assert POSTGRES_URL is not None
    database_name = make_url(POSTGRES_URL).database
    if not database_name or not database_name.endswith("_integration_test"):
        pytest.fail(
            "POSTGRES_INTEGRATION_URL must target a dedicated *_integration_test database"
        )

    engine = sa.create_engine(POSTGRES_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            existing_tables = sa.inspect(connection).get_table_names()
            if existing_tables:
                pytest.fail(
                    "PostgreSQL integration database must be empty; "
                    f"found tables: {', '.join(existing_tables)}"
                )
            connection.commit()
            config = _migration_config(connection)

            command.upgrade(config, "head")
            inspector = sa.inspect(connection)
            assert {
                "users",
                "devices",
                "metrics",
                "alerts",
                "alert_rules",
                "alert_rule_states",
                "notification_deliveries",
            }.issubset(inspector.get_table_names())
            assert "uq_alerts_active_rule_device" in {
                index["name"] for index in inspector.get_indexes("alerts")
            }
            assert "fk_alerts_rule_id_alert_rules" in {
                foreign_key["name"]
                for foreign_key in inspector.get_foreign_keys("alerts")
            }
            connection.commit()

            command.downgrade(config, "base")
            command.upgrade(config, INITIAL_REVISION)

            email = f"migration-{uuid4().hex}@example.com"
            with connection.begin():
                user_id = connection.execute(
                    sa.text(
                        "INSERT INTO users (email, hashed_password, role, is_active) "
                        "VALUES (:email, :password, 'viewer', true) RETURNING id"
                    ),
                    {"email": email, "password": "test-hash"},
                ).scalar_one()
                device_id = connection.execute(
                    sa.text(
                        "INSERT INTO devices "
                        "(name, owner_id, api_key_prefix, api_key_hash, status) "
                        "VALUES ('pre-migration-host', :owner, :prefix, :hash, 'unknown') "
                        "RETURNING id"
                    ),
                    {
                        "owner": user_id,
                        "prefix": uuid4().hex[:16],
                        "hash": uuid4().hex * 2,
                    },
                ).scalar_one()

            connection.commit()
            command.upgrade(config, "head")
            preserved = connection.execute(
                sa.text(
                    "SELECT d.agent_id, d.name, u.email FROM devices d "
                    "JOIN users u ON u.id = d.owner_id WHERE d.id = :id"
                ),
                {"id": device_id},
            ).mappings().one()
            assert preserved["name"] == "pre-migration-host"
            assert preserved["email"] == email
            assert str(UUID(preserved["agent_id"])) == preserved["agent_id"]
            connection.commit()

            rule_id = connection.execute(
                sa.text(
                    "INSERT INTO alert_rules "
                    "(owner_id, device_id, name, metric, operator, threshold, severity) "
                    "VALUES (:owner, :device, 'test-rule', 'cpu', 'gt', 80, 'warning') "
                    "RETURNING id"
                ),
                {"owner": user_id, "device": device_id},
            ).scalar_one()
            alert_id = connection.execute(
                sa.text(
                    "INSERT INTO alerts "
                    "(device_id, rule_id, rule_name, metric_name, threshold, "
                    "observed_value, severity, status, message) "
                    "VALUES (:device, :rule, 'test-rule', 'cpu', 80, 90, "
                    "'warning', 'open', 'test incident') RETURNING id"
                ),
                {"device": device_id, "rule": rule_id},
            ).scalar_one()
            connection.commit()

            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        sa.text(
                            "INSERT INTO alerts "
                            "(device_id, rule_id, rule_name, metric_name, threshold, "
                            "observed_value, severity, status, message) "
                            "VALUES (:device, :rule, 'test-rule', 'cpu', 80, 91, "
                            "'warning', 'open', 'duplicate active incident')"
                        ),
                        {"device": device_id, "rule": rule_id},
                    )

            connection.execute(
                sa.text(
                    "INSERT INTO notification_deliveries "
                    "(alert_id, event_type, status) VALUES (:alert, 'fired', 'pending')"
                ),
                {"alert": alert_id},
            )
            connection.commit()

            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        sa.text(
                            "INSERT INTO notification_deliveries "
                            "(alert_id, event_type, status) "
                            "VALUES (:alert, 'fired', 'pending')"
                        ),
                        {"alert": alert_id},
                    )

            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        sa.text(
                            "INSERT INTO notification_deliveries "
                            "(alert_id, event_type, status) "
                            "VALUES (999999999, 'resolved', 'pending')"
                        )
                    )

            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            first_worker = sessions()
            second_worker = sessions()
            try:
                now = datetime.now(UTC)
                first_claims = _due_deliveries(first_worker, now)
                second_claims = _due_deliveries(second_worker, now)
                assert len(first_claims) == 1
                assert second_claims == []
            finally:
                first_worker.rollback()
                second_worker.rollback()
                first_worker.close()
                second_worker.close()
    finally:
        engine.dispose()
