"""
Контент-бот: генерирует посты, сценарии рилс и планы публикаций
для Telegram-канала, Instagram и TikTok.

Запуск:
  python content_bot.py post "тема поста"
  python content_bot.py reels "тема рилс"
  python content_bot.py plan 30
"""
import asyncio
import sys
from anthropic import AsyncAnthropic
from config import config


client = AsyncAnthropic(api_key=config.anthropic_api_key)

SYSTEM_PROMPT = f"""Ты — контент-менеджер бренда «{config.brand_name}».
Аудитория: {config.target_audience}.
Ниша: {config.niche}.

Стиль: живой, честный, без воды. Говоришь от первого лица (от имени Юлии).
Цепляющий крючок в начале, ценность в теле, призыв к действию в конце.
Язык: русский. Без хэштегов, если не просят."""


async def generate_telegram_post(topic: str) -> str:
    """Пост для Telegram-канала @Reva_mentor."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Напиши пост для Telegram-канала на тему: «{topic}»

Структура:
1. Крючок — 1 предложение, вызывающее желание читать дальше
2. Проблема/история — 2-3 абзаца
3. Ценность/инсайт — конкретный вывод
4. CTA — мягкий призыв (не «купи», а «напиши мне» / «разберём твой случай»)

Длина: 150-250 слов. Эмодзи умеренно."""
        }]
    )
    return response.content[0].text


async def generate_instagram_post(topic: str) -> str:
    """Пост для Instagram с хэштегами."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Напиши пост для Instagram на тему: «{topic}»

Структура:
1. Первая строка — крючок (видна без «ещё»)
2. Тело — 100-150 слов, абзацы короткие
3. CTA
4. 10-15 хэштегов на русском и английском

Тон: вдохновляющий, экспертный."""
        }]
    )
    return response.content[0].text


async def generate_reels_script(topic: str) -> str:
    """Сценарий для Reels/TikTok (30 секунд)."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Напиши сценарий рилс на {config.reels_duration_seconds} секунд на тему: «{topic}»

Формат:
[0-3 сек] КРЮЧОК: (текст на экране + что говоришь)
[3-8 сек] ПРОБЛЕМА: (что показываешь + текст)
[8-20 сек] РЕШЕНИЕ: (основной контент, 2-3 пункта)
[20-25 сек] РЕЗУЛЬТАТ: (что получит зритель)
[25-30 сек] CTA: (призыв + текст на экране)

Укажи: музыкальный стиль, переходы, текст на экране отдельно от закадрового голоса."""
        }]
    )
    return response.content[0].text


async def generate_content_plan(days: int = 30) -> str:
    """30-дневный контент-план с темами."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Создай контент-план на {days} дней для эксперта в нише: {config.niche}

Для каждого дня: номер, тема, формат (пост/рилс/сторис), платформа.
Чередуй: экспертный контент, личное, продающее (80/10/10).
Учти воронку: сначала охват → вовлечение → прогрев → продажа.

Оформи таблицей:
День | Тема | Формат | Платформа | Цель

После таблицы — 3 главных совета по продвижению в нише."""
        }]
    )
    return response.content[0].text


async def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python content_bot.py post 'тема'")
        print("  python content_bot.py instagram 'тема'")
        print("  python content_bot.py reels 'тема'")
        print("  python content_bot.py plan [дней]")
        return

    cmd = sys.argv[1]

    if cmd == "post":
        topic = sys.argv[2] if len(sys.argv) > 2 else "диагностика блоков в бизнесе"
        result = await generate_telegram_post(topic)
        print("\n📢 ПОСТ ДЛЯ TELEGRAM:\n")
        print(result)

    elif cmd == "instagram":
        topic = sys.argv[2] if len(sys.argv) > 2 else "личный бренд эксперта"
        result = await generate_instagram_post(topic)
        print("\n📸 ПОСТ ДЛЯ INSTAGRAM:\n")
        print(result)

    elif cmd == "reels":
        topic = sys.argv[2] if len(sys.argv) > 2 else "как найти свой главный блок"
        result = await generate_reels_script(topic)
        print("\n🎬 СЦЕНАРИЙ РИЛС:\n")
        print(result)

    elif cmd == "plan":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = await generate_content_plan(days)
        print(f"\n📅 КОНТЕНТ-ПЛАН НА {days} ДНЕЙ:\n")
        print(result)

    else:
        print(f"Неизвестная команда: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
