import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DENYLIST_PREFIX = "rt_deny"
_DENYLIST_TTL = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86_400  # same lifetime as token


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | Any) -> str:
    """Create a refresh token with a unique jti claim for denylist support."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),  # unique token ID — used to invalidate on logout/rotation
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


def verify_access_token(token: str) -> str:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("Not an access token")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing subject")
    return sub


async def deny_refresh_token(token: str) -> None:
    """Add a refresh token's jti to the Redis denylist so it can never be reused."""
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti:
        return
    from app.core.redis import cache
    await cache.set(f"{_DENYLIST_PREFIX}:{jti}", 1, ttl=_DENYLIST_TTL)


async def verify_refresh_token(token: str) -> str:
    """Verify a refresh token; raise ValueError if it's on the denylist."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing subject")

    jti = payload.get("jti")
    if jti:
        from app.core.redis import cache
        if await cache.exists(f"{_DENYLIST_PREFIX}:{jti}"):
            raise ValueError("Refresh token has been revoked")

    return sub
