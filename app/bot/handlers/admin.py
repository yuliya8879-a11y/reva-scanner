"""Admin commands: /stats, /today, /broadcast — only for ADMIN_TELEGRAM_ID."""

from __future__ import annotations

import logging
from collections import defaultdict

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.event import UserEvent
from app.models.scan import Scan
from app.models.user import User
from app.services.event_service import _EVENT_LABELS

logger = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin(message: Message) -> bool:
    return bool(settings.admin_telegram_id and message.from_user.id == settings.admin_telegram_id)


# ── /stats ────────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message):
        return

    from datetime import datetime, timedelta, timezone
    from app.models.scan import ScanStatus

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Пользователи ──────────────────────────────────────────────
    total_users = await session.scalar(select(func.count()).select_from(User))
    new_today = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= today)
    )
    new_week = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )

    # ── Сканы по типам ────────────────────────────────────────────
    mini_total = await session.scalar(
        select(func.count()).select_from(Scan).where(Scan.scan_type == "mini")
    )
    mini_done = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "mini", Scan.status == ScanStatus.completed.value)
    )
    personal_done = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "personal", Scan.status == ScanStatus.completed.value)
    )
    business_done = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "business", Scan.status == ScanStatus.completed.value)
    )

    # ── Оплаты ────────────────────────────────────────────────────
    paid_total = await session.scalar(
        select(func.count()).select_from(Scan).where(Scan.is_paid.is_(True))
    )
    paid_personal = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "personal", Scan.is_paid.is_(True))
    )
    paid_business = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "business", Scan.is_paid.is_(True))
    )
    paid_week = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= week_ago)
    )
    paid_month = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= month_ago)
    )

    # ── Воронка конверсии ─────────────────────────────────────────
    # Из мини → в платный
    mini_users = (await session.execute(
        select(Scan.user_id).where(Scan.scan_type == "mini").distinct()
    )).scalars().all()
    converted = 0
    if mini_users:
        converted = await session.scalar(
            select(func.count()).select_from(Scan)
            .where(Scan.is_paid.is_(True), Scan.user_id.in_(mini_users))
        ) or 0
    conv_rate = round(converted / len(mini_users) * 100, 1) if mini_users else 0

    # ── Незавершённые ─────────────────────────────────────────────
    pending = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.status.in_(["pending", "in_progress"]))
    )
    failed = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.status == ScanStatus.failed.value)
    )

    total_scans = (mini_total or 0) + (personal_done or 0) + (business_done or 0)

    await message.answer(
        "📊 <b>ОТЧЁТ — Глаз Бога</b>\n"
        f"<i>{now.strftime('%d.%m.%Y %H:%M')} UTC</i>\n\n"

        "👥 <b>Пользователи</b>\n"
        f"  Всего: <b>{total_users}</b>\n"
        f"  Новых сегодня: <b>{new_today}</b>\n"
        f"  Новых за неделю: <b>{new_week}</b>\n\n"

        "🔍 <b>Сканирования</b>\n"
        f"  👁 Мини-сканов запущено: <b>{mini_total}</b>\n"
        f"  👁 Мини-сканов завершено: <b>{mini_done}</b>\n"
        f"  🔮 Личных разборов: <b>{personal_done}</b>\n"
        f"  💼 Бизнес-разборов: <b>{business_done}</b>\n"
        f"  📦 Всего завершено: <b>{total_scans}</b>\n\n"

        "💰 <b>Оплаты</b>\n"
        f"  Всего оплат: <b>{paid_total}</b>\n"
        f"  Личных платных: <b>{paid_personal}</b>\n"
        f"  Бизнес платных: <b>{paid_business}</b>\n"
        f"  За 7 дней: <b>{paid_week}</b>\n"
        f"  За 30 дней: <b>{paid_month}</b>\n\n"

        "📈 <b>Конверсия</b>\n"
        f"  Мини → платный: <b>{converted}</b> из {len(mini_users)} ({conv_rate}%)\n\n"

        "⚙️ <b>Технические</b>\n"
        f"  В процессе: <b>{pending}</b>\n"
        f"  Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


# ── /today ────────────────────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession) -> None:
    """Полный отчёт по каждому пользователю за сегодня."""
    if not _is_admin(message):
        return

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Все события сегодня
    events_rows = (await session.execute(
        select(UserEvent)
        .where(UserEvent.created_at >= today)
        .order_by(UserEvent.telegram_id, UserEvent.created_at)
    )).scalars().all()

    if not events_rows:
        await message.answer("📭 Сегодня ещё никто не заходил.")
        return

    # Группируем по пользователю
    by_user: dict[int, list[UserEvent]] = defaultdict(list)
    for ev in events_rows:
        by_user[ev.telegram_id].append(ev)

    # Сканы сегодня
    scans_today = (await session.execute(
        select(Scan).where(Scan.created_at >= today)
    )).scalars().all()
    scans_by_user: dict[int, list[Scan]] = defaultdict(list)
    for sc in scans_today:
        # нужен telegram_id — получаем через user_id
        pass

    lines = [f"📋 <b>Отчёт за сегодня</b> — {len(by_user)} чел.\n"]

    for tg_id, evs in by_user.items():
        name = evs[0].full_name or evs[0].username or str(tg_id)
        uname = f"@{evs[0].username}" if evs[0].username else f"id:{tg_id}"
        last_event = _EVENT_LABELS.get(evs[-1].event, evs[-1].event)
        event_chain = " → ".join(
            _EVENT_LABELS.get(e.event, e.event).replace("✅ ", "").replace("👁 ", "")
            .replace("▶️ ", "").replace("📅 ", "").replace("✏️ ", "")
            .replace("🆕 ", "").replace("💳 ", "").replace("❌ ", "⚠️ ")
            for e in evs
        )
        lines.append(
            f"👤 <b>{name}</b> ({uname})\n"
            f"   Путь: {event_chain}\n"
            f"   Последнее: {last_event}\n"
        )

    # Разбиваем на части если текст длинный
    text = "\n".join(lines)
    if len(text) <= 4000:
        await message.answer(text, parse_mode="HTML")
    else:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await message.answer(chunk, parse_mode="HTML")


# ── Кнопка Помощь (от пользователя) ──────────────────────────────────────────

class HelpStates(StatesGroup):
    waiting_description = State()


@router.callback_query(lambda c: c.data == "help_request")
async def handle_help_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(HelpStates.waiting_description)
    await callback.message.answer(
        "🆘 <b>Опиши что произошло</b>\n\n"
        "Напиши коротко:\n"
        "— на каком шаге застряло\n"
        "— что написал бот\n"
        "— что ты нажимал(а)\n\n"
        "Отправлю твоё сообщение и разберу ошибку.",
        parse_mode="HTML",
    )


@router.message(HelpStates.waiting_description)
async def handle_help_description(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()

    from app.services.event_service import log_event
    await log_event(
        session, message.from_user, "help_request",
        detail=message.text[:500] if message.text else "",
        bot=message.bot,
    )

    # Уведомить админа с полным контекстом
    if settings.admin_telegram_id:
        name = message.from_user.full_name or message.from_user.username or str(message.from_user.id)
        uname = f"@{message.from_user.username}" if message.from_user.username else f"id:{message.from_user.id}"
        await message.bot.send_message(
            settings.admin_telegram_id,
            f"🆘 <b>Запрос помощи</b>\n\n"
            f"👤 {name} ({uname})\n\n"
            f"📝 <b>Описание:</b>\n{message.text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💬 Ответить пользователю",
                    url=f"tg://user?id={message.from_user.id}"
                )],
            ]),
        )

    await message.answer(
        "✅ Принято. Разберу ошибку и исправлю.\n\n"
        "Если нужна срочная помощь — напиши Юлии: @Reva_Yulya6",
    )


# ── /reviews ──────────────────────────────────────────────────────────────────

@router.message(Command("reviews"))
async def cmd_reviews(message: Message, session: AsyncSession) -> None:
    """Показать последние отзывы и сообщения пользователей из БД."""
    if not _is_admin(message):
        return

    from sqlalchemy import text as sa_text
    result = await session.execute(sa_text("""
        SELECT telegram_id, username, full_name, text, tag, created_at
        FROM feedback_messages
        ORDER BY created_at DESC
        LIMIT 30
    """))
    rows = result.fetchall()

    if not rows:
        await message.answer("📭 Отзывов пока нет.")
        return

    tag_emoji = {"review": "⭐", "help": "🆘", "message": "💬"}
    lines = [f"📋 <b>Отзывы и сообщения</b> (последние {len(rows)}):\n"]
    for tg_id, username, full_name, text, tag, created_at in rows:
        name = full_name or username or str(tg_id)
        uname = f"@{username}" if username else f"id:{tg_id}"
        emoji = tag_emoji.get(tag, "💬")
        date_str = created_at.strftime("%d.%m %H:%M") if created_at else ""
        lines.append(
            f"{emoji} <b>{name}</b> ({uname}) — {date_str}\n"
            f"   {text[:200]}\n"
        )

    full_text = "\n".join(lines)
    chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


# ── /broadcast ────────────────────────────────────────────────────────────────

class BroadcastStates(StatesGroup):
    waiting_text = State()
    confirm = State()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(BroadcastStates.waiting_text)
    await message.answer(
        "✍️ Напиши текст для рассылки всем пользователям бота.\n\n"
        "Поддерживается HTML-разметка (<b>жирный</b>, <i>курсив</i>).\n"
        "Для отмены — /cancel"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer("Отменено.")


@router.message(BroadcastStates.waiting_text)
async def broadcast_get_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text or message.caption or "")
    await state.set_state(BroadcastStates.confirm)
    await message.answer(
        f"📢 <b>Предпросмотр рассылки:</b>\n\n{message.text}\n\n"
        "Отправить всем? Напиши <b>ДА</b> для подтверждения или /cancel для отмены.",
        parse_mode="HTML",
    )


@router.message(BroadcastStates.confirm)
async def broadcast_confirm(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text and message.text.strip().upper() not in ("ДА", "YES", "ДА!"):
        await message.answer("Рассылка отменена. Напиши ДА для подтверждения или /cancel.")
        return

    data = await state.get_data()
    text = data.get("text", "")
    await state.clear()

    users = (await session.execute(select(User.telegram_id))).scalars().all()
    sent = 0
    failed = 0

    await message.answer(f"🚀 Начинаю рассылку {len(users)} пользователям...")

    for telegram_id in users:
        try:
            await message.bot.send_message(telegram_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )
