"""Background tasks: review follow-up (24h), mini-scan follow-up (48h), monitoring."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.scan import Scan
from app.models.user import User

logger = logging.getLogger(__name__)

# Хранит scan_id уже отправленных алертов — не дублируем
_alerted_scan_ids: set[int] = set()

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


# ── task 3: monitor failed scans (every 15 min) ──────────────────────────────

async def _check_failed_scans(bot: Bot) -> None:
    """Находит ошибки за последние 15 минут — отправляет алерт Юлии."""
    if not settings.admin_telegram_id:
        return
    since = _now() - timedelta(minutes=15)
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Scan, User)
            .join(User, Scan.user_id == User.id)
            .where(Scan.status == "failed", Scan.created_at >= since)
        )
        pairs = rows.all()

    new_failures = [(s, u) for s, u in pairs if s.id not in _alerted_scan_ids]
    if not new_failures:
        return

    for scan, user in new_failures:
        _alerted_scan_ids.add(scan.id)
        name = user.full_name or user.username or f"id:{user.telegram_id}"
        uname = f"@{user.username}" if user.username else f"tg://user?id={user.telegram_id}"
        scan_label = {"mini": "мини-скан", "personal": "личный разбор", "business": "бизнес-разбор"}.get(scan.scan_type, scan.scan_type)
        try:
            await bot.send_message(
                settings.admin_telegram_id,
                f"🔴 <b>Ошибка скана</b>\n\n"
                f"👤 {name}  |  {uname}\n"
                f"📦 {scan_label}  |  scan_id={scan.id}\n"
                f"🕐 {scan.created_at.strftime('%H:%M UTC')}\n\n"
                f"Пользователь получил кнопку «Помощь».",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💬 Написать пользователю",
                        url=f"tg://user?id={user.telegram_id}"
                    )],
                ]),
            )
        except Exception:
            logger.warning("Не удалось отправить алерт об ошибке scan_id=%s", scan.id)


# ── task 4: daily report at 9:00 MSK ─────────────────────────────────────────

async def _send_daily_report(bot: Bot) -> None:
    """Утренний отчёт каждый день в 9:00 МСК (06:00 UTC)."""
    if not settings.admin_telegram_id:
        return

    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    async with async_session_factory() as session:
        users_total = await session.scalar(select(func.count()).select_from(User))
        users_today = await session.scalar(select(func.count()).select_from(User).where(User.created_at >= today_start))
        users_week = await session.scalar(select(func.count()).select_from(User).where(User.created_at >= week_ago))

        scans_today = await session.scalar(select(func.count()).select_from(Scan).where(Scan.created_at >= today_start))
        paid_today = await session.scalar(select(func.count()).select_from(Scan).where(Scan.is_paid.is_(True), Scan.created_at >= today_start))
        failed_today = await session.scalar(select(func.count()).select_from(Scan).where(Scan.status == "failed", Scan.created_at >= today_start))

        paid_week = await session.scalar(select(func.count()).select_from(Scan).where(Scan.is_paid.is_(True), Scan.created_at >= week_ago))

    personal_revenue = 0
    business_revenue = 0
    async with async_session_factory() as session:
        p = await session.scalar(select(func.count()).select_from(Scan).where(Scan.scan_type == "personal", Scan.is_paid.is_(True), Scan.created_at >= week_ago))
        b = await session.scalar(select(func.count()).select_from(Scan).where(Scan.scan_type == "business", Scan.is_paid.is_(True), Scan.created_at >= week_ago))
        personal_revenue = (p or 0) * 3500
        business_revenue = (b or 0) * 10000

    status = "✅ Всё работает" if (failed_today or 0) == 0 else f"⚠️ Ошибок сегодня: {failed_today}"

    try:
        await bot.send_message(
            settings.admin_telegram_id,
            f"☀️ <b>Утренний отчёт — Глаз Бога</b>\n"
            f"{now.strftime('%d.%m.%Y')}\n\n"
            f"👥 <b>Пользователи</b>\n"
            f"  Всего: {users_total}  |  Сегодня: +{users_today}  |  Неделя: +{users_week}\n\n"
            f"📊 <b>Сегодня</b>\n"
            f"  Сканов запущено: {scans_today}\n"
            f"  Оплат: {paid_today}\n"
            f"  Ошибок: {failed_today or 0}\n\n"
            f"💰 <b>За 7 дней</b>\n"
            f"  Оплат: {paid_week}  |  Выручка: {personal_revenue + business_revenue:,} ₽\n\n"
            f"⚙️ <b>Статус:</b> {status}",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось отправить дневной отчёт")


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


# ── monitoring loop: every 15 min + daily report ─────────────────────────────

async def run_monitor_loop(bot: Bot) -> None:
    """Мониторинг: каждые 15 мин — проверка ошибок, в 06:00 UTC — дневной отчёт."""
    logger.info("Monitor background task started")
    last_daily_date: str = ""

    while True:
        try:
            await _check_failed_scans(bot)
        except Exception:
            logger.exception("Error in monitor: failed scans check")

        # Дневной отчёт в 06:00 UTC (= 09:00 МСК)
        try:
            now = _now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 6 and last_daily_date != today_str:
                last_daily_date = today_str
                await _send_daily_report(bot)
        except Exception:
            logger.exception("Error in monitor: daily report")

        await asyncio.sleep(900)  # каждые 15 минут
