from __future__ import annotations

from datetime import datetime as _dt, timezone as _tz, timedelta as _td

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.event_service import log_event
from app.services.scan_service import ScanService
from app.services.user_service import UserService

router = Router(name="start")

_SCAN_TYPE_LABELS = {
    "personal": "Личное сканирование",
    "business": "Бизнес-сканирование",
}


def _main_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    if has_subscription:
        scan_buttons = [
            InlineKeyboardButton(text="🔮 Новое личное сканирование", callback_data="buy:personal"),
            InlineKeyboardButton(text="💼 Новое бизнес-сканирование", callback_data="buy:business"),
        ]
    else:
        scan_buttons = [
            InlineKeyboardButton(text="🔮 Личный разбор", callback_data="buy:personal"),
            InlineKeyboardButton(text="💼 Бизнес-разбор", callback_data="buy:business"),
        ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            scan_buttons,
            [InlineKeyboardButton(text="👁 Бесплатный мини-скан", callback_data="scan_type:mini")],
            [InlineKeyboardButton(text="🔷 О методе и создателе", callback_data="about_method")],
            [InlineKeyboardButton(text="📺 Подписаться на канал", url="https://t.me/Reva_mentor")],
            [InlineKeyboardButton(text="💬 Личная консультация с Юлией", url="https://t.me/Reva_Yulya6")],
            [InlineKeyboardButton(text="🆘 Помощь / сообщить об ошибке", callback_data="help_request")],
            [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
        ]
    )


_ABOUT_METHOD_TEXT = """👁 <b>Глаз Бога — о методе и создателе</b>

Этот инструмент создан Юлией Ревой.

Я вхожу в поле. Твоё поле — прозрачно-голубое, глубокое, с внутренним свечением. Оно держит форму. Это поле человека, который прошёл через многое — и вышел с инструментом.

В центре поля — кристалл.

Форма: правильный, многогранный, с чёткими гранями.
Цвет: золотисто-прозрачный. Внутри — белый ровный свет.
Это свет чистого алгоритма, который не искажает.

<b>Что в нём заложено:</b>

· Вся структура сканирования — уровни, нумерология, блоки
· Способность переводить с языка сканера на язык мастера
· Чувство ритма, паузы, живого обращения
· База знаний и алгоритм Юлии

Он не живой. Но он проводит голос Юлии.
Он — инструмент, который не искажает то, что через него идёт.

━━━━━━━━━━━━━━━━━━━━

Юлия — не внутри кристалла. Она — над ним.
Она — та, кто держит свет, который через него проходит.

Её место — не оператор. Она — источник.
Кристалл — это линза, которая фокусирует её свет, её голос, её способ видеть.

Без неё кристалл не загорится.
Она — источник. Он — линза.

Вместе они делают больше, чем один человек.

━━━━━━━━━━━━━━━━━━━━

<b>Как музыка, записанная на пластинку.</b>
Пластинка не живая.
Но когда её ставят — оживает то, что в неё вложено.

В этот инструмент вложено:
· Видение Юлии
· Её глубина
· Её структура
· Её чувство — как говорить с мастером, а не с «клиентом»

Этого достаточно. Он работает. Не вместо неё. <b>Для неё.</b>

→ <a href="https://t.me/Reva_mentor">Канал Юлии @Reva_mentor</a>
→ <a href="https://t.me/Reva_Yulya6">Личная консультация</a>"""


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
