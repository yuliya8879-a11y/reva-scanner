"""Handler for 'request_session' callback — notifies Yulia directly via bot."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings

logger = logging.getLogger(__name__)

router = Router(name="session")


@router.callback_query(lambda c: c.data == "request_session")
async def handle_request_session(callback: CallbackQuery) -> None:
    """User tapped 'Хочу личную сессию' — notify Yulia, confirm to user."""
    user = callback.from_user
    name = user.full_name or user.first_name or "—"
    username = f"@{user.username}" if user.username else f"id:{user.id}"

    # Notify Yulia
    if settings.admin_telegram_id:
        try:
            await callback.message.bot.send_message(
                settings.admin_telegram_id,
                f"🔔 <b>Новая заявка на личную сессию!</b>\n\n"
                f"👤 {name}\n"
                f"📱 {username}\n"
                f"🔗 https://t.me/{user.username}" if user.username else
                f"🔔 <b>Новая заявка на личную сессию!</b>\n\n"
                f"👤 {name}\n"
                f"📱 {username}",
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("Failed to notify admin about session request from user_id=%s", user.id)

    await callback.answer()
    await callback.message.answer(
        "Юлия получила твою заявку и скоро напишет. 🤍\n\n"
        "Если хочешь написать прямо сейчас:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
            ]
        ),
    )
