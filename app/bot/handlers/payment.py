"""Payment handlers: Telegram Stars invoice flow for full scan purchases."""

from __future__ import annotations

import logging
import os
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from app.config import settings
from app.models.scan import ScanStatus
from app.services.full_scan_ai_service import BLOCK_KEYS, FullScanAIService
from app.services.payment_service import PaymentService
from app.services.scan_service import ScanService
from app.services.user_service import UserService

_BLOCK_LABELS = {
    "архитектура": "👤 Состояние владельца",
    "слепые_зоны": "🔍 Поломка — что мешает",
    "энергетические_блоки": "🌀 Глубина — родовое и скрытое",
    "команда": "🛠 Инструменты и команда",
    "деньги": "💰 Деньги",
    "рекомендации": "🎯 Вектор и послание",
}


async def _admin_generate_report(
    bot: Bot,
    chat_id: int,
    scan_id: int,
    scan_type: str,
    user_name: str,
    session: AsyncSession,
) -> None:
    """Тестовая генерация для админа — полный 6-блочный разбор без опросника."""
    scanning_msg = await bot.send_message(
        chat_id,
        "🔓 Тестовый доступ активирован.\n🔮 Генерирую полный разбор... Это займёт около 30 секунд."
    )
    try:
        # Берём реальную дату рождения из профиля если есть, иначе заглушка
        from app.models.user import User as UserModel
        from sqlalchemy import select as sa_select
        from app.models.scan import Scan as ScanModel
        scan_row = await session.get(ScanModel, scan_id)
        real_user = await session.get(UserModel, scan_row.user_id) if scan_row else None
        birth_date = real_user.birth_date if (real_user and real_user.birth_date) else date(1990, 1, 1)
        birth_date_note = "" if (real_user and real_user.birth_date) else "\n_(дата рождения не задана — установи через /setbirthdate или пройди полную анкету)_"

        answers = {
            "name": user_name,
            "birth_date": birth_date.isoformat(),
        }

        ai_service = FullScanAIService()
        report = await ai_service.generate_full_report(answers, birth_date, scan_type)

        scan_service = ScanService(session)
        await scan_service.update_answers(scan_id, answers)
        token_usage = report.get("token_usage", {})
        await scan_service.complete_full_scan(scan_id, report, token_usage)

        await scanning_msg.delete()

        # Нумерология
        num = report.get("numerology", {})
        await bot.send_message(
            chat_id,
            f"*🔢 Нумерология*\nЧисло души: {num.get('soul_number', '—')}\n"
            f"Число жизненного пути: {num.get('life_path_number', '—')}"
            f"{birth_date_note}",
            parse_mode="Markdown",
        )

        # 6 блоков — каждый отдельным сообщением
        for key in BLOCK_KEYS:
            label = _BLOCK_LABELS[key]
            content = report.get(key, "недостаточно данных для анализа этого аспекта")
            await bot.send_message(
                chat_id,
                f"*{label}*\n\n{content}",
                parse_mode="Markdown",
            )

        # Soft closing
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
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

    except Exception:
        logger.exception("Admin test report failed for scan_id=%s", scan_id)
        try:
            await scanning_msg.delete()
        except Exception:
            pass
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        await bot.send_message(
            chat_id,
            "Ошибка при генерации разбора.\n\nНажми «Перезапустить бота» и попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
            ]),
        )

logger = logging.getLogger(__name__)

router = Router(name="payment")

STARS_PRICE_PERSONAL = int(os.getenv("STARS_PRICE", "75"))
STARS_PRICE_BUSINESS = STARS_PRICE_PERSONAL * 2  # 150 by default


# ---------------------------------------------------------------------------
# Handler 1: buy:personal / buy:business callback — create scan, send invoice
# ---------------------------------------------------------------------------


@router.callback_query(lambda c: c.data in ("buy:personal", "buy:business"))
async def handle_buy_callback(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Intercept buy callbacks from upsell, create Payment row, send Stars invoice."""
    scan_type = callback.data.split(":")[1]  # "personal" or "business"
    stars = STARS_PRICE_PERSONAL if scan_type == "personal" else STARS_PRICE_BUSINESS

    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    scan_service = ScanService(session)
    existing = await scan_service.get_incomplete_scan(user.id)

    if existing is not None:
        if existing.scan_type == scan_type:
            scan = existing
        else:
            # Different scan type — cancel old, start fresh
            existing.status = ScanStatus.failed.value
            await session.commit()
            scan = await scan_service.create_full_scan(user.id, scan_type)
    else:
        scan = await scan_service.create_full_scan(user.id, scan_type)

    payment_service = PaymentService(session)
    await payment_service.create_payment(
        user_id=user.id,
        scan_id=scan.id,
        amount_stars=stars,
        product_type=scan_type,
    )

    # Тестовый режим для админа — пропускаем оплату и опросник
    is_admin = settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id
    if is_admin:
        await payment_service.confirm_payment(
            telegram_charge_id="test_free_access",
            scan_id=scan.id,
        )
        await callback.answer()
        await _admin_generate_report(
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
            scan_id=scan.id,
            scan_type=scan_type,
            user_name=callback.from_user.first_name or callback.from_user.full_name or "",
            session=session,
        )
        return

    await callback.message.answer("Сейчас выставим счёт...")
    await callback.message.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Полный скан бизнеса" if scan_type == "business" else "Полный скан",
        description="Персональный разбор 6 блоков: архитектура, слепые зоны, деньги и другие",
        payload=f"scan:{scan.id}:user:{user.id}",
        provider_token="",  # empty string required for Telegram Stars (XTR)
        currency="XTR",
        prices=[LabeledPrice(label="Полный скан", amount=stars)],
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Handler 2: pre_checkout_query — must answer within 10 seconds, no DB work
# ---------------------------------------------------------------------------


@router.pre_checkout_query()
async def handle_pre_checkout_query(query: PreCheckoutQuery) -> None:
    """Answer pre-checkout query immediately. No database work allowed here."""
    await query.answer(ok=True)


# ---------------------------------------------------------------------------
# Handler 3: successful_payment — confirm payment, guard on is_paid, start scan
# ---------------------------------------------------------------------------


@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Process confirmed Telegram Stars payment and launch the full scan questionnaire."""
    charge_id = message.successful_payment.telegram_payment_charge_id
    payload = message.successful_payment.invoice_payload  # "scan:{scan_id}:user:{user_id}"

    parts = payload.split(":")
    # payload format: scan:{scan_id}:user:{user_id}
    scan_id = int(parts[1])

    payment_service = PaymentService(session)
    try:
        await payment_service.confirm_payment(
            telegram_charge_id=charge_id,
            scan_id=scan_id,
        )
    except Exception:
        logger.exception(
            "confirm_payment failed for scan_id=%s charge_id=%s", scan_id, charge_id
        )
        await message.answer("Ошибка обработки оплаты. Пожалуйста, обратитесь в поддержку.")
        return

    scan_service = ScanService(session)
    scan = await scan_service.get_scan(scan_id)
    if scan is None or not scan.is_paid:
        logger.error("Scan not marked paid after confirm for scan_id=%s", scan_id)
        await message.answer("Ошибка: скан не найден. Обратитесь в поддержку.")
        return

    await message.answer("Оплата получена! Запускаем скан.")

    # Deferred import to avoid circular dependency at module load time
    from app.bot.handlers.full_scan import start_questionnaire_after_payment

    await start_questionnaire_after_payment(
        bot=message.bot,
        chat_id=message.chat.id,
        scan_id=scan_id,
        scan_type=scan.scan_type,
        state=state,
        session=session,
        telegram_first_name=message.from_user.first_name or "",
    )
