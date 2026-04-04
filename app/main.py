from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.router import main_router
from app.bot.tasks import run_follow_up_loop, run_monitor_loop
from app.config import settings
from app.database import get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Bot & Dispatcher setup ---
bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp.include_router(main_router)


# --- FastAPI app ---
app = FastAPI(title="Глаз Бога", docs_url=None, redoc_url=None)


@app.on_event("startup")
async def on_startup() -> None:
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != settings.webhook_url:
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=True,
        )
        logger.info("Webhook set: %s", settings.webhook_url)
    else:
        logger.info("Webhook already set: %s", settings.webhook_url)

    # Start background tasks
    asyncio.create_task(run_follow_up_loop(bot))
    asyncio.create_task(run_monitor_loop(bot))
    logger.info("Background tasks scheduled: follow-up + monitor")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await bot.session.close()


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    body = await request.json()
    update = Update.model_validate(body)

    # Pass DB session into handlers via middleware data
    await dp.feed_update(bot, update, session=session)
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook/yookassa")
async def yookassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Вебхук от ЮKassa — обработка успешного платежа."""
    from app.services.yookassa_service import parse_webhook
    from app.services.scan_service import ScanService
    from app.services.payment_service import PaymentService
    from app.services.user_service import UserService
    from app.bot.handlers.full_scan import start_questionnaire_after_payment
    from datetime import datetime, timezone, timedelta

    body = await request.json()
    logger.info("ЮKassa вебхук: %s", body.get("event"))

    data = parse_webhook(body)
    if not data or not data.get("paid"):
        return {"ok": True}

    tg_id = data["telegram_user_id"]
    scan_id = data["scan_id"]
    scan_type = data["scan_type"]

    if not tg_id or not scan_id:
        return {"ok": True}

    # Подтвердить оплату в БД
    payment_service = PaymentService(session)
    await payment_service.confirm_payment(
        telegram_charge_id=data["payment_id"],
        scan_id=scan_id,
    )

    # Выдать подписку на 30 дней
    user_service = UserService(session)
    from sqlalchemy import select as sa_select
    from app.models.user import User
    result = await session.execute(sa_select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        now = datetime.now(timezone.utc)
        user.subscription_until = now + timedelta(days=30)
        await session.commit()

    # Отправить пользователю кнопку "Начать разбор"
    type_label_user = {"mini": "мини-скан", "personal": "личный разбор", "business": "бизнес-разбор"}.get(scan_type, scan_type)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    await bot.send_message(
        tg_id,
        f"✅ <b>Оплата получена!</b>\n\n"
        f"Всё готово — нажми кнопку ниже чтобы начать {type_label_user}.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="▶️ Начать разбор", callback_data=f"resume_scan:{scan_id}")
        ]]),
    )

    # Уведомить Юлию
    if settings.admin_telegram_id:
        type_label = {"mini": "Мини-скан", "personal": "Личный разбор", "business": "Бизнес-разбор"}.get(scan_type, scan_type)
        await bot.send_message(
            settings.admin_telegram_id,
            f"✅ <b>Оплата через ЮKassa</b>\n\n"
            f"👤 tg_id: {tg_id}\n"
            f"📦 {type_label} — {data.get('amount')} ₽\n"
            f"🔗 Payment: {data['payment_id']}",
            parse_mode="HTML",
        )

    return {"ok": True}
