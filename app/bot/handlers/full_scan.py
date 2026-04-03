"""Full scan FSM handler: dynamic 12-15 question questionnaire with progress indicator.

Entry points:
  - start_questionnaire_after_payment() called by payment handler after Stars payment confirmed
  - resume_scan:{scan_id} callback (from /start resume prompt)
  - cancel_scan:{scan_id} callback (from /start cancel prompt)

FSM data structure stored in aiogram state:
  {
      "scan_id": int,
      "user_id": int,
      "scan_type": "personal" | "business",
      "current_index": int,  # 0-based question index currently being answered
  }
"""

from __future__ import annotations

import logging
from datetime import date

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.questions import QuestionDef, get_questions_for_type, get_total_questions
from datetime import datetime as _dt


def parse_birth_date(text: str):
    return _dt.strptime(text.strip(), "%d.%m.%Y").date()
from aiogram.filters import StateFilter

from app.bot.states import FullScanStates
from app.models.scan import ScanStatus
from app.services.full_scan_ai_service import BLOCK_KEYS, FullScanAIService
from app.services.scan_service import ScanService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

_BLOCK_LABELS = {
    "архитектура": "👤 Состояние владельца",
    "слепые_зоны": "🔍 Поломка — что мешает",
    "энергетические_блоки": "🌀 Глубина — родовое и скрытое",
    "команда": "🛠 Инструменты и команда",
    "деньги": "💰 Деньги",
    "рекомендации": "🎯 Вектор и послание",
}

router = Router(name="full_scan")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Build a one-button-per-row inline keyboard from (text, callback_data) pairs."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=cd)] for t, cd in buttons
        ]
    )


async def generate_and_deliver_report(
    bot: Bot,
    chat_id: int,
    scan_id: int,
    scan_type: str,
    session: AsyncSession,
) -> None:
    """Generate full AI report and deliver as split Telegram messages.

    Sends 8 messages total:
      1. Status message ("Генерирую отчёт...")
      2. Numerology block
      3-8. Six content blocks (архитектура, слепые_зоны, ..., рекомендации)

    On error (missing birth_date or AI failure): sets scan.status=failed,
    commits, and sends a user-visible error message.
    """
    scan_service = ScanService(session)

    await bot.send_message(chat_id, "Генерирую отчёт... Это займёт около 30 секунд.")

    scan = await scan_service.get_scan(scan_id)
    answers = scan.answers or {}

    birth_date_str = answers.get("birth_date", "")
    birth_date = None
    try:
        birth_date = date.fromisoformat(birth_date_str)
    except (ValueError, TypeError):
        pass

    if birth_date is None:
        # Fallback: check user profile
        from app.models.user import User as UserModel
        user = await session.get(UserModel, scan.user_id)
        if user is not None and user.birth_date:
            birth_date = user.birth_date
            # Save to scan answers so it's consistent
            await scan_service.save_answer(scan_id, "birth_date", birth_date.isoformat())
            scan = await scan_service.get_scan(scan_id)
            answers = scan.answers or {}

    if birth_date is None:
        logger.error(
            "Missing or invalid birth_date for scan_id=%s: %r", scan_id, birth_date_str
        )
        scan.status = ScanStatus.failed.value
        await session.commit()
        await bot.send_message(
            chat_id,
            "Не удалось определить дату рождения. Пожалуйста, начните скан заново (/start).",
        )
        return

    try:
        ai_service = FullScanAIService()
        report = await ai_service.generate_full_report(answers, birth_date, scan_type)
    except Exception:
        logger.exception("AI generation failed for scan_id=%s", scan_id)
        scan.status = ScanStatus.failed.value
        await session.commit()
        await bot.send_message(
            chat_id,
            "Произошла ошибка при генерации отчёта.\n\n"
            "Нажми «Перезапустить бота» и попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
            ]),
        )
        return

    token_usage = report.get("token_usage", {})
    await scan_service.complete_full_scan(scan_id, report, token_usage)

    # Deliver numerology block first
    numerology = report.get("numerology", {})
    await bot.send_message(
        chat_id,
        (
            f"*Нумерология*\n"
            f"Число души: {numerology.get('soul_number', '—')}\n"
            f"Число жизненного пути: {numerology.get('life_path_number', '—')}"
        ),
        parse_mode="Markdown",
    )

    # Deliver 6 content blocks
    for key in BLOCK_KEYS:
        label = _BLOCK_LABELS[key]
        content = report.get(key, "недостаточно данных для анализа этого аспекта")
        await bot.send_message(
            chat_id,
            f"*{label}*\n\n{content}",
            parse_mode="Markdown",
        )

    # Soft closing — questions, personal session, review
    await bot.send_message(
        chat_id,
        "Это твой разбор.\n\n"
        "Пусть осядет.\n\n"
        "Если что-то отозвалось — или хочешь разобрать глубже — "
        "напиши мне лично. Я отвечаю.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Есть вопрос по разбору", url="https://t.me/Reva_Yulya6")],
                [InlineKeyboardButton(text="🔮 Хочу личную сессию с Юлией", callback_data="request_session")],
                [InlineKeyboardButton(text="⭐ Оставить отзыв", url="https://t.me/Reva_mentor")],
            ]
        ),
    )

    if scan_type == "personal":
        await bot.send_message(
            chat_id,
            "🎁 <b>Подарок к твоему разбору</b>\n\n"
            "Я подготовила для тебя персональную практику — "
            "упражнение, которое поможет закрепить твой вектор и убрать главный блок.\n\n"
            "Нажми кнопку ниже — получишь практику прямо сейчас.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 Получить практику в подарок", callback_data=f"gift_practice:{scan_id}")],
                ]
            ),
        )


async def _send_question(
    bot: Bot,
    chat_id: int,
    question: QuestionDef,
    index: int,
    total: int,
) -> None:
    """Send the question message with progress indicator.

    Keyboard questions use prefix fq:{key}:{value}.
    Optional text questions get a "Пропустить" button.
    birth_date gets an example hint appended.
    """
    progress_prefix = f"Вопрос {index + 1} из {total}\n\n"
    text = progress_prefix + question.text

    if question.key == "birth_date":
        text += "\n\nНапример: 15.05.1990"

    if question.input_type == "keyboard" and question.options:
        buttons = [(label, f"fq:{question.key}:{val}") for label, val in question.options]
        keyboard = _make_keyboard(buttons)
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    elif question.input_type == "text" and not question.required:
        keyboard = _make_keyboard([("Пропустить", f"fq_skip:{question.key}")])
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, text)


async def _advance_to_next(
    state: FSMContext,
    session: AsyncSession,
    scan_id: int,
    scan_type: str,
    next_index: int,
    bot: Bot,
    chat_id: int,
) -> None:
    """Move to the next question or complete the questionnaire."""
    total = get_total_questions(scan_type)

    if next_index >= total:
        # All questions answered — complete
        scan_service = ScanService(session)
        await scan_service.complete_questionnaire(scan_id)
        await state.set_state(FullScanStates.completing)
        await bot.send_message(chat_id, "Анкета заполнена!")
        await state.clear()
        await generate_and_deliver_report(bot, chat_id, scan_id, scan_type, session)
    else:
        questions = get_questions_for_type(scan_type)
        next_question = questions[next_index]
        await state.update_data(current_index=next_index)
        next_state = getattr(FullScanStates, f"q{next_index}")
        await state.set_state(next_state)
        await _send_question(bot, chat_id, next_question, next_index, total)


# ---------------------------------------------------------------------------
# Public entry point called by payment handler after Stars payment confirmed
# ---------------------------------------------------------------------------


async def start_questionnaire_after_payment(
    bot: Bot,
    chat_id: int,
    scan_id: int,
    scan_type: str,
    state: FSMContext,
    session: AsyncSession,
    telegram_first_name: str = "",
) -> None:
    """Start the full scan questionnaire after payment is confirmed.

    Pre-fills birth_date and name from user profile so those questions are skipped
    if the data is already known from a previous session.
    """
    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)
    existing_answers = dict(scan.answers or {}) if scan is not None else {}

    # Pre-fill birth_date from user profile (if not already answered)
    if "birth_date" not in existing_answers and scan is not None:
        from app.models.user import User as UserModel
        user = await session.get(UserModel, scan.user_id)
        if user is not None and user.birth_date:
            await scan_service.save_answer(scan_id, "birth_date", user.birth_date.isoformat())
            existing_answers["birth_date"] = user.birth_date.isoformat()

    # Pre-fill name from Telegram profile (if not already answered)
    if "name" not in existing_answers and telegram_first_name:
        await scan_service.save_answer(scan_id, "name", telegram_first_name)
        existing_answers["name"] = telegram_first_name

    total = get_total_questions(scan_type)
    questions = get_questions_for_type(scan_type)

    # Ищем первый вопрос, на который ещё нет ответа.
    # НЕ используем len(existing_answers) — при пред-заполнении name но не birth_date
    # len=1 прыгает на индекс 1, пропуская birth_date (индекс 0).
    current_index = total  # по умолчанию — всё заполнено
    for i, q in enumerate(questions):
        if q.key not in existing_answers:
            current_index = i
            break

    if current_index >= total:
        # Все вопросы уже заполнены — сразу генерируем
        await state.update_data(
            scan_id=scan_id,
            user_id=scan.user_id if scan is not None else 0,
            scan_type=scan_type,
            current_index=current_index,
        )
        await state.clear()
        await generate_and_deliver_report(bot, chat_id, scan_id, scan_type, session)
        return

    await state.update_data(
        scan_id=scan_id,
        user_id=scan.user_id if scan is not None else 0,
        scan_type=scan_type,
        current_index=current_index,
    )
    fsm_state = getattr(FullScanStates, f"q{current_index}")
    await state.set_state(fsm_state)

    first_question = questions[current_index]
    await _send_question(bot, chat_id, first_question, current_index, total)


# ---------------------------------------------------------------------------
# Keyboard answer handler — handles ALL keyboard questions
# ---------------------------------------------------------------------------


@router.callback_query(StateFilter(FullScanStates), lambda c: c.data.startswith("fq:"))
async def handle_keyboard_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Handle inline keyboard answers. Callback data format: fq:{key}:{value}"""
    # Parse fq:{key}:{value} — key may not contain colon, value might
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer()
        return

    key = parts[1]
    value = parts[2]

    data = await state.get_data()
    scan_id: int = data["scan_id"]
    scan_type: str = data["scan_type"]
    current_index: int = data["current_index"]

    # Guard against stale keyboard buttons from previous questionnaire sessions
    questions = get_questions_for_type(scan_type)
    if current_index >= len(questions) or key != questions[current_index].key:
        await callback.answer("Устаревшая кнопка — пропускаю", show_alert=False)
        return

    scan_service = ScanService(session)
    await scan_service.save_answer(scan_id, key, value)

    await _advance_to_next(
        state=state,
        session=session,
        scan_id=scan_id,
        scan_type=scan_type,
        next_index=current_index + 1,
        bot=callback.message.bot,
        chat_id=callback.message.chat.id,
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Skip handler — for optional text questions
# ---------------------------------------------------------------------------


@router.callback_query(StateFilter(FullScanStates), lambda c: c.data.startswith("fq_skip:"))
async def handle_skip_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Handle skip button for optional questions. Saves empty string."""
    key = callback.data[len("fq_skip:"):]

    data = await state.get_data()
    scan_id: int = data["scan_id"]
    scan_type: str = data["scan_type"]
    current_index: int = data["current_index"]

    # Guard against stale skip buttons from previous questionnaire sessions
    questions = get_questions_for_type(scan_type)
    if current_index >= len(questions) or key != questions[current_index].key:
        await callback.answer("Устаревшая кнопка — пропускаю", show_alert=False)
        return

    scan_service = ScanService(session)
    await scan_service.save_answer(scan_id, key, "")

    await _advance_to_next(
        state=state,
        session=session,
        scan_id=scan_id,
        scan_type=scan_type,
        next_index=current_index + 1,
        bot=callback.message.bot,
        chat_id=callback.message.chat.id,
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Text input handler — for text questions (birth_date, name, situation, social_url)
# ---------------------------------------------------------------------------


@router.message(StateFilter(FullScanStates))
async def handle_text_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Handle free-text answers for all FullScanStates text questions."""
    data = await state.get_data()
    scan_id: int = data["scan_id"]
    scan_type: str = data["scan_type"]
    current_index: int = data["current_index"]

    questions = get_questions_for_type(scan_type)
    question = questions[current_index]

    text_input = message.text or ""

    if question.key == "birth_date":
        try:
            birth_date = parse_birth_date(text_input)
        except ValueError:
            await message.reply(
                "Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ\n\nНапример: 15.05.1990"
            )
            return
        # Also update user profile birth date
        user_service = UserService(session)
        await user_service.update_birth_date(message.from_user.id, birth_date)
        value = birth_date.isoformat()
    else:
        value = text_input

        # Apply max_length truncation
        if question.max_length is not None:
            value = value[: question.max_length]

        # Basic URL validation for social_url (log warning only, do not reject)
        if question.key == "social_url" and value:
            if not (
                value.startswith("http://")
                or value.startswith("https://")
                or "." in value
            ):
                logger.warning(
                    "social_url for scan_id=%s looks invalid: %r", scan_id, value
                )

    scan_service = ScanService(session)
    await scan_service.save_answer(scan_id, question.key, value)

    await _advance_to_next(
        state=state,
        session=session,
        scan_id=scan_id,
        scan_type=scan_type,
        next_index=current_index + 1,
        bot=message.bot,
        chat_id=message.chat.id,
    )


# ---------------------------------------------------------------------------
# Resume scan callback (from /start resume prompt)
# ---------------------------------------------------------------------------


@router.callback_query(lambda c: c.data.startswith("resume_scan:"))
async def handle_resume_scan(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Resume an incomplete scan from the exact question where user left off."""
    scan_id = int(callback.data.split(":")[1])

    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)

    if scan is None:
        await callback.message.answer("Скан не найден. Используйте /start чтобы начать заново.")
        await callback.answer()
        return

    scan_type = scan.scan_type
    existing_answers = scan.answers or {}
    questions = get_questions_for_type(scan_type)
    total = get_total_questions(scan_type)

    # Найти первый незаполненный вопрос
    current_index = total
    for i, q in enumerate(questions):
        if q.key not in existing_answers:
            current_index = i
            break

    if current_index >= total:
        # Все вопросы заполнены, но AI не успел/упал — запускаем генерацию
        await state.update_data(
            scan_id=scan.id,
            user_id=scan.user_id,
            scan_type=scan_type,
            current_index=current_index,
        )
        await state.clear()
        await callback.answer()
        await generate_and_deliver_report(
            callback.message.bot, callback.message.chat.id, scan.id, scan_type, session
        )
        return

    await state.update_data(
        scan_id=scan.id,
        user_id=scan.user_id,
        scan_type=scan_type,
        current_index=current_index,
    )

    fsm_state = getattr(FullScanStates, f"q{current_index}")
    await state.set_state(fsm_state)

    question = questions[current_index]

    await _send_question(callback.message.bot, callback.message.chat.id, question, current_index, total)
    await callback.answer()


# ---------------------------------------------------------------------------
# Cancel scan callback (from /start cancel prompt)
# ---------------------------------------------------------------------------


@router.callback_query(lambda c: c.data.startswith("cancel_scan:"))
async def handle_cancel_scan(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Cancel an incomplete scan and let user start fresh."""
    scan_id = int(callback.data.split(":")[1])

    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)

    if scan is not None:
        scan.status = ScanStatus.failed.value
        await session.commit()

    await state.clear()
    await callback.message.answer(
        "Скан отменён. Используйте /start чтобы начать заново."
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Gift practice callback — генерирует персональную практику после личного разбора
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("gift_practice:"))
async def handle_gift_practice(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await callback.answer("Готовлю практику...")

    scan_id = int(callback.data.split(":")[1])
    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)

    if not scan:
        await callback.message.answer("Не удалось найти разбор.")
        return

    answers = scan.answers or {}
    user_name = answers.get("name") or callback.from_user.first_name or "друг"
    main_request = answers.get("request") or answers.get("situation") or ""
    main_block = (scan.report or {}).get("слепые_зоны", "") if scan.report else ""

    waiting = await callback.message.answer("🎁 Готовлю твою практику...")

    from app.services.ai_client import messages_create
    try:
        response = await messages_create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": (
                    f"Ты — Юлия Рева, аналитик и коуч. Составь персональную практику для {user_name}.\n\n"
                    f"Их запрос: {main_request}\n"
                    f"Главный блок из разбора: {main_block}\n\n"
                    "Практика должна быть:\n"
                    "— конкретная, на 5-10 минут в день\n"
                    "— телесная или письменная (дыхание, движение, или запись)\n"
                    "— направлена на снятие именно этого блока\n"
                    "— с чётким инструктажем: что делать, как, сколько раз\n\n"
                    "Формат: тёплый, живой текст без списков. До 300 слов."
                )
            }]
        )
        practice_text = response.content[0].text
    except Exception:
        practice_text = (
            "Практика «Точка опоры»\n\n"
            "Каждое утро, сразу после пробуждения — 5 минут.\n\n"
            "Сядь удобно. Положи руку на сердце.\n"
            "Задай себе один вопрос: «Что я сейчас чувствую?»\n"
            "Не анализируй. Просто назови это слово вслух или запиши.\n\n"
            "Потом спроси: «Что мне сейчас нужно?»\n"
            "И снова — одно слово. Без объяснений.\n\n"
            "Делай это 7 дней подряд. На 7-й день перечитай все записи.\n"
            "Ты увидишь паттерн — то, что повторяется.\n"
            "Это и есть твоя точка входа."
        )

    try:
        await waiting.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"🎁 <b>Твоя персональная практика</b>\n\n{practice_text}\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "Если хочешь разобрать практику глубже — напиши Юлии:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
        ]),
    )
