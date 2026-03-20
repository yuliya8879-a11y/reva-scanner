"""Mini-scan FSM handlers: 5-question flow -> AI report -> upsell."""

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import MiniScanStates
from app.services.ai_service import AIService
from app.services.numerology import calculate_soul_number
from app.services.scan_service import ScanService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="mini_scan")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AREA_LABELS: dict[str, str] = {
    "services": "Услуги",
    "products": "Продукты",
    "it": "IT",
    "trade": "Торговля",
    "other": "Другое",
}

_AGE_LABELS: dict[str, str] = {
    "lt1": "< 1 года",
    "1to3": "1\u20133 года",
    "3to7": "3\u20137 лет",
    "7plus": "7+ лет",
}

_PAIN_LABELS: dict[str, str] = {
    "no_clients": "Нет клиентов",
    "no_team": "Нет команды",
    "no_system": "Нет системы",
    "no_money": "Нет денег",
    "everything": "Всё сразу",
}


def parse_birth_date(text: str):
    """Parse a date string in DD.MM.YYYY format.

    Returns a datetime.date object.
    Raises ValueError if the format is invalid.
    """
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()


def _make_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Build a one-button-per-row inline keyboard from (text, callback_data) pairs."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=cd)] for t, cd in buttons]
    )


# ---------------------------------------------------------------------------
# scan_type callbacks — entry points from /start
# ---------------------------------------------------------------------------


@router.callback_query(lambda c: c.data == "scan_type:mini")
async def handle_scan_type_mini(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    scan_service = ScanService(session)
    scan = await scan_service.create_mini_scan(user.id)

    await state.update_data(scan_id=scan.id, user_id=user.id, answers={})
    await state.set_state(MiniScanStates.birth_date)

    await callback.message.answer(
        "\U0001f4c5 Вопрос 1 из 5\n\n"
        "Введите вашу дату рождения в формате ДД.ММ.ГГГГ\n\n"
        "Например: 15.05.1990"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data in ("scan_type:personal", "scan_type:business"))
async def handle_scan_type_paid(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Полное сканирование будет доступно после мини-скана. Начните с бесплатного мини-скана!"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Q1: birth date (text input)
# ---------------------------------------------------------------------------


@router.message(MiniScanStates.birth_date)
async def handle_birth_date(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        birth_date = parse_birth_date(message.text or "")
    except ValueError:
        await message.reply(
            "Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например: 15.05.1990)"
        )
        return

    user_service = UserService(session)
    await user_service.update_birth_date(message.from_user.id, birth_date)

    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["birth_date"] = birth_date.isoformat()
    await state.update_data(answers=answers, birth_date=birth_date.isoformat())

    keyboard = _make_keyboard(
        [
            ("Услуги", "area:services"),
            ("Продукты", "area:products"),
            ("IT", "area:it"),
            ("Торговля", "area:trade"),
            ("Другое", "area:other"),
        ]
    )
    await message.answer(
        "\U0001f4ca Вопрос 2 из 5\n\nВаша основная сфера бизнеса?",
        reply_markup=keyboard,
    )
    await state.set_state(MiniScanStates.business_area)


# ---------------------------------------------------------------------------
# Q2: business area (inline keyboard)
# ---------------------------------------------------------------------------


@router.callback_query(MiniScanStates.business_area, lambda c: c.data.startswith("area:"))
async def handle_business_area(callback: CallbackQuery, state: FSMContext) -> None:
    area_key = callback.data.split(":", 1)[1]
    area_label = _AREA_LABELS.get(area_key, area_key)

    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["business_area"] = area_label
    await state.update_data(answers=answers)

    keyboard = _make_keyboard(
        [
            ("< 1 года", "age:lt1"),
            ("1\u20133 года", "age:1to3"),
            ("3\u20137 лет", "age:3to7"),
            ("7+ лет", "age:7plus"),
        ]
    )
    await callback.message.answer(
        "\u23f3 Вопрос 3 из 5\n\nСколько лет вашему бизнесу?",
        reply_markup=keyboard,
    )
    await state.set_state(MiniScanStates.business_age)
    await callback.answer()


# ---------------------------------------------------------------------------
# Q3: business age (inline keyboard)
# ---------------------------------------------------------------------------


@router.callback_query(MiniScanStates.business_age, lambda c: c.data.startswith("age:"))
async def handle_business_age(callback: CallbackQuery, state: FSMContext) -> None:
    age_key = callback.data.split(":", 1)[1]
    age_label = _AGE_LABELS.get(age_key, age_key)

    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["business_age"] = age_label
    await state.update_data(answers=answers)

    keyboard = _make_keyboard(
        [
            ("Нет клиентов", "pain:no_clients"),
            ("Нет команды", "pain:no_team"),
            ("Нет системы", "pain:no_system"),
            ("Нет денег", "pain:no_money"),
            ("Всё сразу", "pain:everything"),
        ]
    )
    await callback.message.answer(
        "\U0001f525 Вопрос 4 из 5\n\nВаша главная боль прямо сейчас?",
        reply_markup=keyboard,
    )
    await state.set_state(MiniScanStates.main_pain)
    await callback.answer()


# ---------------------------------------------------------------------------
# Q4: main pain (inline keyboard)
# ---------------------------------------------------------------------------


@router.callback_query(MiniScanStates.main_pain, lambda c: c.data.startswith("pain:"))
async def handle_main_pain(callback: CallbackQuery, state: FSMContext) -> None:
    pain_key = callback.data.split(":", 1)[1]
    pain_label = _PAIN_LABELS.get(pain_key, pain_key)

    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["main_pain"] = pain_label
    await state.update_data(answers=answers)

    keyboard = _make_keyboard([("Пропустить", "situation:skip")])
    await callback.message.answer(
        "\U0001f4ac Вопрос 5 из 5\n\nКратко опишите вашу ситуацию (до 500 символов)\n\nИли нажмите «Пропустить»",
        reply_markup=keyboard,
    )
    await state.set_state(MiniScanStates.situation)
    await callback.answer()


# ---------------------------------------------------------------------------
# Q5: situation — two handlers (skip button + text input)
# ---------------------------------------------------------------------------


@router.callback_query(MiniScanStates.situation, lambda c: c.data == "situation:skip")
async def handle_situation_skip(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["situation"] = ""
    await state.update_data(answers=answers)

    await callback.answer()
    await _generate_and_send_report(callback.message, state, session, callback.from_user.id)


@router.message(MiniScanStates.situation)
async def handle_situation_text(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "")[:500]
    data = await state.get_data()
    answers = dict(data.get("answers", {}))
    answers["situation"] = text
    await state.update_data(answers=answers)

    await _generate_and_send_report(message, state, session, message.from_user.id)


# ---------------------------------------------------------------------------
# Generation helper
# ---------------------------------------------------------------------------


async def _generate_and_send_report(
    message_obj: Message,
    state: FSMContext,
    session: AsyncSession,
    telegram_id: int,
) -> None:
    """Send scanning feedback, call AI, persist report, send teaser + upsell."""
    data = await state.get_data()
    scan_id: int = data["scan_id"]
    answers: dict = data.get("answers", {})
    birth_date_str: str = data.get("birth_date", "")

    bot = message_obj.bot
    chat_id = message_obj.chat.id

    scanning_msg = await bot.send_message(chat_id, "\U0001f52e Сканирую...")

    try:
        scan_service = ScanService(session)
        await scan_service.update_answers(scan_id, answers)

        from datetime import date as _date
        birth_date = _date.fromisoformat(birth_date_str) if birth_date_str else _date(1990, 1, 1)
        soul_number = calculate_soul_number(birth_date)

        ai_service = AIService()
        report_text, token_usage = await ai_service.generate_mini_report(answers, soul_number)

        await scan_service.complete_mini_scan(
            scan_id,
            report_text,
            {"soul_number": soul_number},
            token_usage,
        )

        await scanning_msg.delete()

        await bot.send_message(
            chat_id,
            f"\U0001f441 <b>Результат мини-скана</b>\n\n{report_text}",
            parse_mode="HTML",
        )

        upsell_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Получить полный скан 3500\u2b50", callback_data="buy:personal")],
                [InlineKeyboardButton(text="Получить полный скан 7000\u2b50", callback_data="buy:business")],
            ]
        )
        await bot.send_message(
            chat_id,
            "Это лишь верхушка айсберга. Полный скан раскроет 6 блоков: архитектуру бизнеса, "
            "слепые зоны, энергетические блоки, команду, деньги и персональные рекомендации.",
            reply_markup=upsell_keyboard,
        )

    except Exception:
        logger.exception("Error generating mini-scan report for scan_id=%s", scan_id)
        try:
            await scanning_msg.delete()
        except Exception:
            pass
        await bot.send_message(
            chat_id,
            "Произошла ошибка при генерации. Попробуйте ещё раз через /start",
        )
    finally:
        await state.clear()
