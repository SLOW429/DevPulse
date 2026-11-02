from app.core.config import Settings


def test_database_url_escapes_special_characters() -> None:
    settings = Settings(postgres_password="p@ss#w:rd/1", secret_key="test-secret")

    rendered = settings.database_url.render_as_string(hide_password=False)

    assert settings.database_url.host == "127.0.0.1"
    assert settings.database_url.password == "p@ss#w:rd/1"
    assert "p%40ss%23w%3Ard%2F1" in rendered