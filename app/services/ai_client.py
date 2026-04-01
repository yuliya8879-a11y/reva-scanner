"""Умный Anthropic клиент с автопереключением между двумя API ключами.

Защита от ситуации: токены закончились — бот не останавливается,
переключается на резервный ключ автоматически.

Управление через бота:
- /api — статус ключей (только для админа)
- Кнопки: Ключ 1 / Ключ 2 / Статус
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# ── Состояние (module-level, живёт всё время работы сервера) ──────────────────

_active_index: int = 0          # 0 = первый ключ, 1 = резервный
_switch_log: list[str] = []     # История переключений (последние 10)
_call_count: int = 0            # Счётчик успешных вызовов
_error_count: int = 0           # Счётчик ошибок

# ── Вспомогательные функции ───────────────────────────────────────────────────

def _all_keys() -> list[str]:
    """Все настроенные ключи в порядке приоритета."""
    return [k for k in [settings.anthropic_api_key, settings.anthropic_api_key_2] if k.strip()]


def _mask_key(key: str) -> str:
    """Показать только первые и последние 4 символа ключа."""
    if len(key) < 12:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def get_status() -> dict[str, Any]:
    """Получить статус API ключей для отображения в боте."""
    keys = _all_keys()
    return {
        "active_key": _active_index + 1,
        "total_keys": len(keys),
        "key_1_set": len(keys) >= 1,
        "key_1_mask": _mask_key(keys[0]) if len(keys) >= 1 else "не задан",
        "key_2_set": len(keys) >= 2,
        "key_2_mask": _mask_key(keys[1]) if len(keys) >= 2 else "не задан",
        "call_count": _call_count,
        "error_count": _error_count,
        "switch_log": _switch_log[-5:],
    }


def set_active_key(index: int) -> bool:
    """Вручную переключить активный ключ (0 или 1). Возвращает True при успехе."""
    global _active_index
    keys = _all_keys()
    if 0 <= index < len(keys):
        _active_index = index
        msg = f"[{datetime.now().strftime('%H:%M')}] Ручное переключение → Ключ {index + 1}"
        _switch_log.append(msg)
        if len(_switch_log) > 10:
            _switch_log.pop(0)
        logger.info(msg)
        return True
    return False


def _is_quota_error(e: Exception) -> bool:
    """Проверить: закончились ли токены/баланс."""
    if isinstance(e, anthropic.AuthenticationError):
        return True
    if isinstance(e, anthropic.PermissionDeniedError):
        return True
    if isinstance(e, anthropic.RateLimitError):
        return True
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", 0) in (402, 429):
        return True
    return False


# ── Основная функция с failover ───────────────────────────────────────────────

async def messages_create(**kwargs: Any) -> anthropic.types.Message:
    """
    Вызвать Claude API с автопереключением на резервный ключ.

    При исчерпании токенов на ключе 1 → автоматически переключается на ключ 2.
    При исчерпании обоих ключей → поднимает APIKeysExhaustedError.
    """
    global _active_index, _call_count, _error_count

    keys = _all_keys()
    if not keys:
        raise RuntimeError("Нет ни одного Anthropic API ключа в настройках")

    last_exc: Exception | None = None

    for attempt_idx in range(_active_index, len(keys)):
        client = anthropic.AsyncAnthropic(api_key=keys[attempt_idx])
        try:
            result = await client.messages.create(**kwargs)
            _active_index = attempt_idx   # запомнить рабочий ключ
            _call_count += 1
            return result

        except Exception as e:
            last_exc = e
            _error_count += 1

            if _is_quota_error(e) and attempt_idx < len(keys) - 1:
                # Переключаемся на следующий ключ
                _active_index = attempt_idx + 1
                msg = (
                    f"[{datetime.now().strftime('%H:%M')}] "
                    f"Ключ {attempt_idx + 1} исчерпан ({type(e).__name__}) "
                    f"→ переключение на Ключ {_active_index + 1}"
                )
                _switch_log.append(msg)
                if len(_switch_log) > 10:
                    _switch_log.pop(0)
                logger.warning(msg)
                continue  # повторить с новым ключом

            raise  # другая ошибка — поднять сразу

    # Оба ключа исчерпаны
    raise APIKeysExhaustedError(
        "Оба API ключа исчерпаны. Пополни баланс на console.anthropic.com"
    ) from last_exc


class APIKeysExhaustedError(Exception):
    """Специальное исключение: все API ключи исчерпаны."""
    pass
