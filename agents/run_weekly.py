#!/usr/bin/env python3
"""
run_weekly.py — главный скрипт еженедельного контент-цикла

Запускает все агенты последовательно:
1. trends_watcher.py — собирает тренды
2. content_generator.py (x3) — генерирует 3 поста
3. content_generator.py --type carousel — генерирует карусель
4. content_generator.py --type reels — генерирует Reels-сценарий
5. Собирает всё в файл НЕДЕЛЯ_[дата].md
6. Выводит итоговый отчёт

Использование:
  python run_weekly.py
  python run_weekly.py --skip-trends  # без сбора трендов (если уже есть)
  python run_weekly.py --topics "нумерология,архетипы"  # дополнительные темы

Требует: ANTHROPIC_API_KEY в ~/reva-scanner/.env
"""

import os
import sys
import argparse
import subprocess
import glob
import re
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv

ENV_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / ".env"
load_dotenv(ENV_PATH)

# ── Пути ──────────────────────────────────────────────────────────────────────
AGENTS_DIR = Path(os.path.expanduser("~")) / "reva-scanner" / "agents"
CONTENT_DIR = Path(os.path.expanduser("~")) / "content" / "бизнес"
METHOD_PATH = Path(os.path.expanduser("~")) / "reva-scanner" / "METHOD.md"
IDEAS_PATH = CONTENT_DIR / "ИДЕИ.md"


def run_script(script_name: str, args: list[str] = None) -> tuple[bool, str]:
    """
    Запускает Python-скрипт из папки agents/.
    Возвращает (успех, вывод).
    """
    script_path = AGENTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + (args or [])

    print(f"   $ python {script_name} {' '.join(args or [])}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 минуты на скрипт
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Таймаут (120 сек)"
    except Exception as e:
        return False, str(e)


def find_latest_file(pattern: str) -> Path | None:
    """Находит последний файл по паттерну."""
    files = glob.glob(str(CONTENT_DIR / pattern))
    if not files:
        return None
    files.sort(reverse=True)
    return Path(files[0])


def read_file_safe(path: Path) -> str:
    """Читает файл, возвращает содержимое или пустую строку."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def extract_generated_content(file_pattern: str, content_type: str) -> str:
    """Извлекает контент из последнего сгенерированного файла."""
    filepath = find_latest_file(file_pattern)
    if not filepath:
        return f"[{content_type} не был создан]"
    content = read_file_safe(filepath)
    # Берём последний блок (после последнего ---)
    parts = content.split("---\n\n")
    return parts[-1].strip() if parts else content


def assemble_week_plan(
    trends_file: Path | None,
    post_files: list[Path],
    carousel_file: Path | None,
    reels_file: Path | None
) -> str:
    """
    Собирает недельный контент-план из всех сгенерированных файлов.
    """
    today = datetime.now()
    # Начало следующей недели (понедельник)
    days_ahead = 7 - today.weekday()  # до следующего понедельника
    if days_ahead == 7:
        days_ahead = 0  # уже понедельник
    week_start = today + timedelta(days=days_ahead)
    week_end = week_start + timedelta(days=6)

    start_str = week_start.strftime("%d.%m.%Y")
    end_str = week_end.strftime("%d.%m.%Y")
    date_str = today.strftime("%Y-%m-%d")

    # Читаем тренды
    trends_content = ""
    if trends_file and trends_file.exists():
        trends_raw = read_file_safe(trends_file)
        # Извлекаем топ-5 тем
        top5_match = re.search(
            r"## Топ-5 тем для контента([\s\S]+?)(?=\n## |\Z)",
            trends_raw
        )
        if top5_match:
            trends_content = top5_match.group(1).strip()[:800]

    # Читаем сгенерированные посты
    posts = []
    for i, pf in enumerate(post_files[:3], 1):
        if pf and pf.exists():
            content = read_file_safe(pf)
            parts = content.split("---\n\n")
            post_text = parts[-1].strip() if parts else content
            posts.append(post_text[:1500])
        else:
            posts.append(f"[Пост {i} не был создан]")

    # Дополняем до 3 постов
    while len(posts) < 3:
        posts.append("[Пост не был создан — запусти content_generator.py вручную]")

    # Карусель
    carousel_content = "[Карусель не была создана]"
    if carousel_file and carousel_file.exists():
        content = read_file_safe(carousel_file)
        parts = content.split("---\n\n")
        carousel_content = parts[-1].strip()[:2000] if parts else content[:2000]

    # Reels
    reels_content = "[Reels-сценарий не был создан]"
    if reels_file and reels_file.exists():
        content = read_file_safe(reels_file)
        parts = content.split("---\n\n")
        reels_content = parts[-1].strip()[:2000] if parts else content[:2000]

    # Собираем план
    plan = f"""# Контент-план — неделя {start_str} — {end_str}
*Сгенерировано автоматически: {today.strftime("%d.%m.%Y %H:%M")}*
*Инструмент: run_weekly.py*

---

## Тренды недели
{trends_content if trends_content else "Запусти trends_watcher.py для актуальных трендов"}

---

## ПОНЕДЕЛЬНИК — @bizscanner

**Тема поста:** Из трендов недели
**Текст:**
{posts[0]}

---

## СРЕДА — @bizscanner

**Тема поста:** Развитие темы
**Текст:**
{posts[1]}

---

## ПЯТНИЦА — @bizscanner

**Тема поста:** Вывод + CTA
**Текст:**
{posts[2]}

---

## ВТОРНИК — Instagram @biz.architect (карусель)

{carousel_content}

---

## ЧЕТВЕРГ — Instagram Reels

{reels_content}

---

## КАК ПУБЛИКОВАТЬ

### Telegram (@bizscanner):
```bash
python ~/reva-scanner/agents/telegram_poster.py --schedule
```

### Instagram (@biz.architect):
Копируй текст карусели и Reels вручную из этого файла.

---

## ИТОГИ ПОДГОТОВКИ

Постов для @bizscanner: 3
Карусель для Instagram: {'✅' if carousel_file else '❌'}
Reels-сценарий: {'✅' if reels_file else '❌'}
Тренды собраны: {'✅' if trends_file else '❌'}

Следующий запуск: {(today + timedelta(days=7)).strftime("%d.%m.%Y")}
"""
    return plan


def save_week_plan(plan: str) -> Path:
    """Сохраняет недельный план."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = CONTENT_DIR / f"НЕДЕЛЯ_{date_str}.md"
    filepath.write_text(plan, encoding="utf-8")
    return filepath


def parse_args():
    parser = argparse.ArgumentParser(
        description="Еженедельный контент-цикл для @Eye888888_bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python run_weekly.py
  python run_weekly.py --skip-trends
  python run_weekly.py --topics "нумерология,деньги"
        """
    )
    parser.add_argument(
        "--skip-trends",
        action="store_true",
        help="Пропустить сбор трендов (использовать последний файл)"
    )
    parser.add_argument(
        "--topics",
        default="",
        help="Дополнительные темы для трендов через запятую"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("🚀 ЕЖЕНЕДЕЛЬНЫЙ КОНТЕНТ-ЦИКЛ @Eye888888_bot")
    print(f"   {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    results = {
        "trends": False,
        "posts": [],
        "carousel": False,
        "reels": False,
    }
    errors = []

    # ── Шаг 1: Тренды ─────────────────────────────────────────────────────────
    print("\n📊 ШАГ 1: Сбор трендов")
    if args.skip_trends:
        trends_file = find_latest_file("ТРЕНДЫ_*.md")
        if trends_file:
            print(f"   ⏭️  Пропускаю (использую {trends_file.name})")
            results["trends"] = True
        else:
            print("   ⚠️  Нет файла трендов, запускаю сбор...")
            args.skip_trends = False

    if not args.skip_trends:
        trend_args = []
        if args.topics:
            trend_args = ["--topics", args.topics]

        success, output = run_script("trends_watcher.py", trend_args)
        if success:
            print("   ✅ Тренды собраны")
            results["trends"] = True
        else:
            print("   ⚠️  Ошибка сбора трендов (продолжаю без них)")
            errors.append(f"trends_watcher: {output[-200:]}")

    trends_file = find_latest_file("ТРЕНДЫ_*.md")

    # ── Шаг 2: 3 поста ────────────────────────────────────────────────────────
    print("\n✍️  ШАГ 2: Генерация 3 постов для @bizscanner")

    # Определяем темы для постов (из трендов или базовые)
    post_topics = [
        "почему бизнес не растёт — нумерологический взгляд",
        "ловушка мастера: когда ты сам тормозишь свой бизнес",
        "деньги и число судьбы: что твоя дата рождения говорит о доходе",
    ]

    # Если есть тренды — читаем топ-5 тем и берём первые 3
    if trends_file and trends_file.exists():
        trends_text = read_file_safe(trends_file)
        top_match = re.findall(r"\d\.\s+(.+?)\s+—", trends_text)
        if top_match and len(top_match) >= 3:
            post_topics = top_match[:3]
            print(f"   Темы из трендов: {post_topics}")

    post_files = []
    for i, topic in enumerate(post_topics, 1):
        print(f"\n   Пост {i}/3: {topic[:50]}...")
        success, output = run_script(
            "content_generator.py",
            ["--type", "post", "--topic", topic]
        )
        if success:
            print(f"   ✅ Пост {i} создан")
            results["posts"].append(True)
            pf = find_latest_file(f"АВТО_POST_*.md")
            post_files.append(pf)
        else:
            print(f"   ❌ Ошибка поста {i}")
            errors.append(f"post {i}: {output[-200:]}")
            results["posts"].append(False)
            post_files.append(None)

    # ── Шаг 3: Карусель ───────────────────────────────────────────────────────
    print("\n🎠 ШАГ 3: Генерация карусели для Instagram")

    # Тема карусели — первая из трендов или базовая
    carousel_topic = post_topics[0] if post_topics else "4 уровня блоков в бизнесе"
    print(f"   Тема: {carousel_topic[:60]}...")

    success, output = run_script(
        "content_generator.py",
        ["--type", "carousel", "--topic", carousel_topic]
    )
    if success:
        print("   ✅ Карусель создана")
        results["carousel"] = True
        carousel_file = find_latest_file("АВТО_CAROUSEL_*.md")
    else:
        print("   ❌ Ошибка карусели")
        errors.append(f"carousel: {output[-200:]}")
        carousel_file = None

    # ── Шаг 4: Reels ──────────────────────────────────────────────────────────
    print("\n🎬 ШАГ 4: Генерация Reels-сценария")

    reels_topic = post_topics[1] if len(post_topics) > 1 else "блоки в деньгах по нумерологии"
    print(f"   Тема: {reels_topic[:60]}...")

    success, output = run_script(
        "content_generator.py",
        ["--type", "reels", "--topic", reels_topic]
    )
    if success:
        print("   ✅ Reels-сценарий создан")
        results["reels"] = True
        reels_file = find_latest_file("АВТО_REELS_*.md")
    else:
        print("   ❌ Ошибка Reels")
        errors.append(f"reels: {output[-200:]}")
        reels_file = None

    # ── Шаг 5: Сборка недельного плана ───────────────────────────────────────
    print("\n📋 ШАГ 5: Сборка недельного плана")

    plan = assemble_week_plan(trends_file, post_files, carousel_file, reels_file)
    week_filepath = save_week_plan(plan)
    print(f"   ✅ Недельный план сохранён: {week_filepath.name}")

    # ── Итоговый отчёт ────────────────────────────────────────────────────────
    posts_ok = sum(1 for p in results["posts"] if p)
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)
    print(f"  Тренды:          {'✅' if results['trends'] else '❌'}")
    print(f"  Посты (3):       {'✅' if posts_ok == 3 else f'⚠️  {posts_ok}/3'}")
    print(f"  Карусель:        {'✅' if results['carousel'] else '❌'}")
    print(f"  Reels-сценарий:  {'✅' if results['reels'] else '❌'}")
    print(f"\n  📁 Недельный план: {week_filepath}")
    print(f"\n  🚀 Публикация в Telegram:")
    print(f"     python ~/reva-scanner/agents/telegram_poster.py --schedule")

    if errors:
        print(f"\n⚠️  Ошибки ({len(errors)}):")
        for err in errors:
            print(f"   - {err[:100]}")

    total_ok = (
        results["trends"] +
        posts_ok +
        results["carousel"] +
        results["reels"]
    )
    total_max = 6

    print(f"\n  Готово: {total_ok}/{total_max} задач")

    if total_ok == total_max:
        print("\n  🎉 Всё готово! Неделя закрыта.")
    else:
        print("\n  💡 Проверь ошибки выше и запусти недостающее вручную.")

    print("=" * 60)


if __name__ == "__main__":
    main()
