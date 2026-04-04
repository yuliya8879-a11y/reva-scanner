#!/usr/bin/env python3
"""
telegram_poster.py — публикация постов в Telegram-канал @bizscanner

Использование:
  python telegram_poster.py --now "Текст поста"
  python telegram_poster.py --file ~/content/бизнес/НЕДЕЛЯ_2026-03-29.md
  python telegram_poster.py --schedule  # интерактивный выбор из файла

Требует: TELEGRAM_BOT_TOKEN в ~/reva-scanner/.env
"""

import os
import sys
import argparse
import requests
import glob
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ── Пути ──────────────────────────────────────────────────────────────────────
ENV_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / ".env"
CONTENT_DIR = Path(os.path.expanduser("~")) / "content" / "бизнес"

# ── Константы ─────────────────────────────────────────────────────────────────
CHANNEL_ID = "@bizscanner"
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# ── Загрузка окружения ────────────────────────────────────────────────────────
load_dotenv(ENV_PATH)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def check_token():
    """Проверяем наличие токена."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        print(f"   Путь к .env: {ENV_PATH}")
        sys.exit(1)


def send_message(text: str, channel: str = CHANNEL_ID) -> dict:
    """
    Отправляет сообщение в Telegram-канал.
    Возвращает ответ API.
    """
    url = TELEGRAM_API.format(token=BOT_TOKEN, method="sendMessage")
    payload = {
        "chat_id": channel,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Ошибка при отправке: {e}")
        sys.exit(1)


def publish_now(text: str):
    """Публикует текст прямо сейчас."""
    check_token()

    print(f"\n📤 Публикую в {CHANNEL_ID}...")
    print(f"─" * 50)
    # Предпросмотр текста (первые 100 символов)
    preview = text[:100] + ("..." if len(text) > 100 else "")
    print(f"Текст: {preview}")
    print(f"─" * 50)

    result = send_message(text)

    if result.get("ok"):
        msg = result.get("result", {})
        msg_id = msg.get("message_id")
        date = datetime.fromtimestamp(msg.get("date", 0)).strftime("%d.%m.%Y %H:%M")
        print(f"✅ Опубликовано!")
        print(f"   Канал: {CHANNEL_ID}")
        print(f"   ID сообщения: {msg_id}")
        print(f"   Время: {date}")
    else:
        error = result.get("description", "неизвестная ошибка")
        print(f"❌ Ошибка публикации: {error}")
        sys.exit(1)


def read_week_file(filepath: Path) -> list[dict]:
    """
    Читает НЕДЕЛЯ файл и извлекает посты для @bizscanner.
    Возвращает список словарей: {'day': str, 'topic': str, 'text': str}
    """
    posts = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"❌ Файл не найден: {filepath}")
        sys.exit(1)

    # Ищем секции с постами (@bizscanner)
    # Паттерн: ## ПОНЕДЕЛЬНИК — @bizscanner и т.д.
    day_pattern = re.compile(
        r"##\s+(ПОНЕДЕЛЬНИК|ВТОРНИК|СРЕДА|ЧЕТВЕРГ|ПЯТНИЦА|СУББОТА|ВОСКРЕСЕНЬЕ)\s*[—–-]\s*@bizscanner",
        re.IGNORECASE
    )

    # Ищем блоки с текстом постов
    # Берём всё между **Текст:** и следующей секцией ---
    sections = re.split(r"\n---\n", content)
    for section in sections:
        day_match = day_pattern.search(section)
        if day_match:
            day = day_match.group(1)
            # Извлекаем тему
            topic_match = re.search(r"\*\*Тема поста:\*\*\s*(.+)", section)
            topic = topic_match.group(1).strip() if topic_match else "Без темы"
            # Извлекаем текст поста
            text_match = re.search(r"\*\*Текст:\*\*\s*\n([\s\S]+?)(?=\n---|\n##|\Z)", section)
            if text_match:
                text = text_match.group(1).strip()
                posts.append({"day": day, "topic": topic, "text": text})

    return posts


def find_latest_week_file() -> Path | None:
    """Находит последний файл НЕДЕЛЯ_*.md в папке контента."""
    pattern = str(CONTENT_DIR / "НЕДЕЛЯ_*.md")
    files = glob.glob(pattern)
    if not files:
        return None
    # Сортируем по дате в имени файла
    files.sort(reverse=True)
    return Path(files[0])


def schedule_from_file(filepath: Path | None = None):
    """Интерактивный выбор поста из файла для публикации."""
    check_token()

    if filepath is None:
        filepath = find_latest_week_file()
        if filepath is None:
            print(f"❌ Нет файлов НЕДЕЛЯ_*.md в {CONTENT_DIR}")
            print("   Сначала создай контент-план через reva-week агент или run_weekly.py")
            sys.exit(1)
        print(f"📂 Использую файл: {filepath.name}")

    posts = read_week_file(filepath)

    if not posts:
        print(f"❌ Не нашёл постов для @bizscanner в файле {filepath.name}")
        print("   Проверь формат файла (должны быть секции ## ДЕНЬ — @bizscanner)")
        sys.exit(1)

    print(f"\n📋 Найдено {len(posts)} поста для @bizscanner:\n")
    for i, post in enumerate(posts, 1):
        preview = post["text"][:60].replace("\n", " ") + "..."
        print(f"  {i}. [{post['day']}] {post['topic']}")
        print(f"     {preview}\n")

    # Выбор поста
    while True:
        try:
            choice = input("Выбери номер поста для публикации (или 0 для отмены): ").strip()
            if choice == "0":
                print("Отменено.")
                return
            idx = int(choice) - 1
            if 0 <= idx < len(posts):
                selected = posts[idx]
                break
            print(f"Введи число от 1 до {len(posts)}")
        except (ValueError, KeyboardInterrupt):
            print("\nОтменено.")
            return

    # Подтверждение
    print(f"\n📝 Пост для публикации:")
    print(f"─" * 50)
    print(selected["text"])
    print(f"─" * 50)
    confirm = input("\nОпубликовать? (да/нет): ").strip().lower()

    if confirm in ("да", "yes", "y", "д"):
        publish_now(selected["text"])
    else:
        print("Отменено.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Публикация постов в Telegram-канал @bizscanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python telegram_poster.py --now "Текст поста"
  python telegram_poster.py --file ~/content/бизнес/НЕДЕЛЯ_2026-03-29.md
  python telegram_poster.py --schedule
        """
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--now",
        metavar="ТЕКСТ",
        help="Опубликовать текст прямо сейчас"
    )
    group.add_argument(
        "--file",
        metavar="ПУТЬ",
        help="Выбрать пост из файла НЕДЕЛЯ_*.md"
    )
    group.add_argument(
        "--schedule",
        action="store_true",
        help="Интерактивный выбор из последнего файла НЕДЕЛЯ_*.md"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.now:
        publish_now(args.now)

    elif args.file:
        filepath = Path(os.path.expanduser(args.file))
        schedule_from_file(filepath)

    elif args.schedule:
        schedule_from_file()


if __name__ == "__main__":
    main()
