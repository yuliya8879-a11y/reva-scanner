from __future__ import annotations

from aiogram import Router

from app.bot.handlers import admin, full_scan, mini_scan, payment, session, start

main_router = Router(name="main")
main_router.include_router(admin.router)     # admin first — /stats, /broadcast
main_router.include_router(start.router)
main_router.include_router(mini_scan.router)
main_router.include_router(payment.router)   # payment router before full_scan for buy:* callbacks
main_router.include_router(full_scan.router)
main_router.include_router(session.router)
