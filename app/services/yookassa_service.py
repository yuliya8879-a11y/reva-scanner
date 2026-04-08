"""ЮKassa — создание платежей и проверка статуса.

Тестовый режим: YOOKASSA_TEST_MODE=true
Боевой режим: YOOKASSA_TEST_MODE=false

Документация: https://yookassa.ru/developers/api
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Цены в рублях
PRICES = {
    "mini": 590,
    "personal": 3500,
    "business": 10000,
}

DESCRIPTIONS = {
    "mini": "Мини-скан «Глаз Бога»",
    "personal": "Личный разбор «Глаз Бога»",
    "business": "Бизнес-разбор «Глаз Бога»",
}


def _get_configuration() -> Any:
    """Инициализировать ЮKassa с текущими ключами."""
    import yookassa
    from yookassa import Configuration

    Configuration.configure(
        account_id=settings.yookassa_shop_id,
        secret_key=settings.yookassa_secret_key,
    )
    return Configuration


def is_configured() -> bool:
    """Проверить что ключи ЮKassa заданы."""
    return bool(settings.yookassa_shop_id and settings.yookassa_secret_key
                and settings.yookassa_shop_id != "ВСТАВЬ_SHOP_ID")


def create_payment(
    scan_type: str,
    telegram_user_id: int,
    scan_id: int,
    return_url: str = "https://t.me/Eye888888_bot",
    amount: int | None = None,
) -> dict:
    """
    Создать платёж в ЮKassa.

    amount — переопределяет стандартную цену (для скидок).
    Возвращает: {"payment_id": str, "confirmation_url": str, "status": str}
    """
    if not is_configured():
        raise RuntimeError("ЮKassa не настроена. Добавь YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env")

    _get_configuration()
    from yookassa import Payment

    amount = amount if amount is not None else PRICES.get(scan_type, 3500)
    description = DESCRIPTIONS.get(scan_type, "Разбор «Глаз Бога»")
    idempotence_key = str(uuid.uuid4())

    payment = Payment.create({
        "amount": {
            "value": f"{amount}.00",
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "description": description,
        "metadata": {
            "telegram_user_id": str(telegram_user_id),
            "scan_id": str(scan_id),
            "scan_type": scan_type,
        },
        "capture": True,
    }, idempotence_key)

    logger.info(
        "ЮKassa платёж создан: id=%s scan_type=%s amount=%s",
        payment.id, scan_type, amount
    )

    return {
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
        "status": payment.status,
        "amount": amount,
    }


def get_payment_status(payment_id: str) -> dict:
    """Проверить статус платежа."""
    if not is_configured():
        raise RuntimeError("ЮKassa не настроена")

    _get_configuration()
    from yookassa import Payment

    payment = Payment.find_one(payment_id)
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "paid": payment.paid,
        "amount": payment.amount.value,
        "metadata": payment.metadata or {},
    }


def parse_webhook(body: dict) -> dict | None:
    """
    Разобрать вебхук от ЮKassa.
    Возвращает словарь если платёж успешен, иначе None.
    """
    event = body.get("event", "")
    if event != "payment.succeeded":
        return None

    obj = body.get("object", {})
    metadata = obj.get("metadata", {})

    return {
        "payment_id": obj.get("id"),
        "status": obj.get("status"),
        "paid": obj.get("paid", False),
        "amount": obj.get("amount", {}).get("value"),
        "telegram_user_id": int(metadata.get("telegram_user_id", 0)),
        "scan_id": int(metadata.get("scan_id", 0)),
        "scan_type": metadata.get("scan_type", ""),
    }
