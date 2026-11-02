from pathlib import Path

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
    postgres_password: str
    postgres_db: str = "devpulse"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

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