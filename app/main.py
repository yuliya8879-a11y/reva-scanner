from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.router import main_router
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
