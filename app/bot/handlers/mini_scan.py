"""Mini-scan FSM: объяснение → согласие → отчёт. Без вопросов."""

from __future__ import annotations

import logging

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
from app.services.event_service import log_event
from app.services.scan_service import ScanService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router(name="mini_scan")

# Кнопки после результата
def _post_scan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 Подписаться на канал", url="https://t.me/Reva_mentor")],
            [InlineKeyboardButton(text="💎 Личная консультация", url="https://t.me/Reva_Yulya6")],
            [InlineKeyboardButton(text="🔮 Хочу полный разбор 3500⭐", callback_data="buy:personal")],
            [InlineKeyboardButton(text="💼 Бизнес-разбор 7000⭐", callback_data="buy:business")],
        ]
    )

def _support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
            [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
        ]
    )


# ---------------------------------------------------------------------------
# Вход — кнопка "Бесплатный мини-скан"
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
    user_name = callback.from_user.first_name or callback.from_user.full_name or "друг"

    await state.update_data(
        scan_id=scan.id,
        user_id=user.id,
        user_name=user_name,
    )
    await state.set_state(MiniScanStates.consent)
    await log_event(session, callback.from_user, "mini_scan_start", bot=callback.message.bot)

    consent_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Согласна / Согласен", callback_data="consent:yes")],
            [InlineKeyboardButton(text="❌ Не сейчас", callback_data="consent:no")],
        ]
    )

    await callback.message.answer(
        f"👁 <b>Добрый день, {user_name}.</b>\n\n"
        "Вы заходите в формат глубокого сканирования.\n\n"
        "Я работаю не поверхностно:\n"
        "— выявляю корневую причину\n"
        "— нахожу системную ошибку\n"
        "— даю конкретный вектор действий\n\n"
        "Сканирование охватывает:\n"
        "• Ваше состояние и природу (на своём ли месте)\n"
        "• Деньги — где они и куда уходят\n"
        "• Главный блок, который мешает расти\n"
        "• Инструменты, которые вы не используете\n"
        "• Один шаг — что сделать прямо сейчас\n\n"
        "Это бесплатный первый разбор.\n"
        "Следующий — уже платный и значительно глубже.\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "Разрешаете провести сканирование?",
        parse_mode="HTML",
        reply_markup=consent_keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data in ("scan_type:personal", "scan_type:business"))
async def handle_scan_type_paid(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    from app.config import settings
    from app.models.scan import ScanStatus
    from app.bot.handlers.payment import _admin_generate_report

    is_admin = (
        settings.admin_telegram_id
        and callback.from_user.id == settings.admin_telegram_id
    )
    if is_admin:
        # Сбрасываем любое активное FSM-состояние
        await state.clear()

        scan_type = callback.data.split(":")[1]

        # Убираем кнопки с сообщения — защита от двойного нажатия
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.answer()

        user_service = UserService(session)
        user, _ = await user_service.get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )

        # Сохраняем дату рождения если спрашивали раньше и знаем
        # (для корректной нумерологии в будущих сканах)

        scan_service = ScanService(session)
        # Закрываем все незавершённые сканы
        existing = await scan_service.get_incomplete_scan(user.id)
        if existing is not None:
            existing.status = ScanStatus.failed.value
            await session.commit()
        scan = await scan_service.create_full_scan(user.id, scan_type)
        user_name = callback.from_user.first_name or callback.from_user.full_name or ""
        await _admin_generate_report(
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
            scan_id=scan.id,
            scan_type=scan_type,
            user_name=user_name,
            session=session,
        )
        return

    await callback.message.answer(
        "Для платного сканирования сначала пройдите бесплатный мини-скан.\n\n"
        "Нажмите «Бесплатный мини-скан» ниже."
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Согласие
# ---------------------------------------------------------------------------

@router.callback_query(MiniScanStates.consent, lambda c: c.data == "consent:yes")
async def handle_consent_yes(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await callback.answer()

    # Check if we already have birth_date for this user
    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    await log_event(session, callback.from_user, "mini_consent_yes")
    if user.birth_date:
        # Already know the date — skip to request question
        await state.update_data(birth_date=user.birth_date)
        await state.set_state(MiniScanStates.asking_request)
        await callback.message.answer(
            "С чем ты сейчас? Опиши коротко свою ситуацию или запрос.\n\n"
            "<i>Например: устала, деньги не идут — или — хочу понять куда двигаться дальше</i>",
            parse_mode="HTML",
        )
    else:
        await state.set_state(MiniScanStates.asking_birth_date)
        await callback.message.answer(
            "Напиши свою дату рождения.\n\n"
            "<b>Формат: ДД.ММ.ГГГГ</b>\n"
            "<i>Например: 15.03.1990</i>",
            parse_mode="HTML",
        )


@router.message(MiniScanStates.asking_birth_date)
async def handle_mini_birth_date(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    import re
    text = (message.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await message.answer(
            "Пожалуйста, введи дату в формате ДД.ММ.ГГГГ\n"
            "<i>Например: 15.03.1990</i>",
            parse_mode="HTML",
        )
        return

    # Save to user profile
    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    user.birth_date = text
    await session.commit()

    await log_event(session, message.from_user, "mini_date_entered", detail=text)
    await state.update_data(birth_date=text)
    await state.set_state(MiniScanStates.asking_request)
    await message.answer(
        "С чем ты сейчас? Опиши коротко свою ситуацию или запрос.\n\n"
        "<i>Например: устала, деньги не идут — или — хочу понять куда двигаться дальше</i>",
        parse_mode="HTML",
    )


@router.message(MiniScanStates.asking_request)
async def handle_mini_request(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    await log_event(session, message.from_user, "mini_request_entered", detail=text[:100])
    await state.update_data(mini_request=text)
    await _generate_and_send_report(message, state, session, message.from_user.id)


@router.callback_query(MiniScanStates.consent, lambda c: c.data == "consent:no")
async def handle_consent_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer(
        "Хорошо. Когда будете готовы — напишите /start",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Генерация отчёта
# ---------------------------------------------------------------------------

async def _generate_and_send_report(
    message_obj: Message,
    state: FSMContext,
    session: AsyncSession,
    telegram_id: int,
) -> None:
    data = await state.get_data()
    scan_id: int = data["scan_id"]
    user_name: str = data.get("user_name", "")
    user_id: int = data.get("user_id")
    birth_date: str = data.get("birth_date", "")
    mini_request: str = data.get("mini_request", "")

    bot = message_obj.bot
    chat_id = message_obj.chat.id

    scanning_msg = await bot.send_message(
        chat_id,
        "🔮 Настраиваюсь на ваше поле...\n\nСделайте три глубоких вдоха.",
    )

    try:
        scan_service = ScanService(session)
        answers = {"user_name": user_name, "birth_date": birth_date, "request": mini_request}
        await scan_service.update_answers(scan_id, answers)

        ai_service = AIService()
        is_first_scan = not await scan_service.has_completed_scan(user_id)

        if is_first_scan:
            report_text, token_usage = await ai_service.generate_full_free_report(
                answers, soul_number=None
            )
        else:
            report_text, token_usage = await ai_service.generate_mini_report(
                answers, soul_number=None
            )

        await scan_service.complete_mini_scan(
            scan_id, report_text, {}, token_usage,
        )
        await log_event(session, message_obj.from_user, "mini_scan_done", bot=bot)
        await scanning_msg.delete()

        await bot.send_message(
            chat_id,
            f"👁 <b>Твой разбор, {user_name}</b>\n\n{report_text}",
            parse_mode="HTML",
        )

        if is_first_scan:
            await bot.send_message(
                chat_id,
                "Это был твой первый бесплатный разбор.\n\n"
                "Следующий — платный. Значительно глубже: 6 полных блоков,\n"
                "чакры, системы, родовые программы и практика на выход.",
                reply_markup=_post_scan_keyboard(),
            )
        else:
            await bot.send_message(
                chat_id,
                "Для полного разбора — выбери формат ниже.",
                reply_markup=_post_scan_keyboard(),
            )

        # Soft closing — gentle continuation offer
        await bot.send_message(
            chat_id,
            "Если что-то из разбора откликнулось — напиши мне.\n"
            "Я здесь.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔮 Хочу личную сессию с Юлией", callback_data="request_session")],
                    [InlineKeyboardButton(text="⭐ Поделиться впечатлением", url="https://t.me/Reva_mentor")],
                ]
            ),
        )

    except Exception:
        logger.exception("Error generating mini-scan report for scan_id=%s", scan_id)
        await log_event(session, message_obj.from_user, "scan_error", detail="mini_scan", bot=bot)
        try:
            await scanning_msg.delete()
        except Exception:
            pass
        await bot.send_message(
            chat_id,
            "Произошла ошибка при сканировании.\n"
            "Напишите напрямую — разберём вместе.",
            reply_markup=_support_keyboard(),
        )
    finally:
        await state.clear()
