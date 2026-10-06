"""Google Sign-In protocol checks — no database, no network.

ID tokens are signed with a locally generated RSA key standing in for
Google's, so signature/audience/issuer/nonce/at_hash validation runs for real.
"""

import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.core.config import Settings, settings
from app.services.legal import google_auth_service as g

CLIENT_ID = "test-client.apps.googleusercontent.com"


def _rsa_pair(kid: str):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = jwk.construct(pem, "RS256").public_key().to_dict()
    public.update(kid=kid, use="sig", alg="RS256")
    return pem, public


SIGNING_PEM, SIGNING_JWK = _rsa_pair("test-key")
OTHER_PEM, _ = _rsa_pair("other-key")
JWKS = {"keys": [SIGNING_JWK]}


@pytest.fixture(autouse=True)
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(
        settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"
    )
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")


def _id_token(nonce="n-1", pem=SIGNING_PEM, kid="test-key", access_token="at-1", **overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "Student@Example.com",
        "email_verified": True,
        "name": "Test Student",
        "picture": "https://lh3.googleusercontent.com/a/photo",
        "nonce": nonce,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(
        claims, pem, algorithm="RS256", headers={"kid": kid}, access_token=access_token
    )


# ─── Authorization request + state cookie ────────────────────────────────────


def test_authorization_url_and_state_cookie():
    url, cookie = g.build_authorization_request()
    parsed = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert parsed.netloc == "accounts.google.com"
    assert q["client_id"] == CLIENT_ID
    assert q["redirect_uri"] == settings.GOOGLE_REDIRECT_URI
    assert q["response_type"] == "code"
    assert q["scope"] == "openid email profile"
    assert q["code_challenge_method"] == "S256"

    nonce, verifier = g.read_state_cookie(cookie, q["state"])
    assert nonce == q["nonce"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert q["code_challenge"] == expected.rstrip(b"=").decode()
    assert "client_secret" not in url and "test-secret" not in url


def test_state_mismatch_missing_expired_and_tampered_cookie_are_rejected():
    url, cookie = g.build_authorization_request()
    with pytest.raises(g.GoogleAuthError) as e:
        g.read_state_cookie(cookie, "attacker-state")
    assert e.value.code == "invalid_state"
    with pytest.raises(g.GoogleAuthError) as e:
        g.read_state_cookie(None, "anything")
    assert e.value.code == "expired"

    expired = jwt.encode(
        {"type": "google_oauth_state", "state": "s", "nonce": "n", "cv": "v",
         "exp": int(time.time()) - 5},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(g.GoogleAuthError) as e:
        g.read_state_cookie(expired, "s")
    assert e.value.code == "expired"

    forged = jwt.encode(
        {"type": "google_oauth_state", "state": "s", "nonce": "n", "cv": "v",
         "exp": int(time.time()) + 60},
        "not-the-server-secret", algorithm="HS256",
    )
    with pytest.raises(g.GoogleAuthError) as e:
        g.read_state_cookie(forged, "s")
    assert e.value.code == "invalid_state"


def test_access_token_is_not_accepted_as_state_cookie():
    from app.core.security import create_access_token

    with pytest.raises(g.GoogleAuthError):
        g.read_state_cookie(create_access_token("some-user"), "s")


# ─── ID token validation ─────────────────────────────────────────────────────


def test_valid_id_token_yields_normalized_identity():
    claims = g.validate_id_token_claims(_id_token(), JWKS, "n-1", "at-1")
    identity = g.identity_from_claims(claims)
    assert identity.subject_id == "1234567890"
    assert identity.email == "student@example.com"
    assert identity.avatar_url.startswith("https://")


@pytest.mark.parametrize(
    "token_kwargs, nonce, access_token, expected_code",
    [
        ({"aud": "someone-else.apps.googleusercontent.com"}, "n-1", "at-1", "failed"),
        ({"iss": "https://evil.example.com"}, "n-1", "at-1", "failed"),
        ({"exp": int(time.time()) - 10}, "n-1", "at-1", "failed"),
        ({}, "different-nonce", "at-1", "failed"),
        ({"pem": OTHER_PEM}, "n-1", "at-1", "failed"),  # not signed by a published key
        ({}, "n-1", "a-different-access-token", "failed"),  # at_hash mismatch
        ({"email_verified": False}, "n-1", "at-1", "email_not_verified"),
        ({"sub": ""}, "n-1", "at-1", "failed"),
    ],
)
def test_invalid_id_tokens_are_rejected(token_kwargs, nonce, access_token, expected_code):
    token = _id_token(**token_kwargs)
    with pytest.raises(g.GoogleAuthError) as e:
        g.validate_id_token_claims(token, JWKS, nonce, access_token)
    assert e.value.code == expected_code


def test_non_https_picture_is_dropped():
    claims = g.validate_id_token_claims(
        _id_token(picture="http://insecure.example.com/p.png"), JWKS, "n-1", "at-1"
    )
    assert g.identity_from_claims(claims).avatar_url is None


# ─── One-time codes ──────────────────────────────────────────────────────────


def test_exchange_code_is_single_use_and_expires(monkeypatch):
    code = g.issue_exchange_code("user-1")
    assert g.redeem_exchange_code(code) == "user-1"
    assert g.redeem_exchange_code(code) is None

    code = g.issue_exchange_code("user-2")
    monkeypatch.setattr(g.time, "time", lambda: 10**12)
    assert g.redeem_exchange_code(code) is None


def test_link_code_is_discarded_after_too_many_wrong_passwords():
    identity = g.GoogleIdentity("sub-1", "a@example.com", None, None)
    code = g.issue_link_code(identity, "user-1")
    for _ in range(g.LINK_MAX_PASSWORD_ATTEMPTS - 1):
        g.record_failed_link_attempt(code)
        assert g.get_link_request(code) is not None
    g.record_failed_link_attempt(code)
    assert g.get_link_request(code) is None


# ─── Configuration ───────────────────────────────────────────────────────────


def test_production_requires_https_google_urls():
    base = dict(
        APP_ENV="production", SECRET_KEY="x" * 40, JWT_SECRET_KEY="y" * 40,
        POSTGRES_PASSWORD="strong-pw", REDIS_PASSWORD="strong-redis-pw",
        CORS_ORIGINS="https://chronolegal.vercel.app", GOOGLE_CLIENT_ID="id",
        GOOGLE_CLIENT_SECRET="secret",
    )
    with pytest.raises(ValueError, match="https"):
        Settings(**base, GOOGLE_REDIRECT_URI="http://x.example/cb", FRONTEND_URL="https://f.example")
    ok = Settings(
        **base,
        GOOGLE_REDIRECT_URI="https://api.example/api/v1/auth/google/callback",
        FRONTEND_URL="https://chronolegal.vercel.app",
    )
    assert ok.google_oauth_enabled


def test_google_disabled_without_client_credentials():
    assert Settings(SECRET_KEY="x" * 40, GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="").google_oauth_enabled is False


# ─── Endpoints that never touch the database ─────────────────────────────────


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)  # no lifespan: no migrations, no model loading


def test_providers_endpoint(client):
    assert client.get("/api/v1/auth/providers").json() == {"password": True, "google": True}


def test_google_start_redirects_to_google_with_secure_cookie(client):
    r = client.get("/api/v1/auth/google", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    cookie = r.headers["set-cookie"]
    assert g.STATE_COOKIE in cookie
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "Path=/api/v1/auth/google" in cookie


def test_google_start_when_not_configured_returns_to_login(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    r = client.get("/api/v1/auth/google", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?oauth_error=not_configured"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("error=access_denied&state=x", "cancelled"),
        ("error=server_error", "failed"),
        ("code=abc&state=x", "expired"),  # no state cookie in this browser
    ],
)
def test_callback_errors_redirect_to_login_with_safe_code(client, query, expected):
    r = client.get(f"/api/v1/auth/google/callback?{query}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"http://localhost:5173/login?oauth_error={expected}"


def test_callback_rejects_state_from_another_flow(client):
    client.get("/api/v1/auth/google", follow_redirects=False)  # sets this browser's cookie
    r = client.get(
        "/api/v1/auth/google/callback?code=abc&state=forged-state", follow_redirects=False
    )
    assert r.headers["location"] == "http://localhost:5173/login?oauth_error=invalid_state"


def test_redirect_target_cannot_be_chosen_by_the_request(client):
    r = client.get(
        "/api/v1/auth/google/callback?error=access_denied&redirect_uri=https://evil.example&next=https://evil.example",
        follow_redirects=False,
    )
    assert r.headers["location"].startswith("http://localhost:5173/")


def test_exchange_with_unknown_code_is_rejected(client):
    r = client.post("/api/v1/auth/google/exchange", json={"code": "x" * 43})
    assert r.status_code == 401
