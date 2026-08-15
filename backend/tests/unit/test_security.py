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


def test_refresh_token_lifecycle():
    subject = "user-id-456"
    token = create_refresh_token(subject)
    recovered = verify_refresh_token(token)
    assert recovered == subject


def test_access_token_rejects_refresh():
    subject = "user-id-789"
    refresh = create_refresh_token(subject)
    with pytest.raises(ValueError, match="Not an access token"):
        verify_access_token(refresh)


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        verify_access_token("not.a.valid.token")
