#!/usr/bin/env python3
"""
trends_watcher.py — мониторинг трендов в нише Юлии Ревой

Ищет актуальные темы и конкурентов в нишах:
- нумерология + предприниматели
- архетипы владельца бизнеса
- блоки в деньгах / финансовые программы
- AI диагностика для бизнеса
- выгорание предпринимателей

Использование:
  python trends_watcher.py
  python trends_watcher.py --topics "нумерология бизнес,блоки деньги"

Запускать еженедельно.
Требует: ANTHROPIC_API_KEY в ~/reva-scanner/.env
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

ENV_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / ".env"
load_dotenv(ENV_PATH)

import anthropic

# ── Пути ──────────────────────────────────────────────────────────────────────
CONTENT_DIR = Path(os.path.expanduser("~")) / "content" / "бизнес"
METHOD_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / "METHOD.md"

# ── Модель ────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# ── Темы для мониторинга (базовые) ────────────────────────────────────────────
DEFAULT_TOPICS = [
    "нумерология предприниматель 2025 2026",
    "архетип владельца бизнеса блоки",
    "финансовый блок деньги нумерология",
    "AI диагностика личность бизнес",
    "выгорание предприниматель что делать",
    "блоки в деньгах программы установки",
    "число судьбы предназначение бизнес",
]

# ── Поисковые запросы для Yandex/Google ──────────────────────────────────────
SEARCH_QUERIES = [
    "нумерология для предпринимателей тренды",
    "блоки в деньгах Instagram популярное",
    "архетип владельца telegram канал",
    "AI диагностика бизнес популярные боты",
    "нумерология бизнес сканер",
]

# ── Хэштеги для анализа ───────────────────────────────────────────────────────
HASHTAGS_TO_MONITOR = [
    "#нумерологиябизнес",
    "#блокивденьгах",
    "#архетиппредпринимателя",
    "#числодуши",
    "#финансовыеблоки",
    "#предназначениевбизнесе",
    "#женщинавбизнесе",
    "#предприниматель",
    "#деньгиифинансы",
    "#личностныйрост",
]


def fetch_search_context(query: str) -> str:
    """
    Пытается получить контекст из DuckDuckGo Instant Answer API.
    Не требует API ключей. Возвращает описание или пустую строку.
    """
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
            "no_redirect": 1,
        }
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RevaScanner/1.0)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        # Собираем доступные данные
        parts = []
        if data.get("AbstractText"):
            parts.append(data["AbstractText"])
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(topic["Text"])

        return " | ".join(parts) if parts else ""
    except Exception:
        # Если поиск недоступен — не падаем, просто возвращаем пусто
        return ""


def collect_search_context(topics: list[str]) -> str:
    """
    Собирает контекст по всем темам через поиск.
    Возвращает сводный текст для анализа.
    """
    context_parts = []

    print("🔍 Собираю данные по темам...")
    for i, topic in enumerate(topics, 1):
        print(f"   [{i}/{len(topics)}] {topic}")
        result = fetch_search_context(topic)
        if result:
            context_parts.append(f"Тема: {topic}\nДанные: {result}")

    # Если ничего не нашли через API — работаем с базовыми знаниями модели
    if not context_parts:
        context_parts.append(
            "Поисковые запросы не дали результатов. "
            "Анализируй на основе актуальных трендов в нишах: "
            "нумерология, предпринимательство, коучинг, AI-инструменты для бизнеса."
        )

    return "\n\n".join(context_parts)


def generate_trends_report(search_context: str, topics: list[str]) -> str:
    """
    Генерирует отчёт о трендах через Claude.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY не найден в .env")
        sys.exit(1)

    # Читаем METHOD.md для контекста
    try:
        method_content = METHOD_PATH.read_text(encoding="utf-8")[:2000]
    except FileNotFoundError:
        method_content = "Метод: нумерология + 4 уровня блоков + чакры для анализа бизнеса"

    system_prompt = """Ты — маркетинг-аналитик и контент-стратег для Юлии Ревой.
Проект: @Eye888888_bot — AI бизнес-сканер "Глаз Бога" (нумерология + 4 уровня блоков + чакры).
Аудитория: предприниматели, владельцы бизнеса, женщины в бизнесе.
Каналы: @bizscanner (Telegram), @biz.architect (Instagram).

Твоя задача: анализировать тренды и давать конкретные рекомендации по контенту.
Всегда отвечай на русском языке."""

    user_prompt = f"""Проанализируй текущие тренды в нишах Юлии Ревой и составь отчёт.

Метод Юлии (краткая суть):
{method_content}

Мониторируемые темы:
{chr(10).join(f"- {t}" for t in topics)}

Данные из поиска (если есть):
{search_context}

Хэштеги для мониторинга:
{', '.join(HASHTAGS_TO_MONITOR)}

Составь детальный отчёт в формате:

## Горячие темы прямо сейчас
[3-5 тем с объяснением почему они актуальны для аудитории Юлии]

## Топ-5 тем для контента на этой неделе
1. [тема] — [почему подходит + рекомендуемый формат: пост/карусель/reels]
2. [тема] — [...]
3. [тема] — [...]
4. [тема] — [...]
5. [тема] — [...]

## Конкуренты и коллеги в нише
[3-5 типов аккаунтов с описанием что делают успешно]

## Популярные хэштеги (рекомендации)
Нишевые (10K-100K): [список]
Широкие (>500K): [список]
Для роста (растущие): [список]

## Форматы которые сейчас заходят
[что лучше работает в Instagram и Telegram прямо сейчас]

## Возможности для коллабораций
[3-5 направлений где Юлии имеет смысл появиться]

## Что делать на этой неделе
[конкретный план из 3-5 действий]"""

    print("🤖 Анализирую тренды через Claude...")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return message.content[0].text
    except anthropic.APIError as e:
        print(f"❌ Ошибка Claude API: {e}")
        sys.exit(1)


def save_report(report: str) -> Path:
    """Сохраняет отчёт в файл."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = CONTENT_DIR / f"ТРЕНДЫ_{date_str}.md"

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    full_content = f"""# Отчёт трендов — {date_str}
*Сгенерировано: {timestamp}*
*Инструмент: trends_watcher.py*

---

{report}

---
*Следующий запуск: через 7 дней*
"""

    filepath.write_text(full_content, encoding="utf-8")
    return filepath


def parse_args():
    parser = argparse.ArgumentParser(
        description="Мониторинг трендов в нише Юлии Ревой",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python trends_watcher.py
  python trends_watcher.py --topics "нумерология бизнес,блоки деньги,архетипы"
        """
    )
    parser.add_argument(
        "--topics",
        help="Дополнительные темы через запятую",
        default=""
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Формируем список тем
    topics = DEFAULT_TOPICS.copy()
    if args.topics:
        extra = [t.strip() for t in args.topics.split(",") if t.strip()]
        topics.extend(extra)

    print(f"\n🔭 Мониторинг трендов для @Eye888888_bot")
    print(f"   Тем для анализа: {len(topics)}")
    print()

    # Собираем данные из поиска
    search_context = collect_search_context(SEARCH_QUERIES)

    # Генерируем отчёт
    report = generate_trends_report(search_context, topics)

    # Сохраняем
    filepath = save_report(report)

    # Выводим результат
    print(f"\n{'═' * 60}")
    print(report)
    print(f"{'═' * 60}")
    print(f"\n✅ Отчёт сохранён: {filepath}")
    print(f"   Используй его для создания контент-плана:")
    print(f"   python run_weekly.py  — полный недельный цикл")


if __name__ == "__main__":
    main()
