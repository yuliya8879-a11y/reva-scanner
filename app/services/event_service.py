"""Логирование событий пользователей и уведомления админа."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.event import UserEvent

logger = logging.getLogger(__name__)

# Какие события отправляем админу в реальном времени
_NOTIFY_EVENTS = {
    "new_user",
    "mini_scan_start",
    "mini_scan_done",
    "personal_scan_paid",
    "business_scan_paid",
    "scan_error",
    "help_request",
}

_EVENT_LABELS = {
    "new_user":           "🆕 Новый пользователь",
    "start":              "▶️ /start",
    "mini_scan_start":    "👁 Начал мини-скан",
    "mini_consent_yes":   "✅ Дал согласие",
    "mini_date_entered":  "📅 Ввёл дату рождения",
    "mini_request_entered": "✏️ Описал запрос",
    "mini_scan_done":     "✅ Мини-скан завершён",
    "personal_scan_paid": "💳 Оплатил личный разбор",
    "business_scan_paid": "💳 Оплатил бизнес-разбор",
    "questionnaire_q":    "📝 Отвечает на анкету",
    "questionnaire_done": "📋 Анкета завершена",
    "full_scan_done":     "🏁 Полный скан завершён",
    "scan_error":         "❌ Ошибка скана",
    "restart":            "🔄 Перезапустил бота",
    "help_request":       "🆘 Запрос помощи",
    "session_request":    "🔮 Запросил личную сессию",
}


async def log_event(
    session: AsyncSession,
    tg_user: TgUser,
    event: str,
    detail: str | None = None,
    bot: Bot | None = None,
) -> None:
    """Сохраняет событие в БД и при необходимости уведомляет админа."""
    try:
        ev = UserEvent(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            event=event,
            detail=detail,
        )
        session.add(ev)
        await session.commit()
    except Exception:
        logger.exception("Failed to log event %s for user %s", event, tg_user.id)

    if bot and event in _NOTIFY_EVENTS and settings.admin_telegram_id:
        await _notify_admin(bot, tg_user, event, detail)


async def _notify_admin(
    bot: Bot,
    tg_user: TgUser,
    event: str,
    detail: str | None,
) -> None:
    label = _EVENT_LABELS.get(event, event)
    name = tg_user.full_name or tg_user.username or str(tg_user.id)
    username_str = f"@{tg_user.username}" if tg_user.username else f"id:{tg_user.id}"
    text = (
        f"{label}\n"
        f"👤 {name} ({username_str})\n"
    )
    if detail:
        text += f"📝 {detail}"
    try:
        await bot.send_message(settings.admin_telegram_id, text)
    except Exception:
        logger.exception("Failed to notify admin about event %s", event)
