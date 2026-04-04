# REVA MENTOR — Юлия Рева / @Eye888888_bot

## Что это
Личный бренд Юлии Ревы. Бот-сканер @Eye888888_bot для диагностики бизнес-блоков.
Продвижение через @Reva_mentor (Telegram), Instagram, TikTok.

## Стек
- Python + Claude API (контент, воронки, тренды)
- Telegram Bot API (@Eye888888_bot)
- Канал: @Reva_mentor

## Структура
```
agents/
  content_bot.py   — посты, рилс, контент-план
  funnel_bot.py    — автоворонка welcome→warmup→sale
  trends_bot.py    — тренды, конкуренты, инсайты
config.py          — настройки бренда и API
skills/            — команды Claude
templates/         — шаблоны контента
```

## Запуск агентов
```bash
cd ~/REVA-MENTOR
export ANTHROPIC_API_KEY="..."
python3 agents/content_bot.py post "тема"
python3 agents/funnel_bot.py welcome
python3 agents/trends_bot.py analyze
```

## Голос бренда
- Живой, честный, без давления
- От первого лица (Юлия говорит сама)
- Экспертность через истории, не через регалии
- НЕ агрессивные продажи

## Правила
- НЕ смешивать с AGRO-HUB
- Маркетинговые находки из агро можно адаптировать сюда
- Все новые агенты кладём в agents/
- Секреты только в .env — не в коде

## Ошибки
- Если anthropic не импортируется: `pip install anthropic`
- Если нет ключа: проверь .env или export ANTHROPIC_API_KEY
