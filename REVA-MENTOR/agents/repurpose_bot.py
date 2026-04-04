"""
Агент перепаковки контента.
Берёт один пост и адаптирует под все платформы.

Запуск:
  python3 repurpose_bot.py adapt "текст поста"
  python3 repurpose_bot.py thread "тема для треда"
"""
import asyncio
import sys
import os
from anthropic import AsyncAnthropic
from config import config

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", config.anthropic_api_key))

SYSTEM = f"""Ты — контент-стратег бренда «{config.brand_name}».
Умеешь адаптировать один материал под разные форматы без потери смысла.
Голос Юлии: живой, честный, экспертный."""


async def adapt_content(text: str) -> str:
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Адаптируй этот материал под 3 платформы:

ИСХОДНИК:
{text}

Дай:
1. TELEGRAM — пост (до 1000 символов)
2. INSTAGRAM — пост с хэштегами
3. TIKTOK/REELS — сценарий на 30 сек (по секундам)"""
        }]
    )
    return response.content[0].text


async def create_thread(topic: str) -> str:
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Напиши тред из 5 постов на тему «{topic}». Каждый пост — отдельная мысль, заканчивается крючком на следующий."
        }]
    )
    return response.content[0].text


async def main():
    if len(sys.argv) < 3:
        print("Использование: python3 repurpose_bot.py adapt|thread <текст>")
        return

    cmd, text = sys.argv[1], " ".join(sys.argv[2:])
    if cmd == "adapt":
        print(await adapt_content(text))
    elif cmd == "thread":
        print(await create_thread(text))


if __name__ == "__main__":
    asyncio.run(main())
