"""
Агент аналитики контента.
Анализирует что работает в нише и даёт рекомендации.

Запуск:
  python3 analytics_bot.py week        — что писать на неделю
  python3 analytics_bot.py best        — лучшие форматы для ниши
  python3 analytics_bot.py hook "тема" — 5 вариантов крючка
"""
import asyncio
import sys
import os
from anthropic import AsyncAnthropic
from config import config

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", config.anthropic_api_key))

SYSTEM = f"""Ты — стратег контента для бренда «{config.brand_name}».
Ниша: {config.niche}.
Аудитория: {config.target_audience}.
Цель: рост охватов, доверие, продажи @Eye888888_bot."""


async def weekly_plan() -> str:
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": """Составь контент-план на 7 дней.
Каждый день:
- Тема поста
- Формат (текст/рилс/опрос)
- Крючок (первое предложение)
- Цель (охват/доверие/продажа)"""}]
    )
    return response.content[0].text


async def best_formats() -> str:
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1000,
        system=SYSTEM,
        messages=[{"role": "user", "content": "Какие форматы контента сейчас лучше всего работают для экспертов в нише диагностики и личностного роста? Конкретно с примерами."}]
    )
    return response.content[0].text


async def generate_hooks(topic: str) -> str:
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Напиши 5 разных крючков (первое предложение поста) для темы: «{topic}». Каждый — другой тип (вопрос, факт, история, провокация, инсайт)."}]
    )
    return response.content[0].text


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "week"
    if cmd == "week":
        print(await weekly_plan())
    elif cmd == "best":
        print(await best_formats())
    elif cmd == "hook" and len(sys.argv) > 2:
        print(await generate_hooks(" ".join(sys.argv[2:])))


if __name__ == "__main__":
    asyncio.run(main())
