"""Unit tests for refresh token rotation and denylist."""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.security import (
    create_refresh_token,
    decode_token,
    deny_refresh_token,
    verify_refresh_token,
)


def test_refresh_token_has_jti():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert "jti" in payload
    assert payload["jti"]


def test_refresh_token_type():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_two_tokens_have_different_jtis():
    t1 = create_refresh_token("user-123")
    t2 = create_refresh_token("user-123")
    assert decode_token(t1)["jti"] != decode_token(t2)["jti"]


@pytest.mark.asyncio
async def test_verify_refresh_token_ok():
    token = create_refresh_token("user-abc")
    with patch("app.core.security.cache") as mock_cache:
        mock_cache.exists = AsyncMock(return_value=False)
        result = await verify_refresh_token(token)
    assert result == "user-abc"


@pytest.mark.asyncio
async def test_verify_refresh_token_denied():
    token = create_refresh_token("user-abc")
    with patch("app.core.security.cache") as mock_cache:
        mock_cache.exists = AsyncMock(return_value=True)
        with pytest.raises(ValueError, match="revoked"):
            await verify_refresh_token(token)


@pytest.mark.asyncio
async def test_deny_refresh_token_sets_cache():
    token = create_refresh_token("user-xyz")
    jti = decode_token(token)["jti"]
    with patch("app.core.security.cache") as mock_cache:
        mock_cache.set = AsyncMock()
        await deny_refresh_token(token)
        mock_cache.set.assert_called_once()
        call_key = mock_cache.set.call_args[0][0]
        assert jti in call_key
