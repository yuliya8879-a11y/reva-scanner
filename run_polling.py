"""Запуск бота в режиме polling (без сервера, для локального тестирования)."""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.router import main_router
from app.config import settings
from app.database import Base, async_session_factory, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            return await handler(event, data)


async def main() -> None:
    # Создаём таблицы если не существуют
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(main_router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен в режиме polling — @Eye888888_bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
