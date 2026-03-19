from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user_service = UserService(session)
    user, created = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    if created:
        await message.answer(
            "👁 <b>Глаз Бога</b>\n\n"
            "Добро пожаловать! Я — AI-сканер бизнеса и личности.\n\n"
            "Выберите тип сканирования:",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "👁 <b>Глаз Бога</b>\n\n"
            "С возвращением! Выберите тип сканирования:",
            parse_mode="HTML",
        )
