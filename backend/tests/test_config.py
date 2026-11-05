from app.core.config import Settings


def test_database_url_escapes_special_characters() -> None:
    settings = Settings(
        postgres_password="p@ss#w:rd/123",
        secret_key="test-secret-key-for-unit-tests-32",
    )

    rendered = settings.database_url.render_as_string(hide_password=False)

    assert settings.database_url.host == "127.0.0.1"
    assert settings.database_url.password == "p@ss#w:rd/123"
    assert "p%40ss%23w%3Ard%2F1" in rendered


def test_settings_reject_placeholder_secrets() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(postgres_password="replace_me_with_a_password", secret_key="x" * 31)

    with pytest.raises(ValidationError):
        Settings(postgres_password="secure-database-password", secret_key="change_me" + "x" * 32)