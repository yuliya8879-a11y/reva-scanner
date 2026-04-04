"""
Тренд-аналитик: отслеживает актуальные тренды в нише
и генерирует инсайты + идеи контента на основе трендов.

Запуск:
  python trends_bot.py analyze
  python trends_bot.py ideas "диагностика блоков"
  python trends_bot.py competitor "имя конкурента или описание"
"""
import asyncio
import sys
from datetime import date
from anthropic import AsyncAnthropic
from config import config


client = AsyncAnthropic(api_key=config.anthropic_api_key)

TODAY = date.today().strftime("%d.%m.%Y")

ANALYST_SYSTEM = f"""Ты — маркетинговый аналитик и стратег для бренда «{config.brand_name}».
Ниша: {config.niche}.
Аудитория: {config.target_audience}.
Сегодня: {TODAY}.

Твоя задача: анализировать тренды, находить возможности для роста и генерировать
конкретные идеи контента, которые «залетят» прямо сейчас.
Говори конкретно, с примерами. Избегай общих фраз."""


async def analyze_trends() -> str:
    """Анализ актуальных трендов в нише."""
    sources = "\n".join(f"- {s}" for s in config.trend_sources)
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1500,
        system=ANALYST_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Проанализируй текущие тренды в нише для контента по темам:
{sources}

Дай:
1. ТОП-5 трендов прямо сейчас (что хорошо заходит в Telegram и Instagram)
2. Антитренды (что уже не работает, людям надоело)
3. Незанятые ниши — что конкуренты не освещают, но аудитория ищет
4. Форматы контента с наибольшим охватом в этой нише сейчас
5. Конкретные 5 тем для постов, актуальных ПРЯМО СЕЙЧАС

Будь конкретным. Опирайся на реальную картину рынка экспертов в России 2025."""
        }]
    )
    return response.content[0].text


async def generate_trend_ideas(topic: str) -> str:
    """Идеи контента на основе тренда."""
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1000,
        system=ANALYST_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Тема/тренд: «{topic}»

Для этой темы придумай:
1. 3 идеи для Reels (крючок + формат + почему залетит)
2. 3 идеи для постов в Telegram (угол подачи + почему цепляет аудиторию)
3. 1 идея для серии сторис (3-5 частей, нарратив)
4. Потенциальный вирусный формат — что-то нестандартное

Для каждой идеи укажи: заголовок/крючок, формат, почему это сработает сейчас."""
        }]
    )
    return response.content[0].text


async def analyze_competitor(competitor_description: str) -> str:
    """Анализ конкурентов и стратегии отстройки."""
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1000,
        system=ANALYST_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Проанализируй конкурента/аналог в нише:
{competitor_description}

Дай:
1. Что они делают хорошо (возьмём на заметку)
2. Их слабые места — где мы можем быть лучше
3. Чего им не хватает — незакрытые боли аудитории
4. Как нам отстроиться от них (уникальное позиционирование)
5. 3 конкретные идеи контента, которые выгодно нас отличат

Бренд «{config.brand_name}» отличается: Telegram-бот с AI-диагностикой, нумерология,
соматика, доступность 24/7, конкретные блоки и рекомендации."""
        }]
    )
    return response.content[0].text


async def weekly_brief() -> str:
    """Еженедельная сводка для планирования контента."""
    sources = ", ".join(config.trend_sources)
    response = await client.messages.create(
        model=config.trends_model,
        max_tokens=1200,
        system=ANALYST_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Составь еженедельную маркетинговую сводку для эксперта в нише: {sources}

Формат сводки:
📊 ТРЕНДЫ НЕДЕЛИ — что сейчас актуально
🎯 ФОКУС НА НЕДЕЛЮ — 1 главная тема для контента
📅 ПЛАН НА 7 ДНЕЙ — конкретные темы по дням (Пн-Вс)
💡 ИНСАЙТ — неочевидное наблюдение, которое стоит использовать
⚡ БЫСТРЫЕ ПОБЕДЫ — 2-3 действия с высоким ROI прямо сейчас

Будь конкретным, как будто готовишь сводку для реального клиента."""
        }]
    )
    return response.content[0].text


async def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python trends_bot.py analyze          — анализ трендов в нише")
        print("  python trends_bot.py ideas 'тема'     — идеи контента по теме")
        print("  python trends_bot.py competitor 'кто' — анализ конкурента")
        print("  python trends_bot.py brief            — еженедельная сводка")
        return

    cmd = sys.argv[1]

    if cmd == "analyze":
        result = await analyze_trends()
        print("\n📈 ТРЕНДЫ В НИШЕ:\n")
        print(result)

    elif cmd == "ideas":
        topic = sys.argv[2] if len(sys.argv) > 2 else "диагностика блоков"
        result = await generate_trend_ideas(topic)
        print(f"\n💡 ИДЕИ КОНТЕНТА — «{topic}»:\n")
        print(result)

    elif cmd == "competitor":
        desc = sys.argv[2] if len(sys.argv) > 2 else "эксперт по нумерологии в Telegram"
        result = await analyze_competitor(desc)
        print("\n🔍 АНАЛИЗ КОНКУРЕНТА:\n")
        print(result)

    elif cmd == "brief":
        result = await weekly_brief()
        print("\n📋 ЕЖЕНЕДЕЛЬНАЯ СВОДКА:\n")
        print(result)

    else:
        print(f"Неизвестная команда: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
