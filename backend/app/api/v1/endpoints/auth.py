from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    deny_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    GoogleExchangeRequest,
    GoogleLinkRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.services.legal import google_auth_service as google_auth
from app.services.legal.user_service import UserService

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    from app.core.exceptions import credentials_exception
    from app.core.security import verify_access_token

    try:
        user_id = verify_access_token(token)
    except ValueError:
        raise credentials_exception

    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)
):
    svc = UserService(db)
    existing = await svc.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    existing_username = await svc.get_by_username(payload.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = await svc.create(payload)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, payload: UserLogin, db: AsyncSession = Depends(get_db)
):
    svc = UserService(db)
    user = await svc.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    await svc.update_last_login(user.id)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/login/form", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_form(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    user = await svc.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
        )
    await svc.update_last_login(user.id)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_id = await verify_refresh_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    # Token rotation: deny the old token so it cannot be reused
    await deny_refresh_token(payload.refresh_token)
    access_token = create_access_token(str(user.id))
    refresh_token_new = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshTokenRequest):
    """Invalidate the refresh token so it cannot be used after logout."""
    try:
        await deny_refresh_token(payload.refresh_token)
    except Exception:
        pass  # always succeed; client should discard tokens regardless


# ─── Google Sign-In ──────────────────────────────────────────────────────────
# See app/services/legal/google_auth_service.py for the protocol details.
# Every path ends in _issue_tokens(), i.e. the same JWTs password login issues.


def _issue_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


def _frontend_redirect(
    path: str, query: dict[str, str] | None = None, fragment: dict[str, str] | None = None
) -> RedirectResponse:
    # Destination is always settings.FRONTEND_URL — never taken from the
    # request — so this cannot be abused as an open redirect.
    url = settings.FRONTEND_URL.rstrip("/") + path
    if query:
        url += "?" + urlencode(query)
    if fragment:
        url += "#" + urlencode(fragment)
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/providers")
async def auth_providers():
    """Which sign-in methods are configured — lets the frontend hide the
    Google button when no Google client is set up."""
    return {"password": True, "google": settings.google_oauth_enabled}


@router.get("/google")
@limiter.limit("20/minute")
async def google_login(request: Request):
    if not settings.google_oauth_enabled:
        return _frontend_redirect("/login", query={"oauth_error": "not_configured"})
    authorization_url, state_cookie = google_auth.build_authorization_request()
    response = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        google_auth.STATE_COOKIE,
        state_cookie,
        max_age=google_auth.STATE_TTL_SECONDS,
        path=google_auth.STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.GOOGLE_REDIRECT_URI.startswith("https://"),
        # Lax is sent on the top-level GET redirect back from Google.
        samesite="lax",
    )
    return response


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        if not settings.google_oauth_enabled:
            raise google_auth.GoogleAuthError("not_configured")
        if error:
            # access_denied = the user cancelled on Google's consent screen.
            raise google_auth.GoogleAuthError(
                "cancelled" if error == "access_denied" else "failed",
                f"Google returned error={error[:50]}",
            )
        nonce, code_verifier = google_auth.read_state_cookie(
            request.cookies.get(google_auth.STATE_COOKIE), state
        )
        if not code:
            raise google_auth.GoogleAuthError("failed", "callback without code")

        identity = await google_auth.exchange_code_for_identity(code, code_verifier, nonce)
        outcome, user = await google_auth.resolve_google_user(db, identity)

        if outcome == "link":
            response = _frontend_redirect(
                "/login",
                fragment={
                    "google_link": google_auth.issue_link_code(identity, str(user.id)),
                    "email": user.email,
                },
            )
        else:
            await UserService(db).update_last_login(user.id)
            await db.commit()  # the user must exist before the frontend redeems the code
            response = _frontend_redirect(
                "/auth/google/callback",
                fragment={"code": google_auth.issue_exchange_code(str(user.id))},
            )
    except google_auth.GoogleAuthError as e:
        logger.warning(f"Google sign-in failed: {e.code} ({e.log_detail})")
        response = _frontend_redirect("/login", query={"oauth_error": e.code})

    response.delete_cookie(google_auth.STATE_COOKIE, path=google_auth.STATE_COOKIE_PATH)
    return response


@router.post("/google/exchange", response_model=TokenResponse)
@limiter.limit("20/minute")
async def google_exchange(
    request: Request, payload: GoogleExchangeRequest, db: AsyncSession = Depends(get_db)
):
    user_id = google_auth.redeem_exchange_code(payload.code)
    user = await UserService(db).get_by_id(user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google sign-in expired. Please try again.",
        )
    return _issue_tokens(user)


@router.post("/google/link", response_model=TokenResponse)
@limiter.limit("10/minute")
async def google_link(
    request: Request, payload: GoogleLinkRequest, db: AsyncSession = Depends(get_db)
):
    """Links a Google account to an existing email/password account after
    the user proves they know that account's password. The Google identity
    and the target account both come from the server-side link request
    created by the callback — the browser supplies only the code and the
    password."""
    pending = google_auth.get_link_request(payload.link_code)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This Google sign-in has expired. Please continue with Google again.",
        )
    identity, user_id = pending
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if not user or not user.is_active:
        google_auth.consume_link_code(payload.link_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is not available.",
        )
    if not verify_password(payload.password, user.hashed_password):
        google_auth.record_failed_link_attempt(payload.link_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    if user.google_subject_id or await svc.get_by_google_subject_id(identity.subject_id):
        google_auth.consume_link_code(payload.link_code)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account or Google account is already linked.",
        )

    google_auth.consume_link_code(payload.link_code)
    await svc.link_google(user, identity.subject_id, identity.avatar_url)
    await svc.update_last_login(user.id)
    await db.commit()
    logger.info(f"Google account linked to user id={user.id}")
    return _issue_tokens(user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserService(db)
    await svc.change_password(
        current_user.id, payload.current_password, payload.new_password
    )
