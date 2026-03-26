"""Background tasks: review follow-up (24h), mini-scan follow-up (48h)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.scan import Scan
from app.models.user import User

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window(hours_min: int, hours_max: int):
    now = _now()
    return now - timedelta(hours=hours_max), now - timedelta(hours=hours_min)


# ── task 1: review request 24h after paid scan ───────────────────────────────

async def _send_review_requests(bot: Bot) -> None:
    lo, hi = _window(23, 25)
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Scan, User)
            .join(User, Scan.user_id == User.id)
            .where(
                Scan.is_paid.is_(True),
                Scan.status == "completed",
                Scan.completed_at >= lo,
                Scan.completed_at <= hi,
            )
        )
        pairs = rows.all()

    for scan, user in pairs:
        try:
            await bot.send_message(
                user.telegram_id,
                "👁 Прошли сутки после твоего разбора.\n\n"
                "Как тебе? Что уже применяешь?\n\n"
                "Если было ценно — буду рада твоему отзыву в канале. "
                "Это помогает другим решиться.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="⭐ Оставить отзыв в канале",
                            url="https://t.me/Reva_mentor",
                        )],
                        [InlineKeyboardButton(
                            text="🔮 Хочу ещё один разбор",
                            url="https://t.me/Eye888888_bot",
                        )],
                    ]
                ),
            )
            logger.info("Review request sent to user_id=%s scan_id=%s", user.id, scan.id)
        except Exception:
            logger.warning("Failed to send review request to telegram_id=%s", user.telegram_id)


# ── task 2: mini-scan follow-up 48h (no paid scan yet) ───────────────────────

async def _send_mini_followups(bot: Bot) -> None:
    lo, hi = _window(47, 49)
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Scan, User)
            .join(User, Scan.user_id == User.id)
            .where(
                Scan.scan_type == "mini",
                Scan.status == "completed",
                Scan.completed_at >= lo,
                Scan.completed_at <= hi,
            )
        )
        pairs = rows.all()

    for scan, user in pairs:
        # Skip if user already has a paid scan
        async with async_session_factory() as session:
            paid = await session.scalar(
                select(Scan.id)
                .where(Scan.user_id == user.id, Scan.is_paid.is_(True))
            )
        if paid:
            continue

        try:
            await bot.send_message(
                user.telegram_id,
                f"Привет, {user.full_name.split()[0] if user.full_name else 'друг'} 👋\n\n"
                "Два дня назад ты получил(а) бесплатный разбор.\n\n"
                "Как применяешь то, что там увидел(а)?\n\n"
                "Если хочешь копнуть глубже — "
                "полный разбор даёт картину в 6 блоках: "
                "состояние, деньги, поломка, глубина, команда, вектор.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔮 Хочу полный разбор",
                            url="https://t.me/Eye888888_bot",
                        )],
                        [InlineKeyboardButton(
                            text="💬 Написать Юлии",
                            url="https://t.me/Reva_Yulya6",
                        )],
                    ]
                ),
            )
            logger.info("Mini follow-up sent to user_id=%s scan_id=%s", user.id, scan.id)
        except Exception:
            logger.warning("Failed to send mini follow-up to telegram_id=%s", user.telegram_id)


# ── loop: runs every hour ─────────────────────────────────────────────────────

async def run_follow_up_loop(bot: Bot) -> None:
    """Background loop: every hour checks for users to follow up with."""
    logger.info("Follow-up background task started")
    while True:
        try:
            await _send_review_requests(bot)
            await _send_mini_followups(bot)
        except Exception:
            logger.exception("Error in follow-up loop")
        await asyncio.sleep(3600)  # run every hour
