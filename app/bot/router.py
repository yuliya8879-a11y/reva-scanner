from __future__ import annotations

from aiogram import Router

from app.bot.handlers import start

main_router = Router(name="main")
main_router.include_router(start.router)
