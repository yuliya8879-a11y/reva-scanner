#!/usr/bin/env python3
"""
content_generator.py — автоматическая генерация контента через Claude API

Использование:
  python content_generator.py --type post --topic "блоки в деньгах"
  python content_generator.py --type carousel --topic "архетип владельца"
  python content_generator.py --type reels --topic "нумерология для бизнеса"

Типы контента:
  post      — пост для Telegram/Instagram
  carousel  — карусель Instagram (10 слайдов)
  reels     — сценарий Reels 30-60 сек

Требует: ANTHROPIC_API_KEY в ~/reva-scanner/.env
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Загружаем .env до импорта anthropic
from dotenv import load_dotenv

ENV_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / ".env"
load_dotenv(ENV_PATH)

import anthropic

# ── Пути ──────────────────────────────────────────────────────────────────────
METHOD_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / "METHOD.md"
IDEAS_PATH = Path(os.path.expanduser("~")) / "content" / "бизнес" / "ИДЕИ.md"
CONTENT_DIR = Path(os.path.expanduser("~")) / "content" / "бизнес"

# ── Модель (haiku — дешевле для генерации) ────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# ── Промпты по типам контента ─────────────────────────────────────────────────

SYSTEM_BASE = """Ты — контент-менеджер и копирайтер Юлии Ревой, автора метода "Глаз Бога".
Проект: @Eye888888_bot — AI бизнес-сканер на основе нумерологии и 4 уровней блоков.

Стиль Юлии:
- Только "ты". Прямо. Без дистанции.
- Короткие фразы. Пауза. Потом следующая.
- Образы, которые чувствуются телом: держать, тонуть, корни, свет, стена, воздух
- Не пугать — но говорить правду с опорой на выход
- Всегда CTA → @Eye888888_bot

Метод (краткая суть):
- Нумерология: число души (день рождения) и число судьбы (сумма всей даты)
- 4 уровня блоков: физический → эмоциональный → ментальный → причинный
- 7 чакр как карта зон проблем
- Не поиск похожего — считывание конкретного человека

Никогда не используй корпоративный язык. Пиши так, как говорит умный человек другу."""

PROMPTS = {
    "post": """Напиши пост для Telegram-канала @bizscanner и/или Instagram @biz.architect.

Тема: {topic}

Метод Юлии для контекста:
{method}

Формат поста:
- Первая строка: стоп-фраза (работает без раскрытия, вызывает желание прочитать)
- 3-5 коротких абзацев (каждый 1-3 строки)
- Последний абзац: вывод + CTA → @Eye888888_bot
- 12-15 хэштегов в конце

Объём: 150-250 слов текста + хэштеги.
Пиши на русском языке.""",

    "carousel": """Напиши карусель для Instagram @biz.architect (10 слайдов с текстом).

Тема: {topic}

Метод Юлии для контекста:
{method}

Формат каждого слайда:
СЛАЙД [номер]:
ТЕКСТ: [короткий текст, 1-4 строки]
ДИЗАЙН: [подсказка для дизайна — цвет, элемент, акцент]

Структура:
- Слайд 1 (обложка): Провокационный заголовок. Боль или неожиданное утверждение.
- Слайды 2-3: Ситуация и усиление
- Слайды 4-8: Основная идея через призму метода (нумерология/уровни/чакры)
- Слайд 9: Признание / "ты не одна в этом"
- Слайд 10: CTA + @Eye888888_bot

Пиши на русском языке. Все тексты для слайдов должны быть конкретными и готовыми к публикации.""",

    "reels": """Напиши сценарий Reels для Instagram @biz.architect (30-60 секунд).

Тема: {topic}

Метод Юлии для контекста:
{method}

Формат:
═══ ХУК (0-3 сек) ═══
[ТЕКСТ НА ЭКРАНЕ: крупно, 1-3 слова или короткая фраза]
[ГОЛОС: что говорит Юлия]

═══ ТЕЛО (3-45 сек) ═══
Блок 1 (3-15 сек):
[ТЕКСТ НА ЭКРАНЕ: ...]
[ГОЛОС: ...]

Блок 2 (15-30 сек):
[ТЕКСТ НА ЭКРАНЕ: ...]
[ГОЛОС: ...]

Блок 3 (30-45 сек):
[ТЕКСТ НА ЭКРАНЕ: ...]
[ГОЛОС: ...]

═══ CTA (45-60 сек) ═══
[ТЕКСТ НА ЭКРАНЕ: ...]
[ГОЛОС: ...]

═══ ХЭШТЕГИ (15-20 штук) ═══
[список]

Пиши на русском языке. Сценарий должен быть динамичным и останавливать скролл."""
}


def read_file_safe(path: Path, description: str) -> str:
    """Читает файл, возвращает содержимое или пустую строку с предупреждением."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️  {description} не найден: {path}")
        return ""
    except Exception as e:
        print(f"⚠️  Ошибка чтения {description}: {e}")
        return ""


def generate_content(content_type: str, topic: str) -> str:
    """
    Генерирует контент через Claude API.
    Возвращает готовый текст.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY не найден в .env")
        print(f"   Путь к .env: {ENV_PATH}")
        sys.exit(1)

    # Читаем контекст
    method_content = read_file_safe(METHOD_PATH, "METHOD.md")
    ideas_content = read_file_safe(IDEAS_PATH, "ИДЕИ.md")

    # Формируем системный промпт с методом
    system_prompt = SYSTEM_BASE
    if ideas_content:
        system_prompt += f"\n\nАктуальные идеи Юлии из ИДЕИ.md:\n{ideas_content[:2000]}"

    # Обрезаем METHOD.md до разумного размера (первые 3000 символов ключевых частей)
    method_short = method_content[:3000] if method_content else "Метод недоступен"

    # Формируем пользовательский промпт
    if content_type not in PROMPTS:
        print(f"❌ Неизвестный тип контента: {content_type}")
        print(f"   Доступные типы: {', '.join(PROMPTS.keys())}")
        sys.exit(1)

    user_prompt = PROMPTS[content_type].format(
        topic=topic,
        method=method_short
    )

    # Вызов Claude API
    print(f"🤖 Генерирую {content_type} на тему: {topic}...")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return message.content[0].text
    except anthropic.APIError as e:
        print(f"❌ Ошибка Claude API: {e}")
        sys.exit(1)


def save_content(content_type: str, topic: str, content: str) -> Path:
    """Сохраняет контент в файл и возвращает путь."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"АВТО_{content_type.upper()}_{date_str}.md"
    filepath = CONTENT_DIR / filename

    # Если файл уже есть — добавляем к нему
    if filepath.exists():
        separator = "\n\n---\n\n"
        existing = filepath.read_text(encoding="utf-8")
        full_content = existing + separator
    else:
        full_content = ""

    # Формируем блок с контентом
    timestamp = datetime.now().strftime("%H:%M")
    block = f"""# {content_type.upper()} — {topic}
*Создано: {date_str} {timestamp}*

{content}
"""
    full_content += block

    filepath.write_text(full_content, encoding="utf-8")
    return filepath


def parse_args():
    parser = argparse.ArgumentParser(
        description="Генерация Instagram/Telegram контента через Claude API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python content_generator.py --type post --topic "блоки в деньгах"
  python content_generator.py --type carousel --topic "архетип владельца"
  python content_generator.py --type reels --topic "почему бизнес не растёт"
        """
    )
    parser.add_argument(
        "--type",
        choices=["post", "carousel", "reels"],
        required=True,
        help="Тип контента: post, carousel или reels"
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Тема для генерации"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Генерируем контент
    content = generate_content(args.type, args.topic)

    # Сохраняем
    filepath = save_content(args.type, args.topic, content)

    # Выводим результат
    print(f"\n{'═' * 60}")
    print(content)
    print(f"{'═' * 60}")
    print(f"\n✅ Сохранено: {filepath}")
    print(f"   Тип: {args.type}")
    print(f"   Тема: {args.topic}")


if __name__ == "__main__":
    main()
