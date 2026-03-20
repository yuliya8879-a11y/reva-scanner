from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scan_service import ScanService
from app.services.user_service import UserService

router = Router(name="start")

_SCAN_TYPE_LABELS = {
    "personal": "Личное сканирование",
    "business": "Бизнес-сканирование",
}


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user_service = UserService(session)
    user, created = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    # Check for incomplete full scan BEFORE clearing FSM state
    scan_service = ScanService(session)
    incomplete_scan = await scan_service.get_incomplete_scan(user.id)

    if incomplete_scan is not None:
        scan_type_label = _SCAN_TYPE_LABELS.get(incomplete_scan.scan_type, incomplete_scan.scan_type)
        resume_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Продолжить",
                        callback_data=f"resume_scan:{incomplete_scan.id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Отменить и начать заново",
                        callback_data=f"cancel_scan:{incomplete_scan.id}",
                    )
                ],
            ]
        )
        await message.answer(
            f"У вас незавершённый скан ({scan_type_label}). Хотите продолжить?",
            reply_markup=resume_keyboard,
        )
        return

    # No incomplete scan — clear FSM state and show normal menu
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Личное сканирование 3500\u2b50",
                    callback_data="scan_type:personal",
                ),
                InlineKeyboardButton(
                    text="Бизнес-сканирование 7000\u2b50",
                    callback_data="scan_type:business",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\U0001f50d Бесплатный мини-скан",
                    callback_data="scan_type:mini",
                )
            ],
        ]
    )

    if created:
        text = (
            "\U0001f441 <b>Глаз Бога</b>\n\n"
            "Добро пожаловать! Я — AI-сканер бизнеса и личности.\n\n"
            "Начни с бесплатного мини-скана — узнай одну неудобную правду о своём бизнесе.\n\n"
            "Выберите тип сканирования:"
        )
    else:
        text = (
            "\U0001f441 <b>Глаз Бога</b>\n\n"
            "С возвращением! Начни с бесплатного мини-скана — узнай одну неудобную правду о своём бизнесе.\n\n"
            "Выберите тип сканирования:"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
