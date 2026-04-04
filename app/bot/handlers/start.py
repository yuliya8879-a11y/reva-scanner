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
            [InlineKeyboardButton(text="👁 Мини-скан — 590 ₽", callback_data="scan_type:mini")],
            [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔑 API ключи — статус/переключение", callback_data="api_status")],
        ]
    )


def _main_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    if has_subscription:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔮 Новое личное сканирование", callback_data="buy:personal")],
                [InlineKeyboardButton(text="💼 Новое бизнес-сканирование", callback_data="buy:business")],
                [InlineKeyboardButton(text="🗄 Мой кабинет", callback_data="my_cabinet")],
                [InlineKeyboardButton(text="👁 Мини-скан — 590 ₽", callback_data="scan_type:mini")],
                [InlineKeyboardButton(text="🔷 О методе и создателе", callback_data="about_method")],
                [InlineKeyboardButton(text="📺 Подписаться на канал", url="https://t.me/Reva_mentor")],
                [InlineKeyboardButton(text="💬 Личная консультация с Юлией", url="https://t.me/Reva_Yulya6")],
                [InlineKeyboardButton(text="🆘 Помощь / сообщить об ошибке", callback_data="help_request")],
                [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Мини-скан — 590 ₽", callback_data="scan_type:mini")],
            [InlineKeyboardButton(text="💳 Оплатить — Личный разбор — 3 500 ₽", callback_data="buy:personal")],
            [InlineKeyboardButton(text="💳 Оплатить — Бизнес-разбор — 10 000 ₽", callback_data="buy:business")],
            [InlineKeyboardButton(text="🗄 Мой кабинет 🔒", callback_data="my_cabinet")],
            [InlineKeyboardButton(text="🔷 О методе и создателе", callback_data="about_method")],
            [InlineKeyboardButton(text="📺 Подписаться на канал", url="https://t.me/Reva_mentor")],
            [InlineKeyboardButton(text="💬 Личная консультация с Юлией", url="https://t.me/Reva_Yulya6")],
            [InlineKeyboardButton(text="🆘 Помощь / сообщить об ошибке", callback_data="help_request")],
            [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
        ]
    )


_ABOUT_METHOD_TEXT = """🔍 <b>Цифровой структурный анализ личности и ситуаций</b>

━━━━━━━━━━━━━━━━━━━━

<b>ЧТО ДЕЛАЕТ ЭТОТ БОТ</b>

Бот предназначен для информационно-аналитической поддержки в вопросах самоанализа, понимания личных и профессиональных ситуаций, выявления повторяющихся сценариев и паттернов поведения.

Бот не говорит: «я предсказываю будущее».
Бот говорит: «на основе анализа ваших данных выявлена повторяющаяся тема».

Это информационно-аналитический инструмент. Не магия. Не эзотерика.

━━━━━━━━━━━━━━━━━━━━

<b>КАК РАБОТАЕТ МЕТОД</b>

· <b>Числовые данные</b> — дата рождения как точка входа для анализа временных и циклических паттернов (не астрология, не нумерология)
· <b>Именные данные</b> — имя как идентификатор для построения статистически значимых корреляций
· <b>Текстовый запрос</b> — слова, формулировки, повторяющиеся темы — семантический и структурный анализ

<b>Алгоритм:</b>
1. Получение входных данных (дата, имя, запрос)
2. Анализ по математическим и семантическим алгоритмам
3. Структурированный отчёт: повторяющиеся темы, внутренние противоречия, зоны внимания

Бот не «считывает поле». Он обрабатывает данные, которые предоставил пользователь, и выдаёт их в структурированном виде.

━━━━━━━━━━━━━━━━━━━━

<b>ЧТО ВЫ ПОЛУЧАЕТЕ</b>

· Структуру там, где был хаос
· Факты — без домыслов и осуждений
· Ясность по конкретному запросу
· Практики для самостоятельной работы

Бот не ставит диагнозы, не предсказывает будущее, не заменяет психолога, не требует веры, не создаёт зависимость, не пугает.

━━━━━━━━━━━━━━━━━━━━

<b>ОБО МНЕ</b>

Меня зовут <b>Юлия Рева</b>.

Я — аналитик и стратег. Прошла через жёсткие изменения в бизнесе, деньгах, личной жизни — и создала инструмент, который помогает другим не топтаться на месте.

За методом — тысячи анализов, логика, структура, путь от хаоса к ясности.

━━━━━━━━━━━━━━━━━━━━

→ <a href="https://t.me/Reva_mentor">Канал @Reva_mentor</a>
→ <a href="https://t.me/Reva_Yulya6">Личная консультация — по записи</a>"""


_OFERTA_TEXT = """📋 <b>Условия использования @Eye888888_bot</b>

Перед началом работы ознакомьтесь с условиями.

<b>1. Характер услуги</b>
Сервис предоставляет информационно-аналитические материалы на основе числовых данных (дата рождения) и текстового запроса пользователя. <b>Не является</b> психологической, медицинской, консультационной или терапевтической услугой. Не требует лицензии.

<b>2. Результат</b>
Разбор — информация для самостоятельного анализа. Не является диагнозом, прогнозом, медицинским заключением или руководством к обязательному действию.

<b>3. Стоимость</b>
• Мини-скан — 590 ₽
• Личный разбор — 3 500 ₽
• Бизнес-разбор — 10 000 ₽

<b>4. Возврат</b>
Услуга является цифровым контентом, предоставляемым немедленно. После выдачи разбора возврат не производится (ст. 26.1 ЗоЗПП). При технической ошибке бота — повтор или возврат по обращению к @Reva_Yulya6.

<b>5. Персональные данные</b>
Сервис обрабатывает: дату рождения, имя, Telegram ID, текст запроса. Данные используются исключительно для формирования разбора и не передаются третьим лицам. Нажимая «Принимаю», вы даёте согласие на обработку персональных данных в соответствии с ФЗ-152.

<b>6. Ответственность</b>
Исполнитель не несёт ответственности за решения, принятые пользователем на основе разбора. Пользователь действует самостоятельно и осознанно.

<i>ИП Рева Юлия Александровна
ИНН: 324500804640</i>"""


@router.callback_query(lambda c: c.data == "accept_terms")
async def handle_accept_terms(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Пользователь принял оферту — отмечаем в БД и показываем главное меню."""
    from app.services.user_service import UserService
    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )
    user.terms_accepted = True
    await session.commit()
    await callback.answer("Спасибо!")

    name = callback.from_user.first_name or "друг"
    text = (
        "👁 <b>Глаз Бога</b>\n\n"
        f"Добрый день, {name}.\n\n"
        "Это не гадание. Не предположение «попадёт — не попадёт».\n"
        "Это <b>точное сканирование</b> вас, вашего состояния и ваших желаний — "
        "отточенное до идеала.\n\n"
        "Я — AI-сканер Юлии Ревы. Нахожу корень, системную ошибку, даю вектор.\n\n"
        "Начните с <b>мини-скана</b> (590 ₽) — быстрый разбор по дате рождения."
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=_main_keyboard(False))


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

    # Если пользователь ещё не принял оферту — показываем её первой
    if not user.terms_accepted:
        await message.answer(
            _OFERTA_TEXT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms")],
                [InlineKeyboardButton(text="📋 Политика конфиденциальности", url="https://t.me/Eye888888_bot")],
            ]),
        )
        return

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
            "Начните с <b>мини-скана</b> (590 ₽) — быстрый разбор по дате рождения и запросу."
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
                    [InlineKeyboardButton(text="💳 Личный разбор — 3 500 ₽", callback_data="buy:personal")],
                    [InlineKeyboardButton(text="💳 Бизнес-разбор — 10 000 ₽", callback_data="buy:business")],
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
                [InlineKeyboardButton(text="💳 Личный разбор — 3 500 ₽", callback_data="buy:personal")],
                [InlineKeyboardButton(text="💳 Бизнес-разбор — 10 000 ₽", callback_data="buy:business")],
                [InlineKeyboardButton(text="← Назад в меню", callback_data="back_to_menu")],
            ]
        ),
    )
