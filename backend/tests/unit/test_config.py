"""Regression tests for Settings._validate_production_secrets.

Nothing in the existing test suite ever constructs Settings with
APP_ENV="production", so this validator has never actually been exercised
by CI. These tests pin its current, correct behavior: production blocks
known-insecure default secrets, while development remains unaffected.

Enforcing that real deployments actually deliver APP_ENV=production is a
docker-compose/CD concern (see docker-compose.prod.yml), not something
this validator itself can guarantee — these tests only prove the
validator does its job once APP_ENV is correctly set to "production".
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_env_rejects_insecure_default_secrets():
    with pytest.raises(ValidationError, match="Production startup blocked"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="your-super-secret-key-change-in-production-min-32-chars",
        )


def test_production_env_accepts_non_default_secrets():
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="test-only-non-default-secret-abc123",
        JWT_SECRET_KEY="test-only-non-default-jwt-secret-xyz789",
        POSTGRES_PASSWORD="test-only-non-default-postgres-pw",
        REDIS_PASSWORD="test-only-non-default-redis-pw",
    )

    assert settings.is_production is True


def test_development_env_allows_default_secrets():
    settings = Settings(SECRET_KEY="dev-only-test-key")

    assert settings.APP_ENV == "development"
    assert settings.is_production is False
