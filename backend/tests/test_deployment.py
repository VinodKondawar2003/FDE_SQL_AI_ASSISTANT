import pytest
from pydantic import ValidationError
from backend.app.config import Settings


def test_vercel_requires_durable_storage():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vercel=True)


def test_postgres_requires_direct_connection():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://example.test/db")


def test_vercel_origins_and_cookie_security():
    settings = Settings(
        _env_file=None,
        vercel=True,
        database_url="postgresql://example.test/db",
        database_url_unpooled="postgresql://example.test/db",
        vercel_url="preview-abc.vercel.app",
        vercel_project_production_url="querycraft.vercel.app",
    )
    assert settings.secure_cookies
    assert settings.allowed_origins == {"https://preview-abc.vercel.app", "https://querycraft.vercel.app"}
    assert "http://localhost:8000" not in settings.allowed_origins


def test_local_defaults_remain_usable():
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == {"http://localhost:8000"}
    assert not settings.secure_cookies
