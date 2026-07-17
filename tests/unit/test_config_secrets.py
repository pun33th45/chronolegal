"""Unit tests for production secret validation."""
import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    from app.core.config import Settings
    defaults = dict(
        APP_ENV="production",
        SECRET_KEY="a-very-long-and-unique-secret-key-at-least-32chars",
        JWT_SECRET_KEY="another-unique-jwt-key-that-is-also-long-enough",
        POSTGRES_PASSWORD="super-secure-db-password-123",
        REDIS_PASSWORD="super-secure-redis-password-456",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://:p@localhost:6379/0",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_production_with_secure_secrets_ok():
    s = _make_settings()
    assert s.APP_ENV == "production"


def test_production_default_secret_key_raises():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _make_settings(SECRET_KEY="your-super-secret-key-change-in-production-min-32-chars")


def test_production_default_postgres_password_raises():
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        _make_settings(POSTGRES_PASSWORD="chronolegal_password")


def test_production_empty_secret_key_raises():
    with pytest.raises(ValidationError):
        _make_settings(SECRET_KEY="")


def test_development_allows_defaults():
    from app.core.config import Settings
    # Should NOT raise even with default-looking values in dev
    s = Settings(
        APP_ENV="development",
        SECRET_KEY="your-super-secret-key-change-in-production-min-32-chars",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://:p@localhost:6379/0",
    )
    assert s.APP_ENV == "development"
