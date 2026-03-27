"""Feedback & help handler — catches free-text messages outside FSM.

Receives user reviews and help requests, forwards them to Yulia.
Must be registered LAST in the router chain so FSM handlers take priority.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.config import settings

logger = logging.getLogger(__name__)
router = Router(name="feedback")


async def _forward_to_admin(message: Message, tag: str) -> None:
    """Пересылает сообщение пользователя Юлии с тегом."""
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


# ─── Обработчик кнопки "Помощь / сообщить об ошибке" ─────────────────────────

@router.callback_query(lambda c: c.data == "help_request")
async def handle_help_request(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state("awaiting_help_text")
    await callback.message.answer(
        "Напиши что произошло — я передам Юлии.\n\n"
        "Опиши кратко: что ты делал(а), что пошло не так."
    )


# ─── Входящий текст в состоянии ожидания помощи ──────────────────────────────

@router.message(StateFilter("awaiting_help_text"))
async def handle_help_text(message: Message, state: FSMContext) -> None:
    await _forward_to_admin(message, "🆘 <b>Запрос помощи / ошибка:</b>")
    await state.clear()
    await message.answer(
        "Юлия получила твоё сообщение и разберётся. 🤍\n\n"
        "Обычно отвечаем в течение нескольких часов.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать Юлии напрямую", url="https://t.me/Reva_Yulya6")],
                [InlineKeyboardButton(text="← Главное меню", callback_data="back_to_menu")],
            ]
        ),
    )


# ─── Catch-all: любое сообщение вне FSM → принимаем как отзыв ────────────────

@router.message(StateFilter(default_state))
async def handle_free_text(message: Message) -> None:
    """Принимает любое сообщение вне FSM — скорее всего отзыв или вопрос."""
    if not message.text:
        return

    text_lower = message.text.lower()

    # Если похоже на отзыв — вперёд Юлии + тёплое подтверждение
    review_words = [
        "спасибо", "thank", "понравилось", "помогло", "ясность", "понял",
        "узнал", "класс", "круто", "огонь", "хорошо", "отзыв", "фидбек",
        "feedback", "почувствовал", "зашло", "точно", "попало", "разбор",
        "интересно", "помог", "помогла",
    ]

    if any(w in text_lower for w in review_words):
        await _forward_to_admin(message, "⭐ <b>Отзыв пользователя:</b>")
        await message.answer(
            "Спасибо! Юлия это получила. 🤍\n\n"
            "Если хочешь пройти следующее сканирование — нажми /start",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔮 Хочу личную сессию с Юлией", callback_data="request_session")],
                    [InlineKeyboardButton(text="← Главное меню", callback_data="back_to_menu")],
                ]
            ),
        )
    else:
        # Любое другое сообщение — переслать и дать меню
        await _forward_to_admin(message, "💬 <b>Сообщение от пользователя:</b>")
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
