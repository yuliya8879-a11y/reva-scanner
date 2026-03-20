from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_birth_date(self, telegram_id: int, birth_date: date) -> Optional[User]:
        """Update birth_date for the user identified by telegram_id."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.birth_date = birth_date
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Tuple[User, bool]:
        """Return (user, created). created=True if new user was inserted."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, True

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
