from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# DevPulse/backend/app/core/config.py -> parents[3] is the project root (DevPulse)
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    app_name: str = "DevPulse API"
    app_description: str = "Real-Time Infrastructure Monitoring & Automation Platform"
    app_version: str = "0.1.0"
    debug: bool = False

    postgres_user: str = "devpulse"
    postgres_password: str = Field(repr=False)
    postgres_db: str = "devpulse"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    secret_key: str = Field(repr=False)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    device_offline_after_seconds: int = Field(default=90, gt=0, le=86400)
    frontend_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    alerts_worker_enabled: bool = True
    alert_worker_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    alert_worker_batch_size: int = Field(default=50, ge=1, le=1000)
    alert_notification_max_attempts: int = Field(default=5, ge=1, le=20)
    alert_notification_retry_base_seconds: int = Field(default=5, ge=1, le=3600)
    alert_notification_sending_timeout_seconds: int = Field(
        default=60, ge=5, le=3600
    )
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    telegram_api_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("postgres_password")
    @classmethod
    def validate_database_password(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(value) < 12 or normalized in {
            "password",
            "postgres",
            "change_me",
            "replace_me",
        }:
            raise ValueError("POSTGRES_PASSWORD must be a non-placeholder value of at least 12 characters")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(value) < 32 or any(
            placeholder in normalized
            for placeholder in ("change_me", "replace_me", "generate_with", "your_secret")
        ):
            raise ValueError("SECRET_KEY must be a non-placeholder value of at least 32 characters")
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = Settings()