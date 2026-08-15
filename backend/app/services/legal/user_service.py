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
