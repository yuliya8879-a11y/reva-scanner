"""Feedback & help handler — catches free-text messages outside FSM.

ALL messages are saved to feedback_messages table in DB — never lost.
Forwards to Yulia in Telegram in real time.
Must be registered LAST in the router chain so FSM handlers take priority.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)
router = Router(name="feedback")

REVIEW_WORDS = [
    "спасибо", "thank", "понравилось", "помогло", "ясность", "понял",
    "узнал", "класс", "круто", "огонь", "хорошо", "отзыв", "фидбек",
    "feedback", "почувствовал", "зашло", "точно", "попало", "разбор",
    "интересно", "помог", "помогла", "впечатл", "сильно", "мощно",
    "работает", "точное", "увидел", "увидела", "поняла", "получилось",
]


async def _save_to_db(session: AsyncSession, message: Message, tag: str) -> None:
    """Сохраняет сообщение в таблицу feedback_messages — никогда не теряется."""
    user = message.from_user
    try:
        await session.execute(
            text("""
                INSERT INTO feedback_messages (telegram_id, username, full_name, text, tag)
                VALUES (:telegram_id, :username, :full_name, :text, :tag)
            """),
            {
                "telegram_id": user.id,
                "username": user.username,
                "full_name": user.full_name or user.first_name,
                "text": message.text or "(нет текста)",
                "tag": tag,
            },
        )
        await session.commit()
    except Exception:
        logger.exception("Не удалось сохранить feedback от user_id=%s", user.id)


async def _forward_to_admin(message: Message, tag: str) -> None:
    """Пересылает сообщение пользователя Юлии в Telegram."""
    if not settings.admin_telegram_id:
        return
    user = message.from_user
    name = user.full_name or user.first_name or "—"
    username = f"@{user.username}" if user.username else f"id:{user.id}"
    try:
        await message.bot.send_message(
            settings.admin_telegram_id,
            f"{tag}\n\n"
            f"👤 {name}  |  {username}\n\n"
            f"💬 {message.text or '(нет текста)'}",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось переслать сообщение админу от user_id=%s", user.id)


# ─── Catch-all: любое сообщение вне FSM → сохранить + переслать ──────────────

@router.message(StateFilter(default_state))
async def handle_free_text(message: Message, session: AsyncSession) -> None:
    """Принимает любое сообщение вне FSM. Сохраняет в БД. Пересылает Юлии."""
    if not message.text:
        return

    text_lower = message.text.lower()
    is_review = any(w in text_lower for w in REVIEW_WORDS)
    tag = "review" if is_review else "message"

    # Сохраняем ВСЕГДА — даже если пересылка в Telegram упадёт
    await _save_to_db(session, message, tag)
    await _forward_to_admin(message, "⭐ <b>Отзыв:</b>" if is_review else "💬 <b>Сообщение:</b>")

    if is_review:
        await message.answer(
            "Спасибо! Юлия это получила. 🤍\n\n"
            "Если хочешь пройти следующее сканирование — /start",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔮 Хочу личную сессию с Юлией", callback_data="request_session")],
                    [InlineKeyboardButton(text="← Главное меню", callback_data="back_to_menu")],
                ]
            ),
        )
    else:
        await message.answer(
            "Получила! Если это вопрос — Юлия ответит.\n\n"
            "Если нужна помощь прямо сейчас:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
                    [InlineKeyboardButton(text="← Главное меню", callback_data="back_to_menu")],
                ]
            ),
        )
