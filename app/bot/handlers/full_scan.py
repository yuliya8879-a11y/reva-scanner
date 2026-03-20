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

from app.bot.handlers.mini_scan import parse_birth_date
from app.bot.questions import QuestionDef, get_questions_for_type, get_total_questions
from app.bot.states import FullScanStates
from app.models.scan import ScanStatus
from app.services.full_scan_ai_service import BLOCK_KEYS, FullScanAIService
from app.services.scan_service import ScanService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

_BLOCK_LABELS = {
    "архитектура": "Архитектура",
    "слепые_зоны": "Слепые зоны",
    "энергетические_блоки": "Энергетические блоки owner'а",
    "команда": "Команда",
    "деньги": "Деньги",
    "рекомендации": "Рекомендации",
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
    try:
        birth_date = date.fromisoformat(birth_date_str)
    except (ValueError, TypeError):
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
            "Произошла ошибка при генерации отчёта. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
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
) -> None:
    """Start the full scan questionnaire after payment is confirmed.

    Called by app.bot.handlers.payment.handle_successful_payment.
    Resets FSM state to first unanswered question (or question 0 if scan is fresh).
    """
    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)
    current_index = len(scan.answers or {}) if scan is not None else 0
    total = get_total_questions(scan_type)
    questions = get_questions_for_type(scan_type)

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


@router.callback_query(FullScanStates, lambda c: c.data.startswith("fq:"))
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


@router.callback_query(FullScanStates, lambda c: c.data.startswith("fq_skip:"))
async def handle_skip_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Handle skip button for optional questions. Saves empty string."""
    key = callback.data[len("fq_skip:"):]

    data = await state.get_data()
    scan_id: int = data["scan_id"]
    scan_type: str = data["scan_type"]
    current_index: int = data["current_index"]

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


@router.message(FullScanStates)
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

    current_index = len(scan.answers or {})
    scan_type = scan.scan_type

    await state.update_data(
        scan_id=scan.id,
        user_id=scan.user_id,
        scan_type=scan_type,
        current_index=current_index,
    )

    fsm_state = getattr(FullScanStates, f"q{current_index}")
    await state.set_state(fsm_state)

    total = get_total_questions(scan_type)
    questions = get_questions_for_type(scan_type)
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
