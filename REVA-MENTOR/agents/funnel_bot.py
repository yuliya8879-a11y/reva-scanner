"""
Автоворонка для Telegram: приветствие → прогрев → продажа.
Генерирует тексты для каждого шага воронки.

Запуск:
  python funnel_bot.py welcome      — приветственная серия (3 сообщения)
  python funnel_bot.py warmup       — прогревочная серия (5 сообщений)
  python funnel_bot.py sale         — продающие сообщения
  python funnel_bot.py full         — полная воронка
  python funnel_bot.py objections   — ответы на возражения
"""
import asyncio
import sys
from anthropic import AsyncAnthropic
from config import config


client = AsyncAnthropic(api_key=config.anthropic_api_key)

FUNNEL_SYSTEM = f"""Ты — копирайтер и стратег воронок для бренда «{config.brand_name}».
Продукт: AI-бот @Eye888888_bot — диагностика бизнес-блоков за 15 минут.
Стоимость: 3500 ₽ (полный скан).
Аудитория: {config.target_audience}.

Стиль Юлии Ревы: живой, честный, без давления. Экспертность через истории и результаты.
НЕ используй агрессивные продажи. Помогай людям прийти к решению самим.
Каждое сообщение — ценность + мягкое движение к следующему шагу."""

PRODUCT_DESCRIPTION = """
Бот @Eye888888_bot:
- 15-минутный опросник (15 личных + 12 бизнес вопросов)
- AI-анализ через Claude (6 блоков: Архитектура, Слепые зоны, Блоки, Команда, Деньги, Рекомендации)
- Нумерологический анализ по дате рождения
- Конкретные рекомендации, не шаблоны
- Доступно 24/7, результат за 30 секунд после опросника
"""


async def generate_welcome_series() -> str:
    """Серия приветственных сообщений для новых подписчиков."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=1500,
        system=FUNNEL_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Напиши серию из 3 приветственных сообщений для нового подписчика канала.

Продукт: {PRODUCT_DESCRIPTION}

Сообщение 1 (сразу при подписке): Тёплое приветствие, кто такая Юлия, что найдёт здесь подписчик
Сообщение 2 (через 1 день): История или кейс — как кто-то нашёл свой главный блок
Сообщение 3 (через 3 дня): Мини-диагностика в тексте — 3 вопроса, которые заставят задуматься + приглашение попробовать бота БЕСПЛАТНО

Каждое сообщение: 80-120 слов. Оформи как готовый текст для отправки."""
        }]
    )
    return response.content[0].text


async def generate_warmup_series() -> str:
    """Прогревочная серия из 5 сообщений."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=2000,
        system=FUNNEL_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Напиши серию из 5 прогревочных сообщений (рассылка за 1 неделю).

Продукт: {PRODUCT_DESCRIPTION}

Цель: провести человека от «интересно» до «хочу попробовать».

День 1: Боль — почему умные предприниматели застревают (без продаж)
День 2: История клиента — конкретный кейс с результатом (вымышленный, но реалистичный)
День 3: Разрушение мифа — «работать больше» не поможет, если есть блок
День 4: Как работает диагностика — за кулисами бота (вызвать любопытство)
День 5: Социальное доказательство + мягкое приглашение

Каждое сообщение: 100-150 слов. Нумерация и заголовок для каждого."""
        }]
    )
    return response.content[0].text


async def generate_sales_messages() -> str:
    """Продающие сообщения и офферы."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=1500,
        system=FUNNEL_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Напиши 3 варианта продающего сообщения для бота.

Продукт: {PRODUCT_DESCRIPTION}
Цена: 3500 ₽

Вариант А: Рациональный — акцент на конкретику и экономию времени
Вариант Б: Эмоциональный — история трансформации, ощущение «наконец-то понял»
Вариант В: Срочность — ограниченное предложение (например, первые 10 по старой цене)

Для каждого: крючок + суть + цена + CTA.
Длина: 120-180 слов.
Кнопка CTA: «Пройти диагностику» → @Eye888888_bot"""
        }]
    )
    return response.content[0].text


async def generate_objection_handlers() -> str:
    """Ответы на типичные возражения."""
    response = await client.messages.create(
        model=config.content_model,
        max_tokens=1200,
        system=FUNNEL_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Напиши ответы на топ-5 возражений для продукта:
{PRODUCT_DESCRIPTION}
Цена: 3500 ₽

Возражения:
1. «Дорого / нет денег»
2. «Это же бот, а не живой человек — как он может меня понять?»
3. «Я уже проходил диагностики, они не работают»
4. «Нет времени»
5. «Мне нужно подумать»

Для каждого: само возражение + мягкий ответ (без давления, с пониманием) + переформулировка.
Тон: как разговор подруги, которая реально хочет помочь."""
        }]
    )
    return response.content[0].text


async def generate_full_funnel() -> str:
    """Полная воронка с описанием каждого шага."""
    response = await client.messages.create(
        model=config.trends_model,  # Sonnet для стратегии
        max_tokens=2000,
        system=FUNNEL_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Опиши полную воронку продаж для Telegram-канала.

Продукт: {PRODUCT_DESCRIPTION}
Цена: 3500 ₽
Бесплатная версия: мини-скан (5 вопросов, тизер результата)

Создай схему воронки:

ЭТАП 1 — ПРИВЛЕЧЕНИЕ (трафик)
Источники, форматы контента, крючки

ЭТАП 2 — ЗАХВАТ (подписка)
Лид-магнит, первое сообщение, что даём сразу

ЭТАП 3 — ПРОГРЕВ (доверие)
Контент-план на 7 дней, точки касания

ЭТАП 4 — КОНВЕРСИЯ (продажа)
Триггеры, оффер, как преподносить цену

ЭТАП 5 — УДЕРЖАНИЕ (LTV)
Что после покупки, как возвращать

Для каждого этапа: цель, инструменты, метрика успеха.
В конце: KPI всей воронки (конверсия, LTV, CAC)."""
        }]
    )
    return response.content[0].text


async def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python funnel_bot.py welcome     — приветственная серия (3 сообщения)")
        print("  python funnel_bot.py warmup      — прогревочная серия (5 сообщений)")
        print("  python funnel_bot.py sale        — продающие сообщения (3 варианта)")
        print("  python funnel_bot.py objections  — ответы на возражения")
        print("  python funnel_bot.py full        — полная воронка со стратегией")
        return

    cmd = sys.argv[1]

    if cmd == "welcome":
        result = await generate_welcome_series()
        print("\n👋 ПРИВЕТСТВЕННАЯ СЕРИЯ:\n")
        print(result)

    elif cmd == "warmup":
        result = await generate_warmup_series()
        print("\n🔥 ПРОГРЕВОЧНАЯ СЕРИЯ (7 ДНЕЙ):\n")
        print(result)

    elif cmd == "sale":
        result = await generate_sales_messages()
        print("\n💰 ПРОДАЮЩИЕ СООБЩЕНИЯ:\n")
        print(result)

    elif cmd == "objections":
        result = await generate_objection_handlers()
        print("\n🛡 ОТВЕТЫ НА ВОЗРАЖЕНИЯ:\n")
        print(result)

    elif cmd == "full":
        result = await generate_full_funnel()
        print("\n🗺 ПОЛНАЯ ВОРОНКА:\n")
        print(result)

    else:
        print(f"Неизвестная команда: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
