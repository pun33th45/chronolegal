import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)


def test_password_hash_and_verify():
    password = "SecurePass123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_lifecycle():
    subject = "user-id-123"
    token = create_access_token(subject)
    assert token

    recovered = verify_access_token(token)
    assert recovered == subject


async def test_refresh_token_lifecycle():
    subject = "user-id-456"
    token = create_refresh_token(subject)
    recovered = await verify_refresh_token(token)
    assert recovered == subject


def test_access_token_rejects_refresh():
    subject = "user-id-789"
    refresh = create_refresh_token(subject)
    with pytest.raises(ValueError, match="Not an access token"):
        verify_access_token(refresh)


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        verify_access_token("not.a.valid.token")


async def test_refresh_token_verification_fails_closed_on_cache_error(monkeypatch):
    """The denylist check must fail CLOSED: if Redis can't be reached, a
    revoked/rotated-out refresh token must not be silently accepted just
    because the revocation check itself couldn't run."""
    from app.core.redis import cache

    async def _broken_exists_strict(key: str) -> bool:
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(cache, "exists_strict", _broken_exists_strict)

    token = create_refresh_token("user-id-999")
    with pytest.raises(ValueError, match="verification unavailable"):
        await verify_refresh_token(token)
