"""Admin commands: /stats, /today, /broadcast, /api — only for ADMIN_TELEGRAM_ID."""

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
from app.models.payment import Payment
from app.models.scan import Scan
from app.models.user import User
from app.services.event_service import _EVENT_LABELS
from app.services.ai_client import get_status as api_get_status, set_active_key, add_or_replace_key

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

    # Расчёт дохода в рублях (3500 личный / 10000 бизнес)
    revenue_total = (paid_personal or 0) * 3500 + (paid_business or 0) * 10000
    revenue_week = 0  # приблизительно — по типам за неделю отдельно не делаем
    # Пытаемся посчитать доход за неделю по типам
    paid_personal_week = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "personal", Scan.is_paid.is_(True), Scan.created_at >= week_ago)
    )
    paid_business_week = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "business", Scan.is_paid.is_(True), Scan.created_at >= month_ago)
    )
    revenue_week = (paid_personal_week or 0) * 3500

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

        "💰 <b>Оплаты и доход</b>\n"
        f"  Всего оплат: <b>{paid_total}</b>\n"
        f"  Личных (3 500 ₽): <b>{paid_personal}</b>\n"
        f"  Бизнес (10 000 ₽): <b>{paid_business}</b>\n"
        f"  За 7 дней: <b>{paid_week}</b>\n"
        f"  За 30 дней: <b>{paid_month}</b>\n"
        f"  💵 Расчётный доход: <b>{revenue_total:,} ₽</b>\n\n"

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


# ── /grant ────────────────────────────────────────────────────────────────────

@router.message(Command("grant"))
async def cmd_grant(message: Message, session: AsyncSession) -> None:
    """/grant <telegram_id|@username> <personal|business> — выдать доступ пользователю."""
    if not _is_admin(message):
        return

    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select as sa_select

    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer(
            "Использование: <code>/grant 123456789 personal</code>\n"
            "или: <code>/grant @username business</code>",
            parse_mode="HTML",
        )
        return

    _, target, scan_type = parts
    scan_type = scan_type.lower()
    if scan_type not in ("personal", "business", "forever"):
        await message.answer("Тип должен быть <code>personal</code>, <code>business</code> или <code>forever</code>.", parse_mode="HTML")
        return

    # Ищем пользователя по ID или username
    if target.startswith("@"):
        uname = target[1:].lower()
        result = await session.execute(
            sa_select(User).where(User.username.ilike(uname))
        )
        user = result.scalar_one_or_none()
    else:
        try:
            tg_id = int(target)
        except ValueError:
            await message.answer("Неверный ID. Укажи числовой telegram_id или @username.")
            return
        result = await session.execute(sa_select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()

    if user is None:
        await message.answer(f"Пользователь {target} не найден в БД.")
        return

    # Выдаём доступ
    now = datetime.now(timezone.utc)
    if scan_type == "forever":
        user.subscription_until = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    else:
        user.subscription_until = now + timedelta(days=30)
    await session.commit()

    type_label = "личный разбор" if scan_type == "personal" else ("бизнес-разбор" if scan_type == "business" else "безлимитный доступ")
    display = f"@{user.username}" if user.username else f"id:{user.telegram_id}"

    await message.answer(
        f"✅ Доступ выдан: {display}\n"
        f"Тип: {type_label}\n"
        f"Действует до: {user.subscription_until.strftime('%d.%m.%Y %H:%M')} UTC"
    )

    # Уведомить пользователя
    try:
        await message.bot.send_message(
            user.telegram_id,
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"Юлия открыла вам доступ к <b>{type_label}у</b>.\n\n"
            f"Нажмите кнопку ниже чтобы начать — или отправьте /start:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=f"🔮 Начать {type_label}",
                    callback_data=f"buy:{scan_type}"
                )
            ]]),
        )
    except Exception:
        logger.warning("Не удалось отправить уведомление пользователю telegram_id=%s", user.telegram_id)
        await message.answer("⚠️ Доступ выдан, но уведомить пользователя не удалось (заблокировал бота?).")


# ── /revoke — забрать доступ ─────────────────────────────────────────────────

@router.message(Command("revoke"))
async def cmd_revoke(message: Message, session: AsyncSession) -> None:
    """/revoke <telegram_id|@username> — убрать подписку."""
    if not _is_admin(message):
        return
    from sqlalchemy import select as sa_select
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/revoke 123456789</code> или <code>/revoke @username</code>", parse_mode="HTML")
        return
    target = parts[1]
    if target.startswith("@"):
        result = await session.execute(sa_select(User).where(User.username.ilike(target[1:])))
    else:
        try:
            result = await session.execute(sa_select(User).where(User.telegram_id == int(target)))
        except ValueError:
            await message.answer("Неверный ID.")
            return
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer(f"Пользователь {target} не найден.")
        return
    user.subscription_until = None
    await session.commit()
    display = f"@{user.username}" if user.username else f"id:{user.telegram_id}"
    await message.answer(f"🚫 Доступ отозван: {display}")


# ── /whois — проверить пользователя ──────────────────────────────────────────

@router.message(Command("whois"))
async def cmd_whois(message: Message, session: AsyncSession) -> None:
    """/whois <telegram_id|@username> — статус пользователя."""
    if not _is_admin(message):
        return
    from datetime import datetime, timezone
    from sqlalchemy import select as sa_select
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/whois 123456789</code>", parse_mode="HTML")
        return
    target = parts[1]
    if target.startswith("@"):
        result = await session.execute(sa_select(User).where(User.username.ilike(target[1:])))
    else:
        try:
            result = await session.execute(sa_select(User).where(User.telegram_id == int(target)))
        except ValueError:
            await message.answer("Неверный ID.")
            return
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer(f"Пользователь {target} не найден.")
        return
    now = datetime.now(timezone.utc)
    has_sub = user.subscription_until and user.subscription_until > now
    sub_str = user.subscription_until.strftime('%d.%m.%Y') if user.subscription_until else "нет"
    display = f"@{user.username}" if user.username else f"id:{user.telegram_id}"
    await message.answer(
        f"👤 <b>{display}</b>  ({user.full_name or '—'})\n"
        f"🆔 telegram_id: <code>{user.telegram_id}</code>\n"
        f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}\n"
        f"🔐 Подписка: {'✅ активна до ' + sub_str if has_sub else '❌ нет'}\n\n"
        f"<code>/grant {user.telegram_id} personal</code> — дать доступ личный\n"
        f"<code>/grant {user.telegram_id} business</code> — дать бизнес\n"
        f"<code>/revoke {user.telegram_id}</code> — отозвать",
        parse_mode="HTML",
    )


# ── Inline-кнопка быстрой выдачи доступа (из уведомления о заявке) ───────────

@router.callback_query(lambda c: c.data and c.data.startswith("quick_grant:"))
async def handle_quick_grant(callback: CallbackQuery, session: AsyncSession) -> None:
    """Выдать доступ одной кнопкой прямо из уведомления о заявке."""
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select as sa_select
    _, tg_id_str, scan_type = callback.data.split(":")
    tg_id = int(tg_id_str)
    result = await session.execute(sa_select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("Пользователь не найден в БД", show_alert=True)
        return
    now = datetime.now(timezone.utc)
    user.subscription_until = now + timedelta(days=30)
    await session.commit()
    type_label = "личный разбор" if scan_type == "personal" else "бизнес-разбор"
    display = f"@{user.username}" if user.username else f"id:{user.telegram_id}"
    await callback.answer(f"✅ Доступ выдан: {display}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ <b>Выдан:</b> {display} → {type_label}", parse_mode="HTML")
    # Уведомить пользователя
    try:
        await callback.message.bot.send_message(
            tg_id,
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"Юлия открыла вам доступ к <b>{type_label}у</b>.\n\n"
            f"Нажмите кнопку ниже чтобы начать:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"▶️ Начать {type_label}", callback_data=f"buy:{scan_type}")
            ]]),
        )
    except Exception:
        pass


# ── Выдать мини-скан после оплаты 590 ₽ ──────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("mini_grant:"))
async def handle_mini_grant(callback: CallbackQuery, session: AsyncSession) -> None:
    """Выдать мини-скан одной кнопкой — запускает скан у пользователя."""
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    from sqlalchemy import select as sa_select
    parts = callback.data.split(":")
    tg_id = int(parts[1])
    scan_id = int(parts[2]) if len(parts) > 2 and parts[2] else 0

    result = await session.execute(sa_select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    display = f"@{user.username}" if user.username else f"id:{tg_id}"
    await callback.answer(f"✅ Мини-скан выдан: {display}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ Мини-скан запущен для {display}", parse_mode="HTML")

    # Уведомить пользователя — предложить ввести дату рождения
    try:
        if user.birth_date:
            await callback.message.bot.send_message(
                tg_id,
                "✅ <b>Оплата подтверждена!</b>\n\n"
                "Скан запускается. С чем ты сейчас?\n\n"
                "<i>Опиши свою ситуацию или запрос — одним-двумя предложениями.</i>",
                parse_mode="HTML",
            )
            # Помечаем скан как оплаченный если есть scan_id
            if scan_id:
                scan = await session.get(Scan, scan_id)
                if scan:
                    scan.is_paid = True
                    await session.commit()
        else:
            await callback.message.bot.send_message(
                tg_id,
                "✅ <b>Оплата подтверждена!</b>\n\n"
                "Для запуска скана нужна дата рождения.\n\n"
                "Напиши свою дату рождения в формате <b>ДД.ММ.ГГГГ</b>:",
                parse_mode="HTML",
            )
    except Exception:
        pass


# ── Быстрый скан для админа (кнопки "Разбор" / "Бизнес разбор") ──────────────

class AdminQuickScanStates(StatesGroup):
    waiting_request = State()


@router.callback_query(lambda c: c.data in ("admin_scan:personal", "admin_scan:business"))
async def handle_admin_quick_scan_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    scan_type = callback.data.split(":")[1]
    label = "личного" if scan_type == "personal" else "бизнес"
    await state.set_state(AdminQuickScanStates.waiting_request)
    await state.update_data(admin_scan_type=scan_type)
    await callback.answer()
    await callback.message.answer(
        f"✍️ <b>{label.capitalize()} разбор</b>\n\nНапиши запрос — что хочешь понять или получить от скана:",
        parse_mode="HTML",
    )


@router.message(AdminQuickScanStates.waiting_request)
async def handle_admin_quick_scan_request(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    from datetime import datetime as _dt, timezone as _tz
    from app.services.scan_service import ScanService
    from app.services.user_service import UserService
    from app.bot.handlers.full_scan import generate_and_deliver_report

    data = await state.get_data()
    scan_type = data.get("admin_scan_type", "personal")
    await state.clear()

    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    scan_service = ScanService(session)
    scan = await scan_service.create_full_scan(user.id, scan_type)

    # Заполняем ответы: birth_date из профиля + запрос
    answers: dict = {}
    if user.birth_date:
        answers["birth_date"] = user.birth_date.isoformat()
    answers["name"] = message.from_user.first_name or "Юлия"
    answers["scan_request"] = message.text or ""
    scan.answers = answers
    scan.is_paid = True
    await session.commit()

    await message.answer("🔮 Генерирую разбор...")
    await generate_and_deliver_report(
        message.bot, message.chat.id, scan.id, scan_type, session
    )


# ── Кнопка "Отчеты за день" ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin_report_today")
async def handle_admin_report_today(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()

    from datetime import datetime, timezone, timedelta
    from app.models.scan import ScanStatus

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    new_today = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= today)
    )
    total_users = await session.scalar(select(func.count()).select_from(User))

    mini_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "mini", Scan.created_at >= today)
    )
    personal_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "personal", Scan.created_at >= today,
               Scan.status == ScanStatus.completed.value)
    )
    business_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.scan_type == "business", Scan.created_at >= today,
               Scan.status == ScanStatus.completed.value)
    )
    paid_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= today)
    )
    paid_week = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= week_ago)
    )

    # Последние 5 сканов за день
    recent_scans = (await session.execute(
        select(Scan, User)
        .join(User, Scan.user_id == User.id)
        .where(Scan.created_at >= today)
        .order_by(Scan.created_at.desc())
        .limit(5)
    )).all()

    lines = [
        f"📊 <b>Отчёт за сегодня</b> — {now.strftime('%d.%m.%Y')}\n",
        f"👥 Новых пользователей: <b>{new_today}</b> (всего: {total_users})",
        f"👁 Мини-сканов: <b>{mini_today}</b>",
        f"🔮 Личных разборов: <b>{personal_today}</b>",
        f"💼 Бизнес-разборов: <b>{business_today}</b>",
        f"💰 Оплат сегодня: <b>{paid_today}</b>",
        f"💰 Оплат за 7 дней: <b>{paid_week}</b>",
    ]

    if recent_scans:
        lines.append("\n<b>Последние сканы:</b>")
        for sc, usr in recent_scans:
            uname = f"@{usr.username}" if usr.username else f"id:{usr.telegram_id}"
            t = sc.created_at.strftime("%H:%M")
            lines.append(f"  {t} — {uname} — {sc.scan_type} — {sc.status}")

    from app.bot.handlers.start import _admin_keyboard
    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_admin_keyboard(),
    )


# ── Полный отчёт + кто не оплатил ────────────────────────────────────────────

async def _send_full_report(target: Message | CallbackQuery, session: AsyncSession) -> None:
    from datetime import datetime, timezone, timedelta
    from app.models.scan import ScanStatus

    send = target.answer if isinstance(target, Message) else target.message.answer
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    # ── Всё время ──────────────────────────────────────────────
    total_users = await session.scalar(select(func.count()).select_from(User))
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
    paid_total = await session.scalar(
        select(func.count()).select_from(Scan).where(Scan.is_paid.is_(True))
    )

    # ── Вчера ──────────────────────────────────────────────────
    new_yesterday = await session.scalar(
        select(func.count()).select_from(User)
        .where(User.created_at >= yesterday, User.created_at < today)
    )
    scans_yesterday = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.created_at >= yesterday, Scan.created_at < today,
               Scan.status == ScanStatus.completed.value)
    )
    paid_yesterday = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= yesterday, Scan.created_at < today)
    )

    # ── Сегодня ────────────────────────────────────────────────
    new_today = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= today)
    )
    scans_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.created_at >= today, Scan.status == ScanStatus.completed.value)
    )
    paid_today = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.is_paid.is_(True), Scan.created_at >= today)
    )

    # ── Не оплатили (pending payments) ────────────────────────
    pending_rows = (await session.execute(
        select(Payment, User)
        .join(User, Payment.user_id == User.id)
        .where(Payment.status == "pending")
        .order_by(Payment.created_at.desc())
    )).all()

    # ── Сообщение 1: общая статистика ─────────────────────────
    await send(
        f"📈 <b>ПОЛНЫЙ ОТЧЁТ — Глаз Бога</b>\n"
        f"<i>{now.strftime('%d.%m.%Y %H:%M')} UTC</i>\n\n"

        f"👥 <b>Пользователей всего:</b> {total_users}\n\n"

        f"🔍 <b>Сканы за всё время:</b>\n"
        f"  👁 Мини: <b>{mini_done}</b> завершено\n"
        f"  🔮 Личных: <b>{personal_done}</b> завершено\n"
        f"  💼 Бизнес: <b>{business_done}</b> завершено\n"
        f"  💰 Оплачено всего: <b>{paid_total}</b>\n\n"

        f"📅 <b>Вчера ({yesterday.strftime('%d.%m')}):</b>\n"
        f"  Новых пользователей: <b>{new_yesterday}</b>\n"
        f"  Сканов завершено: <b>{scans_yesterday}</b>\n"
        f"  Оплат: <b>{paid_yesterday}</b>\n\n"

        f"📅 <b>Сегодня ({today.strftime('%d.%m')}):</b>\n"
        f"  Новых пользователей: <b>{new_today}</b>\n"
        f"  Сканов завершено: <b>{scans_today}</b>\n"
        f"  Оплат: <b>{paid_today}</b>",
        parse_mode="HTML",
    )

    # ── Сообщение 2: кто не оплатил ───────────────────────────
    if not pending_rows:
        await send("✅ <b>Незакрытых заявок нет.</b>", parse_mode="HTML")
        return

    lines = [f"⚠️ <b>Хотели купить, но не оплатили — {len(pending_rows)} чел.:</b>\n"]
    for pay, usr in pending_rows:
        uname = f"@{usr.username}" if usr.username else f"id:{usr.telegram_id}"
        name = usr.full_name or uname
        product = "Личный" if pay.product_type == "personal" else "Бизнес"
        date_str = pay.created_at.strftime("%d.%m %H:%M")
        lines.append(
            f"👤 <b>{name}</b> ({uname})\n"
            f"   {product} | {date_str}\n"
            f"   /grant {usr.telegram_id} {pay.product_type}"
        )

    full_text = "\n".join(lines)
    chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
    for chunk in chunks:
        await send(chunk, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin_report_full")
async def handle_admin_report_full(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await _send_full_report(callback, session)


@router.message(Command("report"))
async def cmd_report(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message):
        return
    await _send_full_report(message, session)


# ── Управление пользователями ────────────────────────────────────────────────

def _is_admin_cb(callback: CallbackQuery) -> bool:
    return bool(settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id)


@router.callback_query(lambda c: c.data == "admin_users")
async def handle_admin_users(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not _is_admin_cb(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    users = (await session.execute(
        select(User).order_by(User.created_at.desc()).limit(20)
    )).scalars().all()

    lines = ["👥 <b>Пользователи (последние 20)</b>\n"]
    buttons = []
    for u in users:
        uname = f"@{u.username}" if u.username else f"id:{u.telegram_id}"
        has_sub = u.subscription_until and u.subscription_until > now
        sub_icon = "✅" if has_sub else "—"
        lines.append(f"{sub_icon} {uname} — {u.created_at.strftime('%d.%m.%Y')}")
        buttons.append([
            InlineKeyboardButton(text=f"👤 {uname}", callback_data=f"user_card:{u.id}"),
        ])

    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("user_card:"))
async def handle_user_card(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin_cb(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.message.answer("Пользователь не найден.")
        return

    uname = f"@{user.username}" if user.username else f"tg:{user.telegram_id}"
    has_sub = user.subscription_until and user.subscription_until > now
    sub_status = (
        f"✅ до {user.subscription_until.strftime('%d.%m.%Y')}"
        if has_sub else "❌ нет подписки"
    )

    scans_count = await session.scalar(
        select(func.count()).select_from(Scan).where(Scan.user_id == user_id)
    )
    paid_count = await session.scalar(
        select(func.count()).select_from(Scan)
        .where(Scan.user_id == user_id, Scan.is_paid.is_(True))
    )

    text = (
        f"👤 <b>{user.full_name or uname}</b>\n"
        f"Username: {uname}\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"📋 Подписка: {sub_status}\n"
        f"🔍 Сканов всего: {scans_count} (оплачено: {paid_count})"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Дать 1 мес", callback_data=f"user_grant:{user_id}:1"),
                InlineKeyboardButton(text="✅ Дать 3 мес", callback_data=f"user_grant:{user_id}:3"),
                InlineKeyboardButton(text="✅ Дать 6 мес", callback_data=f"user_grant:{user_id}:6"),
            ],
            [InlineKeyboardButton(text="❌ Отозвать доступ", callback_data=f"user_revoke:{user_id}")],
            [InlineKeyboardButton(text="📋 Запросы пользователя", callback_data=f"user_scans:{user_id}")],
            [InlineKeyboardButton(text="← Назад", callback_data="admin_users")],
        ]),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("user_grant:"))
async def handle_user_grant(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin_cb(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return

    from datetime import datetime, timezone, timedelta
    parts = callback.data.split(":")
    user_id = int(parts[1])
    months = int(parts[2])

    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    base = user.subscription_until if (user.subscription_until and user.subscription_until > now) else now
    user.subscription_until = base + timedelta(days=30 * months)
    await session.commit()

    uname = f"@{user.username}" if user.username else str(user.telegram_id)
    await callback.answer(f"✅ {uname} — доступ +{months} мес.", show_alert=True)

    # Уведомить пользователя
    try:
        await callback.bot.send_message(
            user.telegram_id,
            f"✅ <b>Доступ активирован!</b>\n\n"
            f"Ваша подписка действует до: <b>{user.subscription_until.strftime('%d.%m.%Y')}</b>\n\n"
            f"Вы можете начать разбор прямо сейчас.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.message.answer(
        f"✅ <b>{uname}</b> — подписка выдана на {months} мес.\n"
        f"Действует до: {user.subscription_until.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("user_revoke:"))
async def handle_user_revoke(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin_cb(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return

    from datetime import datetime, timezone, timedelta
    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    user.subscription_until = datetime.now(timezone.utc) - timedelta(days=1)
    await session.commit()

    uname = f"@{user.username}" if user.username else str(user.telegram_id)
    await callback.answer(f"❌ Доступ {uname} отозван", show_alert=True)
    await callback.message.answer(f"❌ Подписка <b>{uname}</b> отозвана.", parse_mode="HTML")


@router.callback_query(lambda c: c.data and c.data.startswith("user_scans:"))
async def handle_user_scans(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin_cb(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()

    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.message.answer("Пользователь не найден.")
        return

    scans = (await session.execute(
        select(Scan)
        .where(Scan.user_id == user_id)
        .order_by(Scan.created_at.desc())
        .limit(5)
    )).scalars().all()

    uname = f"@{user.username}" if user.username else str(user.telegram_id)
    _type_labels = {"mini": "Мини", "personal": "Личный", "business": "Бизнес"}

    if not scans:
        await callback.message.answer(f"У {uname} пока нет сканов.")
        return

    for s in scans:
        label = _type_labels.get(s.scan_type, s.scan_type)
        date = s.created_at.strftime("%d.%m.%Y %H:%M") if s.created_at else "—"
        paid = "💰 оплачен" if s.is_paid else "бесплатно"
        status = s.status

        # Показываем запрос пользователя
        user_request = ""
        if s.answers:
            try:
                import json as _json
                answers = _json.loads(s.answers) if isinstance(s.answers, str) else s.answers
                if isinstance(answers, dict):
                    req = answers.get("request") or answers.get("situation") or answers.get("question") or ""
                    if req:
                        user_request = f"\n\n<b>Запрос:</b> {str(req)[:300]}"
            except Exception:
                pass

        text = (
            f"📋 <b>{label}</b> — {date}\n"
            f"Статус: {status} | {paid}{user_request}"
        )
        await callback.message.answer(text, parse_mode="HTML")


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


# ── /api — управление API ключами ────────────────────────────────────────────

class ApiKeyStates(StatesGroup):
    waiting_key_1 = State()
    waiting_key_2 = State()
    waiting_key_3 = State()


def _api_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Ключ 1", callback_data="api_switch:0"),
            InlineKeyboardButton(text="🔵 Ключ 2", callback_data="api_switch:1"),
            InlineKeyboardButton(text="🟣 Ключ 3", callback_data="api_switch:2"),
        ],
        [
            InlineKeyboardButton(text="✏️ Ключ 1", callback_data="api_set:1"),
            InlineKeyboardButton(text="✏️ Ключ 2", callback_data="api_set:2"),
            InlineKeyboardButton(text="✏️ Ключ 3", callback_data="api_set:3"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="api_status")],
    ])


def _api_status_text() -> str:
    s = api_get_status()
    active = s["active_key"]
    k1 = f"{'✅' if s['key_1_set'] else '❌'} Ключ 1: {s['key_1_mask']}"
    k2 = f"{'✅' if s['key_2_set'] else '❌'} Ключ 2: {s['key_2_mask']}"
    k3 = f"{'✅' if s['key_3_set'] else '❌'} Ключ 3: {s['key_3_mask']}"
    indicator = (
        f"{'🟢' if active == 1 else '⚪'} Ключ 1    "
        f"{'🟢' if active == 2 else '⚪'} Ключ 2    "
        f"{'🟢' if active == 3 else '⚪'} Ключ 3"
    )

    log_lines = "\n".join(s["switch_log"]) if s["switch_log"] else "Переключений не было"

    return (
        f"🔑 <b>API ключи Anthropic</b>\n\n"
        f"{k1}\n"
        f"{k2}\n"
        f"{k3}\n\n"
        f"<b>Активный:</b> {indicator}\n\n"
        f"📊 Вызовов: {s['call_count']} | Ошибок: {s['error_count']}\n\n"
        f"<b>История переключений:</b>\n{log_lines}\n\n"
        f"💡 <i>Пополнить баланс: console.anthropic.com → Billing</i>"
    )


@router.message(Command("api"))
async def cmd_api_status(message: Message) -> None:
    if not _is_admin(message):
        return
    await message.answer(_api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard())


@router.callback_query(lambda c: c.data == "api_status")
async def handle_api_status(callback: CallbackQuery) -> None:
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        _api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("api_switch:"))
async def handle_api_switch(callback: CallbackQuery) -> None:
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    success = set_active_key(index)
    if success:
        await callback.answer(f"✅ Переключено на Ключ {index + 1}", show_alert=True)
    else:
        await callback.answer("❌ Ключ не настроен", show_alert=True)
    await callback.message.edit_text(
        _api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard()
    )


# ── Вставить новый API ключ из бота ──────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("api_set:"))
async def handle_api_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Нажали ✏️ Вставить Ключ 1/2 — запросить ключ."""
    if not (settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    slot = int(callback.data.split(":")[1])
    await callback.answer()
    if slot == 1:
        await state.set_state(ApiKeyStates.waiting_key_1)
    elif slot == 2:
        await state.set_state(ApiKeyStates.waiting_key_2)
    else:
        await state.set_state(ApiKeyStates.waiting_key_3)
    await callback.message.answer(
        f"🔑 <b>Вставь новый Ключ {slot}</b>\n\n"
        f"Скопируй ключ из console.anthropic.com → API Keys\n"
        f"Начинается с <code>sk-ant-</code>\n\n"
        f"Просто отправь его сюда следующим сообщением:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="api_status")]
        ]),
    )


@router.message(ApiKeyStates.waiting_key_1)
async def handle_api_key_1_input(message: Message, state: FSMContext) -> None:
    """Получить новый Ключ 1 и сохранить."""
    await state.clear()
    key = (message.text or "").strip()
    if add_or_replace_key(1, key):
        await message.answer(
            "✅ <b>Ключ 1 обновлён!</b>\n\nБот уже использует новый ключ.",
            parse_mode="HTML",
            reply_markup=_api_keyboard(),
        )
        await message.answer(_api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard())
    else:
        await message.answer(
            "❌ Неверный формат. Ключ должен начинаться с <code>sk-ant-</code>",
            parse_mode="HTML",
        )


@router.message(ApiKeyStates.waiting_key_2)
async def handle_api_key_2_input(message: Message, state: FSMContext) -> None:
    """Получить новый Ключ 2 и сохранить."""
    await state.clear()
    key = (message.text or "").strip()
    if add_or_replace_key(2, key):
        await message.answer(
            "✅ <b>Ключ 2 обновлён!</b>\n\nБот уже использует новый ключ.",
            parse_mode="HTML",
        )
        await message.answer(_api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard())
    else:
        await message.answer(
            "❌ Неверный формат. Ключ должен начинаться с <code>sk-ant-</code>",
            parse_mode="HTML",
        )


@router.message(ApiKeyStates.waiting_key_3)
async def handle_api_key_3_input(message: Message, state: FSMContext) -> None:
    """Получить новый Ключ 3 и сохранить."""
    await state.clear()
    key = (message.text or "").strip()
    if add_or_replace_key(3, key):
        await message.answer(
            "✅ <b>Ключ 3 обновлён!</b>\n\nБот уже использует новый ключ.",
            parse_mode="HTML",
        )
        await message.answer(_api_status_text(), parse_mode="HTML", reply_markup=_api_keyboard())
    else:
        await message.answer(
            "❌ Неверный формат. Ключ должен начинаться с <code>sk-ant-</code>",
            parse_mode="HTML",
        )
