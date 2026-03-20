"""AI service for generating mini-scan teaser reports via Claude Haiku."""

from __future__ import annotations

import logging
from typing import Optional

import anthropic

from app.config import settings
from app.services.numerology import calculate_soul_number  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Ты — AI-сканер бизнеса «Глаз Бога». Твоя задача — на основе ответов пользователя назвать ОДНУ конкретную, "
    "неудобную правду о его бизнесе. Не дай общий совет — укажи на конкретную болевую точку, которую он "
    "предпочитает не замечать.\n\n"
    "Правила:\n"
    "- Ответ: 3-4 предложения, прямой тон, на «ты»\n"
    "- Если данных недостаточно для точного вывода — прямо скажи «недостаточно данных для точного анализа "
    "этого аспекта»\n"
    "- Используй число души пользователя для персонализации (но не упоминай нумерологию явно)\n"
    "- Будь конкретным и резким — пользователь пришёл за правдой, не за комплиментами"
)

_USER_PROMPT_TEMPLATE = (
    "Число души: {soul_number}\n"
    "Сфера бизнеса: {business_area}\n"
    "Возраст бизнеса: {business_age}\n"
    "Главная боль: {main_pain}\n"
    "Описание ситуации: {situation}"
)


class AIService:
    """Wrapper around Anthropic Claude API for mini-scan teaser generation."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_mini_report(
        self,
        answers: dict,
        soul_number: int,
    ) -> tuple[str, dict]:
        """Generate a mini-scan teaser report.

        Args:
            answers: Dict with keys: business_area, business_age, main_pain, situation (optional).
            soul_number: Numerology soul number (1-9).

        Returns:
            Tuple of (report_text, usage_dict) where usage_dict has input_tokens and output_tokens.
        """
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            soul_number=soul_number,
            business_area=answers.get("business_area", "не указано"),
            business_age=answers.get("business_age", "не указано"),
            main_pain=answers.get("main_pain", "не указано"),
            situation=answers.get("situation", "не указано"),
        )

        response = await self._client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        usage = response.usage
        logger.info(
            "Mini-scan tokens: input=%s, output=%s",
            usage.input_tokens,
            usage.output_tokens,
        )

        report_text = response.content[0].text
        usage_dict = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
        return report_text, usage_dict
