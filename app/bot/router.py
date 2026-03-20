from __future__ import annotations

from aiogram import Router

from app.bot.handlers import full_scan, mini_scan, start

main_router = Router(name="main")
main_router.include_router(start.router)
main_router.include_router(mini_scan.router)
main_router.include_router(full_scan.router)
