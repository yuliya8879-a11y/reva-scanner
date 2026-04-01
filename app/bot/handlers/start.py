from __future__ import annotations

from datetime import datetime as _dt, timezone as _tz, timedelta as _td

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.event_service import log_event
from app.services.scan_service import ScanService
from app.services.user_service import UserService

router = Router(name="start")

_SCAN_TYPE_LABELS = {
    "personal": "Личное сканирование",
    "business": "Бизнес-сканирование",
}


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔮 Разбор", callback_data="admin_scan:personal"),
                InlineKeyboardButton(text="💼 Бизнес разбор", callback_data="admin_scan:business"),
            ],
            [InlineKeyboardButton(text="📊 Отчёт за сегодня", callback_data="admin_report_today")],
            [InlineKeyboardButton(text="📈 Полный отчёт + не оплатили", callback_data="admin_report_full")],
            [InlineKeyboardButton(text="👁 Бесплатный мини-скан", callback_data="scan_type:mini")],
            [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔑 API ключи — статус/переключение", callback_data="api_status")],
        ]
    )


def _main_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    if has_subscription:
        scan_buttons = [
            InlineKeyboardButton(text="🔮 Новое личное сканирование", callback_data="buy:personal"),
            InlineKeyboardButton(text="💼 Новое бизнес-сканирование", callback_data="buy:business"),
        ]
        cabinet_row = [InlineKeyboardButton(text="🗄 Мой кабинет", callback_data="my_cabinet")]
    else:
        scan_buttons = [
            InlineKeyboardButton(text="🔮 Личный разбор — 3 500 ₽", callback_data="buy:personal"),
            InlineKeyboardButton(text="💼 Бизнес-разбор — 10 000 ₽", callback_data="buy:business"),
        ]
        cabinet_row = [InlineKeyboardButton(text="🗄 Мой кабинет 🔒", callback_data="my_cabinet")]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            scan_buttons,
            cabinet_row,
            [InlineKeyboardButton(text="👁 Бесплатный мини-скан", callback_data="scan_type:mini")],
            [InlineKeyboardButton(text="🔷 О методе и создателе", callback_data="about_method")],
            [InlineKeyboardButton(text="📺 Подписаться на канал", url="https://t.me/Reva_mentor")],
            [InlineKeyboardButton(text="💬 Личная консультация с Юлией", url="https://t.me/Reva_Yulya6")],
            [InlineKeyboardButton(text="🆘 Помощь / сообщить об ошибке", callback_data="help_request")],
            [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
        ]
    )


_ABOUT_METHOD_TEXT = """👁 <b>Глаз Бога — метод, который видит то, что вы носите годами</b>

━━━━━━━━━━━━━━━━━━━━

<b>О МЕТОДЕ</b>

Я создала метод, который помогает людям увидеть свою ситуацию целиком.

Не «предсказываю». Не «гадаю».
Я анализирую, структурирую, показываю — где застряла энергия, почему не идут деньги, почему не складываются отношения, почему нет сил.

Это не магия.
Это работа с полем, с мышлением, с решениями, которые мы принимаем каждый день — но не всегда осознаём, почему они не ведут к результату.

━━━━━━━━━━━━━━━━━━━━

<b>КАК ЭТО РАБОТАЕТ</b>

Я использую несколько инструментов:

· <b>Аналитику</b> — дата рождения, имя как точка входа
· <b>Структуру</b> — разбор по уровням: деньги, отношения, тело, цели
· <b>Поле зрения</b> — где человек «завис», а где его точка роста

За 30–40 минут вы получаете чёткую карту:
— где вы сейчас
— что мешает
— куда двигаться
— какие решения приведут к результату

━━━━━━━━━━━━━━━━━━━━

<b>ОБО МНЕ</b>

Меня зовут <b>Юлия Рева</b>.

Я не гадалка и не маг.
Я — аналитик, стратег, человек, который прошёл через жёсткие изменения в бизнесе, в деньгах, в личной жизни — и создал инструмент, который помогает другим не топтаться на месте.

За мной и моим методом — тысячи анализов, логика, структура, путь от хаоса к ясности.

Я работаю с предпринимателями, с теми, кто устал от хаоса и хочет ясности.

━━━━━━━━━━━━━━━━━━━━

<b>ДЛЯ КОГО ЭТОТ МЕТОД</b>

· Есть бизнес, но деньги идут нестабильно
· Чувствуете нереализованный потенциал
· Устали, но не понимаете, куда уходит энергия
· Хотите видеть свои «слепые зоны» и принимать решения с опорой

Я не даю готовых решений.
Я даю структуру, ясность и направление.
А дальше вы сами — с вашим опытом, вашей волей, вашим масштабом.

━━━━━━━━━━━━━━━━━━━━

→ <a href="https://t.me/Reva_mentor">Канал @Reva_mentor</a>
→ <a href="https://t.me/Reva_Yulya6">Личная консультация — по записи</a>"""


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    # Пользователи с бесплатным доступом на 6 месяцев (username → месяцев)
    _FREE_ACCESS_USERS = {
        "yakushentsiya": 6,
    }

    user_service = UserService(session)
    user, created = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    # Автовыдача подписки при первом /start
    uname = (message.from_user.username or "").lower()
    if uname in _FREE_ACCESS_USERS:
        months = _FREE_ACCESS_USERS[uname]
        now = _dt.now(_tz.utc)
        if user.subscription_until is None or user.subscription_until < now:
            user.subscription_until = now + _td(days=30 * months)
            await session.commit()

    # Админ видит свою панель ВСЕГДА — первым делом
    is_admin = bool(settings.admin_telegram_id and message.from_user.id == settings.admin_telegram_id)
    if is_admin:
        name = message.from_user.first_name or "Юлия"
        await state.clear()
        await message.answer(
            f"👁 <b>Глаз Бога — панель Юлии</b>\n\nДобро пожаловать, {name}.",
            parse_mode="HTML",
            reply_markup=_admin_keyboard(),
        )
        return

    scan_service = ScanService(session)
    incomplete_scan = await scan_service.get_incomplete_scan(user.id)

    if incomplete_scan is not None:
        scan_type_label = _SCAN_TYPE_LABELS.get(incomplete_scan.scan_type, incomplete_scan.scan_type)
        resume_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data=f"resume_scan:{incomplete_scan.id}")],
                [InlineKeyboardButton(text="✖️ Отменить и начать заново", callback_data=f"cancel_scan:{incomplete_scan.id}")],
            ]
        )
        await message.answer(
            f"У вас незавершённый скан ({scan_type_label}). Хотите продолжить?",
            reply_markup=resume_keyboard,
        )
        return

    await state.clear()
    await log_event(session, message.from_user, "new_user" if created else "start")

    name = message.from_user.first_name or "друг"

    if created:
        text = (
            "👁 <b>Глаз Бога</b>\n\n"
            f"Добрый день, {name}.\n\n"
            "Это не гадание. Не предположение «попадёт — не попадёт».\n"
            "Это <b>точное сканирование</b> вас, вашего состояния и ваших желаний — "
            "отточенное до идеала.\n\n"
            "Я — AI-сканер Юлии Ревы. Нахожу корень, системную ошибку, даю вектор.\n\n"
            "Начните с <b>бесплатного мини-скана</b> — первый разбор полный и без вопросов."
        )
    else:
        text = (
            "👁 <b>Глаз Бога</b>\n\n"
            f"С возвращением, {name}.\n\n"
            "Это не гадание. Не предположение «попадёт — не попадёт».\n"
            "Это <b>точное сканирование</b> вас, вашего состояния и ваших желаний — "
            "отточенное до идеала.\n\n"
            "Выберите формат:"
        )

    has_subscription = (
        user.subscription_until is not None
        and user.subscription_until > _dt.now(_tz.utc)
    )
    await message.answer(text, parse_mode="HTML", reply_markup=_main_keyboard(has_subscription))


@router.callback_query(lambda c: c.data == "restart_bot")
async def handle_restart_bot(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer("Перезапускаю...")
    await state.clear()

    from app.services.scan_service import ScanService
    from app.services.user_service import UserService
    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )
    scan_service = ScanService(session)
    incomplete = await scan_service.get_incomplete_scan(user.id)
    if incomplete is not None:
        from app.models.scan import ScanStatus
        incomplete.status = ScanStatus.failed.value
        await session.commit()

    await callback.message.answer(
        "🔄 Бот перезапущен. Все активные процессы сброшены.\n\n"
        "Выберите действие:",
        reply_markup=_main_keyboard(),
    )


@router.callback_query(lambda c: c.data == "about_method")
async def handle_about_method(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        _ABOUT_METHOD_TEXT,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Назад в меню", callback_data="back_to_menu")],
            ]
        ),
    )


@router.callback_query(lambda c: c.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "👁 Выберите формат:",
        reply_markup=_main_keyboard(),
    )


@router.message(Command("setbirthdate"))
async def cmd_set_birth_date(message: Message, session: AsyncSession) -> None:
    """Сохранить дату рождения: /setbirthdate 15.05.1985"""
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажи дату: /setbirthdate 15.05.1985")
        return
    try:
        birth_date = _dt.strptime(parts[1].strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Пример: /setbirthdate 15.05.1985")
        return
    user_service = UserService(session)
    await user_service.update_birth_date(message.from_user.id, birth_date)
    await message.answer(
        f"✅ Дата рождения сохранена: {birth_date.strftime('%d.%m.%Y')}\n"
        "Теперь бот будет использовать её для нумерологии и не будет спрашивать снова."
    )


@router.callback_query(lambda c: c.data == "my_cabinet")
async def handle_my_cabinet(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await callback.answer()

    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    now = _dt.now(_tz.utc)
    has_sub = user.subscription_until is not None and user.subscription_until > now

    if not has_sub:
        await callback.message.answer(
            "🗄 <b>Мой кабинет</b>\n\n"
            "🔒 Кабинет доступен после оплаты разбора.\n\n"
            "В кабинете вы найдёте:\n"
            "· Все ваши сканы и разборы\n"
            "· Дату следующего сеанса\n"
            "· Историю вашей работы с ботом\n\n"
            "Оформите личный или бизнес разбор — и кабинет откроется:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔮 Личный разбор — 3 500 ₽", callback_data="buy:personal")],
                    [InlineKeyboardButton(text="💼 Бизнес-разбор — 10 000 ₽", callback_data="buy:business")],
                    [InlineKeyboardButton(text="← Назад", callback_data="back_to_menu")],
                ]
            ),
        )
        return

    scan_service = ScanService(session)
    total = await scan_service.count_completed_scans(user.id)
    recent = await scan_service.get_user_completed_scans(user.id, limit=3)

    sub_until = user.subscription_until.strftime("%d.%m.%Y") if user.subscription_until else "—"
    days_left = (user.subscription_until - now).days if user.subscription_until else 0

    _type_labels = {"mini": "Мини-скан", "personal": "Личный разбор", "business": "Бизнес-разбор"}

    scans_text = ""
    for s in recent:
        label = _type_labels.get(s.scan_type, s.scan_type)
        date = s.created_at.strftime("%d.%m.%Y") if s.created_at else "—"
        scans_text += f"  · {label} — {date}\n"

    if not scans_text:
        scans_text = "  (сканов пока нет)\n"

    text = (
        "🗄 <b>Мой кабинет</b>\n\n"
        f"✅ Подписка активна до: <b>{sub_until}</b> ({days_left} дн.)\n\n"
        f"📊 Всего завершённых разборов: <b>{total}</b>\n\n"
        f"🕐 Последние:\n{scans_text}\n"
        "Хотите новый разбор?"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔮 Новый личный", callback_data="buy:personal"),
                    InlineKeyboardButton(text="💼 Новый бизнес", callback_data="buy:business"),
                ],
                [InlineKeyboardButton(text="← Назад в меню", callback_data="back_to_menu")],
            ]
        ),
    )
