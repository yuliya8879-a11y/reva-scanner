"""Умный Anthropic клиент с автопереключением и управлением ключами из бота.

Ключи хранятся в файле api_keys.json — меняются прямо из личного кабинета,
без входа в Railway.

Схема работы:
1. При запуске: загрузить ключи из api_keys.json (если есть) → иначе из .env
2. Ключ 1 закончился → автопереключение на Ключ 2 + уведомление Юлии
3. Оба закончились → уведомление с кнопкой "Вставить новый ключ"
4. Юлия вставляет ключ в боте → сохраняется в api_keys.json → работает мгновенно

Управление в боте:
- /api — статус ключей
- Кнопка "Добавить/заменить ключ" → вставить sk-ant-...
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# Файл для хранения ключей (рядом с проектом, не в git)
_KEYS_FILE = Path(__file__).parent.parent.parent / "api_keys.json"

# ── Runtime-состояние ─────────────────────────────────────────────────────────

_runtime_keys: list[str] = []   # [ключ1, ключ2, ...] — меняется на лету
_active_index: int = 0
_switch_log: list[str] = []
_call_count: int = 0
_error_count: int = 0


def _load_keys() -> None:
    """Загрузить ключи: сначала из файла, потом из .env как fallback."""
    global _runtime_keys, _active_index

    keys: list[str] = []

    # 1. Из сохранённого файла (приоритет — обновляется из бота)
    if _KEYS_FILE.exists():
        try:
            data = json.loads(_KEYS_FILE.read_text())
            keys = [k for k in data.get("keys", []) if k and k.strip()]
            if keys:
                _active_index = data.get("active_index", 0)
                logger.info("API ключи загружены из файла (%d шт.)", len(keys))
        except Exception as e:
            logger.warning("Не удалось прочитать api_keys.json: %s", e)

    # 2. Из .env как fallback
    if not keys:
        for attr in ("anthropic_api_key", "anthropic_api_key_2"):
            val = getattr(settings, attr, "")
            if val and val.strip():
                keys.append(val.strip())
        if keys:
            logger.info("API ключи загружены из .env (%d шт.)", len(keys))

    _runtime_keys = keys
    if _active_index >= len(_runtime_keys):
        _active_index = 0


def _save_keys() -> None:
    """Сохранить текущие ключи в файл."""
    try:
        _KEYS_FILE.write_text(json.dumps({
            "keys": _runtime_keys,
            "active_index": _active_index,
            "updated_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("Не удалось сохранить api_keys.json: %s", e)


# Загрузить ключи при импорте модуля
_load_keys()


# ── Публичный API ─────────────────────────────────────────────────────────────

def add_or_replace_key(slot: int, key: str) -> bool:
    """
    Добавить или заменить ключ в слоте (1 или 2) прямо из бота.
    Сохраняет в файл — работает мгновенно без перезапуска.
    """
    global _runtime_keys
    key = key.strip()
    if not key.startswith("sk-ant-"):
        return False
    idx = slot - 1  # slot 1 → index 0
    while len(_runtime_keys) <= idx:
        _runtime_keys.append("")
    _runtime_keys[idx] = key
    _runtime_keys = [k for k in _runtime_keys if k]  # убрать пустые
    _save_keys()
    msg = f"[{datetime.now().strftime('%H:%M')}] Ключ {slot} обновлён из бота"
    _switch_log.append(msg)
    logger.info(msg)
    return True


def set_active_key(index: int) -> bool:
    """Вручную переключить активный ключ (0 или 1)."""
    global _active_index
    if 0 <= index < len(_runtime_keys):
        _active_index = index
        msg = f"[{datetime.now().strftime('%H:%M')}] Ручное переключение → Ключ {index + 1}"
        _switch_log.append(msg)
        if len(_switch_log) > 10:
            _switch_log.pop(0)
        _save_keys()
        logger.info(msg)
        return True
    return False


def get_status() -> dict[str, Any]:
    """Статус для отображения в /api."""
    keys = _runtime_keys
    return {
        "active_key": _active_index + 1,
        "total_keys": len(keys),
        "key_1_set": len(keys) >= 1 and bool(keys[0]),
        "key_1_mask": _mask(keys[0]) if len(keys) >= 1 else "не задан",
        "key_2_set": len(keys) >= 2 and bool(keys[1]),
        "key_2_mask": _mask(keys[1]) if len(keys) >= 2 else "не задан",
        "call_count": _call_count,
        "error_count": _error_count,
        "switch_log": _switch_log[-5:],
        "keys_file": str(_KEYS_FILE),
    }


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _mask(key: str) -> str:
    if len(key) < 12:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def _is_quota_error(e: Exception) -> bool:
    if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.RateLimitError)):
        return True
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", 0) in (402, 429):
        return True
    return False


def _notify_admin(text: str) -> None:
    """Отправить сообщение Юлии через Telegram без aiogram."""
    try:
        token = settings.telegram_bot_token
        admin_id = settings.admin_telegram_id
        if not token or not admin_id:
            return
        payload = json.dumps({"chat_id": admin_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ── Основная функция с failover ───────────────────────────────────────────────

async def messages_create(**kwargs: Any) -> anthropic.types.Message:
    """
    Вызвать Claude API с автопереключением на резервный ключ.
    Если ключи закончились — Юлья получит уведомление в бот с инструкцией.
    """
    global _active_index, _call_count, _error_count

    if not _runtime_keys:
        raise RuntimeError("Нет ни одного Anthropic API ключа")

    last_exc: Exception | None = None

    for attempt_idx in range(_active_index, len(_runtime_keys)):
        key = _runtime_keys[attempt_idx]
        if not key:
            continue
        client = anthropic.AsyncAnthropic(api_key=key)
        try:
            result = await client.messages.create(**kwargs)
            _active_index = attempt_idx
            _call_count += 1
            return result

        except Exception as e:
            last_exc = e
            _error_count += 1

            if _is_quota_error(e) and attempt_idx < len(_runtime_keys) - 1:
                _active_index = attempt_idx + 1
                msg = (
                    f"[{datetime.now().strftime('%H:%M')}] "
                    f"Ключ {attempt_idx + 1} исчерпан → Ключ {_active_index + 1}"
                )
                _switch_log.append(msg)
                if len(_switch_log) > 10:
                    _switch_log.pop(0)
                logger.warning(msg)
                _notify_admin(
                    f"⚠️ <b>Ключ {attempt_idx + 1} исчерпан</b>\n"
                    f"Переключилась на Ключ {_active_index + 1}. Бот работает.\n\n"
                    f"Пополни баланс: console.anthropic.com → Billing"
                )
                continue

            raise

    # Все ключи исчерпаны
    _notify_admin(
        "🚨 <b>Все API ключи исчерпаны!</b>\n\n"
        "Бот не может генерировать разборы.\n\n"
        "Открой личный кабинет в боте:\n"
        "/start → 🗄 Мой кабинет → 🔑 Добавить ключ\n\n"
        "Вставь новый ключ sk-ant-... из console.anthropic.com"
    )
    raise APIKeysExhaustedError(
        "Все API ключи исчерпаны. Добавь новый через /start → Кабинет → 🔑 Ключ"
    ) from last_exc


class APIKeysExhaustedError(Exception):
    pass
