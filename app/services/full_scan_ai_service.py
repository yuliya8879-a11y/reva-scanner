"""AI service for generating full 6-block scan reports via Claude Sonnet."""

from __future__ import annotations

import json
import logging
from datetime import date

import anthropic

from app.config import settings
from app.services.numerology import calculate_soul_number

logger = logging.getLogger(__name__)

BLOCK_KEYS = [
    "архитектура",
    "слепые_зоны",
    "энергетические_блоки",
    "команда",
    "деньги",
    "рекомендации",
]

_SYSTEM_PROMPT = """Ты — AI-сканер бизнеса «Глаз Бога». Проведи глубокий структурированный анализ бизнеса по ответам пользователя.

Ответь СТРОГО в формате JSON — ровно один объект с 6 ключами на русском языке:
{
  "архитектура": "...",
  "слепые_зоны": "...",
  "энергетические_блоки": "...",
  "команда": "...",
  "деньги": "...",
  "рекомендации": "..."
}

Правила для каждого блока:
- "архитектура": структура бизнеса, бизнес-модель, как устроен поток создания ценности
- "слепые_зоны": что owner предпочитает не замечать — конкретные, неудобные наблюдения
- "энергетические_блоки": психологические паттерны owner'а, страхи, ограничивающие убеждения, нумерологический профиль
- "команда": состояние команды или соло-работы, кадровые риски
- "деньги": финансовая архитектура, средний чек, источники, риски, потенциал роста
- "рекомендации": 3-5 конкретных шагов на ближайшие 90 дней

ВАЖНО:
- Тон прямой, на «ты», без комплиментов
- Если по конкретному блоку данных недостаточно — напиши ровно: "недостаточно данных для анализа этого аспекта"
- Не выдумывай факты которых нет в ответах
- Используй числа (число души и жизненного пути) для персонализации блока энергетические_блоки
- Никакого текста вне JSON — только объект
"""


def calculate_life_path_number(birth_date: date) -> int:
    """Calculate life path number from birth date.

    Reduce day, month, and year separately to single digits, then sum and reduce again.

    Example: 15.05.1990
      day: 1+5=6
      month: 0+5=5
      year: 1+9+9+0=19 -> 1+9=10 -> 1+0=1
      sum: 6+5+1=12 -> 1+2=3
    """

    def reduce_to_single(n: int) -> int:
        while n > 9:
            n = sum(int(d) for d in str(n))
        return n if n > 0 else 9

    day_reduced = reduce_to_single(sum(int(d) for d in str(birth_date.day)))
    month_reduced = reduce_to_single(sum(int(d) for d in str(birth_date.month)))
    year_reduced = reduce_to_single(sum(int(d) for d in str(birth_date.year)))
    return reduce_to_single(day_reduced + month_reduced + year_reduced)


class FullScanAIService:
    """Claude Sonnet wrapper for generating full 6-block diagnostic reports."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_full_report(
        self,
        answers: dict,
        birth_date: date,
        scan_type: str,
    ) -> dict:
        """Generate a structured 6-block report via Claude Sonnet.

        Args:
            answers: Dict of questionnaire answers keyed by question key.
            birth_date: User's date of birth for numerology calculations.
            scan_type: "personal" or "business" — determines which answer fields are used.

        Returns:
            Dict with keys: архитектура, слепые_зоны, энергетические_блоки, команда,
            деньги, рекомендации, numerology, token_usage.

        Raises:
            ValueError: If Claude returns a response that cannot be parsed as JSON.
        """
        soul_number = calculate_soul_number(birth_date)
        life_path_number = calculate_life_path_number(birth_date)

        user_prompt = _build_user_prompt(answers, soul_number, life_path_number, scan_type)

        response = await self._client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        usage = response.usage
        logger.info(
            "Full-scan tokens: input=%s, output=%s",
            usage.input_tokens,
            usage.output_tokens,
        )

        raw_text = response.content[0].text
        try:
            blocks = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Claude returned non-JSON for full scan report: {raw_text[:200]}"
            ) from exc

        return {
            **{
                key: blocks.get(key, "недостаточно данных для анализа этого аспекта")
                for key in BLOCK_KEYS
            },
            "numerology": {
                "soul_number": soul_number,
                "life_path_number": life_path_number,
                "birth_date": birth_date.isoformat(),
            },
            "token_usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
        }


def _build_user_prompt(
    answers: dict,
    soul_number: int,
    life_path_number: int,
    scan_type: str,
) -> str:
    """Build the user-facing prompt from questionnaire answers and numerology."""

    def get(key: str) -> str:
        val = answers.get(key, "")
        return val if val else "не указано"

    lines = [
        f"Тип скана: {scan_type}",
        f"Число души: {soul_number}",
        f"Число жизненного пути: {life_path_number}",
        "",
        "Ответы на анкету:",
        f"Дата рождения: {answers.get('birth_date', 'не указано')}",
        f"Имя: {get('name')}",
        f"Сфера: {get('business_area')}",
        f"Возраст бизнеса: {get('business_age')}",
        f"Роль: {get('role')}",
        f"Команда: {get('team_size')}",
        f"Источник клиентов: {get('client_source')}",
        f"Средний чек: {get('avg_check')}",
        f"Главная боль: {get('main_pain')}",
        f"Блокер роста: {get('growth_blocker')}",
    ]

    if scan_type == "personal":
        lines += [
            f"Суперсила: {get('superpower')}",
            f"Стиль решений: {get('decision_style')}",
            f"Цель на год: {get('year_goal')}",
            f"Текущая ситуация: {get('current_situation')}",
        ]
    else:  # business
        lines.append(f"Описание продукта: {get('product_description')}")

    lines.append(f"Соцсеть/сайт: {get('social_url')}")

    return "\n".join(lines)
