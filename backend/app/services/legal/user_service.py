import re
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: UserCreate) -> User:
        user = User(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_google_subject_id(self, subject_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.google_subject_id == subject_id)
        )
        return result.scalar_one_or_none()

    async def create_from_google(
        self,
        subject_id: str,
        email: str,
        full_name: str | None,
        avatar_url: str | None,
    ) -> User:
        """Creates a Google-only user. hashed_password stays NOT NULL but is
        the hash of a random secret nobody ever sees, so password login is
        impossible for this account until a password exists — the existing
        email/password code paths need no special case."""
        user = User(
            email=email,
            username=await self._unique_username_from_email(email),
            full_name=full_name,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            avatar_url=avatar_url,
            google_subject_id=subject_id,
            is_verified=True,  # Google asserted email_verified
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def link_google(
        self, user: User, subject_id: str, avatar_url: str | None
    ) -> User:
        user.google_subject_id = subject_id
        user.is_verified = True
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def _unique_username_from_email(self, email: str) -> str:
        # Same character rules as UserBase.username (3-100 chars, [A-Za-z0-9_-]).
        base = re.sub(r"[^a-zA-Z0-9_-]", "", email.split("@", 1)[0])[:30]
        base = base if len(base) >= 3 else f"user{base}"
        candidate = base
        while await self.get_by_username(candidate):
            candidate = f"{base}-{secrets.token_hex(3)}"
        return candidate

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )

    async def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if not verify_password(current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(hashed_password=hash_password(new_password))
        )

    async def list_all(self, page: int = 1, page_size: int = 50) -> list[User]:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(User)
            .offset(offset)
            .limit(page_size)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
