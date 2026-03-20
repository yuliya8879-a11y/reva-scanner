"""Payment handlers: Telegram Stars invoice flow for full scan purchases."""

from __future__ import annotations

import logging
import os

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import ScanStatus
from app.services.payment_service import PaymentService
from app.services.scan_service import ScanService
from app.services.user_service import UserService

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
    )
