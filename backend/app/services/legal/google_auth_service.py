"""
Google Sign-In — OAuth 2.0 authorization-code flow with PKCE, plus OpenID
Connect ID-token verification. It ends in the same ChronoLegal JWTs that
password login issues; nothing downstream knows how a user signed in.

    GET  /auth/google           signed state cookie, 302 to Google
    GET  /auth/google/callback  verify state, exchange the code server-side,
                                verify the ID token, map to a ChronoLegal
                                user, 302 to FRONTEND_URL with a one-time code
    POST /auth/google/exchange  one-time code -> the normal TokenResponse
    POST /auth/google/link      one-time link code + account password ->
                                links Google to an existing account

Identity comes only from the ID token Google returns to this backend's
server-to-server token request; nothing the browser sends is trusted as
identity. No Google token or ChronoLegal JWT ever appears in a URL — the
frontend redirect carries only a random single-use code, in the URL fragment
(fragments are not sent to servers or in Referer headers).
"""

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services.legal.user_service import UserService

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# Google documents both spellings as valid `iss` values.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

STATE_COOKIE = "cl_google_oauth"
STATE_COOKIE_PATH = "/api/v1/auth/google"
STATE_TTL_SECONDS = 600
EXCHANGE_CODE_TTL_SECONDS = 60
LINK_CODE_TTL_SECONDS = 600
LINK_MAX_PASSWORD_ATTEMPTS = 5
JWKS_CACHE_SECONDS = 3600


class GoogleAuthError(Exception):
    """`code` is a fixed, user-safe identifier that is forwarded to the
    frontend; `log_detail` stays server-side and never contains tokens."""

    def __init__(self, code: str, log_detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.log_detail = log_detail


@dataclass(frozen=True)
class GoogleIdentity:
    subject_id: str
    email: str
    full_name: str | None
    avatar_url: str | None


# ─── State, nonce, PKCE ──────────────────────────────────────────────────────


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_authorization_request() -> tuple[str, str]:
    """Returns (Google authorization URL, signed state-cookie value).

    The cookie binds this flow to the browser that started it: the callback
    is accepted only if the `state` Google echoes back matches the one in
    this browser's cookie (CSRF / login-CSRF protection). It also carries
    the OIDC nonce (ties the ID token to this flow) and the PKCE verifier
    (ties the authorization code to this flow)."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())

    cookie_value = jwt.encode(
        {
            "type": "google_oauth_state",
            "state": state,
            "nonce": nonce,
            "cv": code_verifier,
            "exp": int(time.time()) + STATE_TTL_SECONDS,
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", cookie_value


def read_state_cookie(cookie_value: str | None, returned_state: str | None) -> tuple[str, str]:
    """Validates the callback's `state` against this browser's state cookie.
    Returns (nonce, code_verifier)."""
    if not cookie_value:
        raise GoogleAuthError("expired", "state cookie missing")
    try:
        payload = jwt.decode(
            cookie_value, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except ExpiredSignatureError:
        raise GoogleAuthError("expired", "state cookie expired")
    except JWTError:
        raise GoogleAuthError("invalid_state", "state cookie signature invalid")
    if payload.get("type") != "google_oauth_state":
        raise GoogleAuthError("invalid_state", "state cookie has wrong type")
    if not returned_state or not hmac.compare_digest(
        str(payload.get("state", "")), returned_state
    ):
        raise GoogleAuthError("invalid_state", "state mismatch")
    return str(payload["nonce"]), str(payload["cv"])


# ─── Code exchange + ID token verification ───────────────────────────────────

_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _google_jwks(force_refresh: bool = False) -> dict[str, Any]:
    fresh = time.time() - _jwks_cache["fetched_at"] < JWKS_CACHE_SECONDS
    if _jwks_cache["keys"] is not None and fresh and not force_refresh:
        return _jwks_cache["keys"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(GOOGLE_JWKS_URL)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise GoogleAuthError("unavailable", f"JWKS fetch failed: {type(e).__name__}")
    _jwks_cache.update(keys=resp.json(), fetched_at=time.time())
    return _jwks_cache["keys"]


def validate_id_token_claims(
    id_token: str, jwks: dict[str, Any], nonce: str, access_token: str | None
) -> dict[str, Any]:
    """Signature (RS256 against Google's published keys), audience, expiry
    and at_hash are checked by python-jose; issuer, nonce, subject and the
    verified-email requirement are checked here."""
    try:
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            access_token=access_token,
            # Google uses two issuer spellings; checked explicitly below.
            options={"verify_iss": False},
        )
    except JWTError as e:
        raise GoogleAuthError("failed", f"ID token rejected: {type(e).__name__}")

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleAuthError("failed", "ID token issuer is not Google")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleAuthError("failed", "ID token nonce mismatch")
    if not claims.get("sub") or not claims.get("email"):
        raise GoogleAuthError("failed", "ID token missing sub/email")
    if claims.get("email_verified") not in (True, "true"):
        raise GoogleAuthError("email_not_verified", "Google email not verified")
    return claims


def identity_from_claims(claims: dict[str, Any]) -> GoogleIdentity:
    picture = claims.get("picture")
    return GoogleIdentity(
        subject_id=str(claims["sub"]),
        email=str(claims["email"]).strip().lower(),
        full_name=(claims.get("name") or None),
        avatar_url=picture if isinstance(picture, str) and picture.startswith("https://") else None,
    )


async def exchange_code_for_identity(code: str, code_verifier: str, nonce: str) -> GoogleIdentity:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )
    except httpx.HTTPError as e:
        raise GoogleAuthError("unavailable", f"token endpoint unreachable: {type(e).__name__}")

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", "unknown")
        except ValueError:
            err = "non-JSON response"
        raise GoogleAuthError("failed", f"token exchange rejected ({resp.status_code}): {err}")

    tokens = resp.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise GoogleAuthError("failed", "token response has no id_token")

    jwks = await _google_jwks()
    try:
        claims = validate_id_token_claims(id_token, jwks, nonce, tokens.get("access_token"))
    except GoogleAuthError as first_error:
        # Google rotates signing keys; a token signed with a key newer than
        # the cached set fails once — retry with a fresh key set before
        # giving up. Any other failure fails the same way again.
        if first_error.code != "failed":
            raise
        jwks = await _google_jwks(force_refresh=True)
        claims = validate_id_token_claims(id_token, jwks, nonce, tokens.get("access_token"))
    return identity_from_claims(claims)


# ─── Account mapping ─────────────────────────────────────────────────────────


async def resolve_google_user(
    db: AsyncSession, identity: GoogleIdentity
) -> tuple[Literal["login", "link"], User]:
    """Maps a verified Google identity to a ChronoLegal user.

    - A user already linked to this Google `sub` signs in.
    - An email nobody has registered gets a new (Google) account.
    - An email that belongs to an existing email/password account is NOT
      linked automatically: ChronoLegal never verified the email of
      password sign-ups, so anyone could have registered a victim's address
      with their own password; auto-linking would hand that account (and
      the attacker's password access) to the victim's Google identity. The
      caller instead asks for that account's password once (`link`).
    - An existing account already linked to a different Google account is a
      conflict and is never overwritten."""
    svc = UserService(db)

    user = await svc.get_by_google_subject_id(identity.subject_id)
    if user is not None:
        if not user.is_active:
            raise GoogleAuthError("account_disabled", "linked user inactive")
        return "login", user

    result = await db.execute(
        select(User).where(func.lower(User.email) == identity.email)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        user = await svc.create_from_google(
            identity.subject_id, identity.email, identity.full_name, identity.avatar_url
        )
        logger.info(f"Google sign-in created user id={user.id}")
        return "login", user

    if existing.google_subject_id:
        raise GoogleAuthError("account_conflict", "email linked to another Google account")
    if not existing.is_active:
        raise GoogleAuthError("account_disabled", "matching user inactive")
    return "link", existing


# ─── One-time codes ──────────────────────────────────────────────────────────
#
# Held in process memory, like document_processor's _upload_status: the
# backend runs as a single uvicorn process (required by embedded Chroma), so
# a code issued by the callback is always redeemed by the same process. A
# restart only invalidates codes that live for seconds-to-minutes anyway.

_exchange_codes: dict[str, tuple[str, float]] = {}
_link_codes: dict[str, dict[str, Any]] = {}


def _purge_expired() -> None:
    now = time.time()
    for code in [c for c, (_, exp) in _exchange_codes.items() if exp < now]:
        _exchange_codes.pop(code, None)
    for code in [c for c, v in _link_codes.items() if v["expires_at"] < now]:
        _link_codes.pop(code, None)


def issue_exchange_code(user_id: str) -> str:
    _purge_expired()
    code = secrets.token_urlsafe(32)
    _exchange_codes[code] = (user_id, time.time() + EXCHANGE_CODE_TTL_SECONDS)
    return code


def redeem_exchange_code(code: str) -> str | None:
    """Single use: the code is removed whether or not it is still valid."""
    entry = _exchange_codes.pop(code, None)
    if entry is None or entry[1] < time.time():
        return None
    return entry[0]


def issue_link_code(identity: GoogleIdentity, user_id: str) -> str:
    _purge_expired()
    code = secrets.token_urlsafe(32)
    _link_codes[code] = {
        "identity": identity,
        "user_id": user_id,
        "expires_at": time.time() + LINK_CODE_TTL_SECONDS,
        "failed_attempts": 0,
    }
    return code


def get_link_request(code: str) -> tuple[GoogleIdentity, str] | None:
    entry = _link_codes.get(code)
    if entry is None or entry["expires_at"] < time.time():
        _link_codes.pop(code, None)
        return None
    return entry["identity"], entry["user_id"]


def record_failed_link_attempt(code: str) -> None:
    entry = _link_codes.get(code)
    if entry is None:
        return
    entry["failed_attempts"] += 1
    if entry["failed_attempts"] >= LINK_MAX_PASSWORD_ATTEMPTS:
        _link_codes.pop(code, None)


def consume_link_code(code: str) -> None:
    _link_codes.pop(code, None)
