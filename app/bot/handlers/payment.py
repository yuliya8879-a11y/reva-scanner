"""Payment handlers: Telegram Stars invoice flow for full scan purchases."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, PreCheckoutQuery
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

STARS_PRICE_PERSONAL = int(os.getenv("STARS_PRICE_PERSONAL", "3500"))
STARS_PRICE_BUSINESS = int(os.getenv("STARS_PRICE_BUSINESS", "7000"))

# Оплата временно приостановлена — True пока не подключён банк
PAYMENT_PAUSED = os.getenv("PAYMENT_PAUSED", "true").lower() == "true"


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

    # Проверка активной подписки — пропускаем оплату
    has_subscription = (
        user.subscription_until is not None
        and user.subscription_until > datetime.now(timezone.utc)
    )

    scan_service = ScanService(session)
    existing = await scan_service.get_incomplete_scan(user.id)

    if existing is not None:
        if existing.scan_type == scan_type:
            scan = existing
        else:
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

    # Подписка / админ — подтверждаем без оплаты, но ведём через опросник (нужен запрос!)
    is_admin = settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id
    if is_admin or has_subscription:
        await payment_service.confirm_payment(
            telegram_charge_id="free_access",
            scan_id=scan.id,
        )
        await callback.answer()
        # Импорт здесь — избегаем циклической зависимости
        from app.bot.handlers.full_scan import start_questionnaire_after_payment
        await start_questionnaire_after_payment(
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
            scan_id=scan.id,
            scan_type=scan_type,
            state=state,
            session=session,
            telegram_first_name=callback.from_user.first_name or callback.from_user.full_name or "",
        )
        return

    # Новый флоу: уведомить Юлию — пользователь хочет оплатить
    price_label = "3 500 ₽" if scan_type == "personal" else "10 000 ₽"
    type_label = "личный разбор" if scan_type == "personal" else "бизнес-разбор"
    user_name = callback.from_user.full_name or callback.from_user.first_name or "—"
    user_at = f"@{callback.from_user.username}" if callback.from_user.username else f"id:{callback.from_user.id}"

    if settings.admin_telegram_id:
        await callback.message.bot.send_message(
            settings.admin_telegram_id,
            f"💳 <b>Новая заявка на оплату</b>\n\n"
            f"👤 {user_name}  |  {user_at}\n"
            f"📦 {type_label.capitalize()} — {price_label}\n\n"
            f"<code>/grant {callback.from_user.id} {scan_type}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ Выдать доступ ({price_label})",
                    callback_data=f"quick_grant:{callback.from_user.id}:{scan_type}"
                )],
                [InlineKeyboardButton(
                    text="💬 Написать пользователю",
                    url=f"tg://user?id={callback.from_user.id}"
                )],
            ]),
        )

    await callback.answer()
    await callback.message.answer(
        f"✅ <b>Заявка принята!</b>\n\n"
        f"Юлия получила уведомление и свяжется с вами для оплаты.\n\n"
        f"После подтверждения оплаты вам откроется доступ к <b>{type_label}у</b>.\n\n"
        f"Если хотите ускорить — напишите напрямую:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")
        ]]),
    )


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
