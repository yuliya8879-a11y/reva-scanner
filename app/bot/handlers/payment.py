"""Payment handlers: единственный метод оплаты — ЮKassa."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from app.config import settings
from app.models.scan import ScanStatus
from app.services.full_scan_ai_service import BLOCK_KEYS, FullScanAIService
from app.services.payment_service import PaymentService
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
        from app.models.user import User as UserModel
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

        num = report.get("numerology", {})
        await bot.send_message(
            chat_id,
            f"*🔢 Нумерология*\nЧисло души: {num.get('soul_number', '—')}\n"
            f"Число жизненного пути: {num.get('life_path_number', '—')}"
            f"{birth_date_note}",
            parse_mode="Markdown",
        )

        for key in BLOCK_KEYS:
            label = _BLOCK_LABELS[key]
            content = report.get(key, "недостаточно данных для анализа этого аспекта")
            await bot.send_message(
                chat_id,
                f"*{label}*\n\n{content}",
                parse_mode="Markdown",
            )

        await bot.send_message(
            chat_id,
            "Это твой разбор.\n\nПусть осядет.\n\nЕсли что-то отозвалось — или хочешь разобрать глубже — "
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
        await bot.send_message(
            chat_id,
            "Ошибка при генерации разбора.\n\nНажми «Перезапустить бота» и попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезапустить бота", callback_data="restart_bot")],
            ]),
        )


router = Router(name="payment")


# ---------------------------------------------------------------------------
# buy:personal / buy:business — создать скан и выслать ссылку ЮKassa
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data in ("buy:personal", "buy:business"))
async def handle_buy_callback(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Создать скан и выслать ссылку на оплату через ЮKassa."""
    scan_type = callback.data.split(":")[1]  # "personal" or "business"

    user_service = UserService(session)
    user, _ = await user_service.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    # Активная подписка или админ — пропускаем оплату
    has_subscription = (
        user.subscription_until is not None
        and user.subscription_until > datetime.now(timezone.utc)
    )
    is_admin = settings.admin_telegram_id and callback.from_user.id == settings.admin_telegram_id

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
        amount_stars=0,
        product_type=scan_type,
    )

    # Бесплатный доступ для админа / подписчика
    if is_admin or has_subscription:
        await payment_service.confirm_payment(
            telegram_charge_id="free_access",
            scan_id=scan.id,
        )
        await callback.answer()
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

    # ── ЮKassa — единственный метод оплаты ──────────────────────────
    price_label = "3 500 ₽" if scan_type == "personal" else "10 000 ₽"
    type_label = "личный разбор" if scan_type == "personal" else "бизнес-разбор"
    user_name = callback.from_user.full_name or callback.from_user.first_name or "—"
    user_at = f"@{callback.from_user.username}" if callback.from_user.username else f"id:{callback.from_user.id}"

    from app.services.yookassa_service import create_payment
    try:
        payment = create_payment(
            scan_type=scan_type,
            telegram_user_id=callback.from_user.id,
            scan_id=scan.id,
        )
        await callback.answer()
        await callback.message.answer(
            f"💳 <b>Оплата — {type_label} — {price_label}</b>\n\n"
            f"Нажми кнопку ниже — откроется страница оплаты.\n"
            f"После оплаты разбор запустится автоматически.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить {price_label}",
                    url=payment["confirmation_url"]
                )],
                [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
            ]),
        )
        if settings.admin_telegram_id:
            await callback.message.bot.send_message(
                settings.admin_telegram_id,
                f"💳 <b>Новый платёж (ЮKassa)</b>\n\n"
                f"👤 {user_name}  |  {user_at}\n"
                f"📦 {type_label.capitalize()} — {price_label}\n"
                f"🔗 Payment ID: <code>{payment['payment_id']}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("ЮKassa ошибка для scan_id=%s: %s", scan.id, e)
        await callback.answer()
        await callback.message.answer(
            "⚠️ Платёжная система временно недоступна.\n\n"
            "Напишите Юлии — она поможет оформить вручную:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать Юлии", url="https://t.me/Reva_Yulya6")],
            ]),
        )
        if settings.admin_telegram_id:
            await callback.message.bot.send_message(
                settings.admin_telegram_id,
                f"❗ <b>Ошибка ЮKassa</b>\n\n"
                f"👤 {user_name}  |  {user_at}\n"
                f"📦 {type_label.capitalize()} — {price_label}\n"
                f"Ошибка: {e}\n\n"
                f"Выдать вручную:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"✅ Выдать доступ ({price_label})",
                        callback_data=f"quick_grant:{callback.from_user.id}:{scan_type}"
                    )],
                ]),
            )
