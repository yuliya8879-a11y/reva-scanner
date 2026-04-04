# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

**@Eye888888_bot** — AI бизнес-сканер «Глаз Бога». Telegram-бот принимает дату рождения и запрос пользователя → генерирует структурированный разбор через Claude API по авторскому алгоритму Юлии Ревой.

**Продукты:** мини-скан 590₽ / личный разбор 3500₽ / бизнес-разбор 10000₽

## Команды

```bash
# Локальный запуск (polling mode, без сервера)
cd ~/reva-scanner
python run_polling.py

# Тесты
pytest
pytest tests/test_numerology.py          # один файл
pytest -k "test_full_scan"               # по имени

# Миграции
alembic upgrade head                     # применить все
alembic revision -m "описание"          # создать новую

# Проверка синтаксиса всех py-файлов
python3 -c "
import ast, os
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try: ast.parse(open(path).read())
            except SyntaxError as e: print(path, e)
"
```

## Деплой

**Production:** Render (webhook mode) — автодеплой при `git push origin main`.

```bash
git add <files>
git commit -m "feat/fix: описание"
git push origin main   # → Render деплоит автоматически
```

Render запускает: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Локально** — `run_polling.py` (polling). **Никогда не запускать оба одновременно** — TelegramConflictError.

## Архитектура

### Два режима работы
- **Production (Render):** `app/main.py` — FastAPI + webhook `/webhook/telegram`
- **Local dev:** `run_polling.py` — aiogram polling с DbSessionMiddleware

### Поток обработки запроса
```
Telegram → webhook/polling → Dispatcher → main_router → handler → session(DB) → response
```

### Порядок роутеров (важен!)
`app/bot/router.py` подключает в строгом порядке:
1. `admin` — /stats, /broadcast, управление пользователями
2. `start` — /start, about_method, restart_bot, **accept_terms** (оферта)
3. `mini_scan` — мини-скан 590₽
4. `payment` — **перед full_scan** — перехватывает `buy:*` callbacks
5. `full_scan` — FSM анкета q0-q14, генерация разбора
6. `session` — request_session callback
7. `feedback` — **последним** — catch-all для свободного текста

### База данных
PostgreSQL async через SQLAlchemy. Сессия инжектируется в хендлеры через middleware.
Миграции: `alembic/versions/` — нумеруются `0001_`, `0002_`, ... `0006_`.

**Модели:**
- `User` — telegram_id, subscription_until, birth_date, **terms_accepted** (новое, миграция 0006)
- `Scan` — scan_type (personal/business/mini), status (collecting/completed/failed), answers (JSONB), report (JSONB)
- `Payment` — привязан к Scan, telegram_charge_id

### AI и алгоритм
**`app/services/algorithm.py`** — центральный модуль. Все правки метода — сюда.
- `PERSONAL_ALGORITHM_BLOCK` — для мини-скана и личного разбора (импортирует `ai_service.py`)
- `BUSINESS_ALGORITHM_BLOCK` — для бизнес-разбора (импортирует `full_scan_ai_service.py`)
- Блоки собираются из констант: MISSION, CONSENT_LAW, SCAN_PRINCIPLE, NUMEROLOGY_ALGORITHM, AXES_AND_SECTORS, PATTERNS_AND_IMPRINTS, LEVEL_CHAIN, BUSINESS_MATRIX_SYSTEM и др.
- `SCAN_PRINCIPLE` содержит «Режим считывания поля» — частота, триада Отец/Мать/Сын, программы

**`app/services/ai_client.py`** — умный Anthropic клиент:
- Два ключа с автопереключением при исчерпании
- Ключи хранятся в `api_keys.json` (не в git), fallback в `.env`
- Управление из бота через `/api`

**`app/services/full_scan_ai_service.py`** — генерация 6-блочного разбора:
- `_PERSONAL_SYSTEM_PROMPT` + `PERSONAL_ALGORITHM_BLOCK` (appended после определения)
- `_BUSINESS_SYSTEM_PROMPT` + `BUSINESS_ALGORITHM_BLOCK` (appended после определения)
- Ответ Claude парсится как JSON, fallback через поиск `{...}`

### FSM анкета
`app/bot/states.py` — `FullScanStates`: q0-q14, completing.
`app/bot/questions.py` — `PERSONAL_QUESTIONS` (2 вопроса), `BUSINESS_QUESTIONS` (15 вопросов).

Ключевой момент: `state.clear()` вызывается **после** `generate_and_deliver_report`, не до.

### Оплата
- **YooKassa** (`app/services/yookassa_service.py`) — если настроена → ссылка на оплату
- **Ручной режим** — уведомление Юлии с кнопкой `quick_grant:` для мгновенной выдачи
- Webhook: `POST /webhook/yookassa` в `app/main.py`
- После оплаты: пользователь получает кнопку `resume_scan:{scan_id}`

### Оферта и согласие
При первом `/start` нового пользователя: показывается оферта → кнопка «Принимаю» → `user.terms_accepted = True` → открывается меню. Без принятия оферты бот не работает.

## Переменные окружения (.env)

```
TELEGRAM_BOT_TOKEN
ANTHROPIC_API_KEY
ANTHROPIC_API_KEY_2        # резервный, автопереключение
DATABASE_URL               # postgresql://...
ADMIN_TELEGRAM_ID          # Telegram ID Юлии — 6343753763
WEBHOOK_BASE_URL           # https://reva-scanner.onrender.com
WEBHOOK_SECRET
YOOKASSA_SHOP_ID           # 515115
YOOKASSA_SECRET_KEY
YOOKASSA_TEST_MODE         # true/false
```

## Версионирование алгоритма

`algorithms/` — датированные файлы с описанием изменений метода:
- `2026-04-03_v2_ФИНАЛЬНЫЙ_ПРОМТ.md` — оси/секторы, паттерны, вторичные выгоды
- `2026-04-03_v3_БИЗНЕС_СИСТЕМА.md` — матрица 144 точки, триада, 6 срезов

`METHOD.md` — актуальное описание метода. Правки метода: сначала в METHOD.md → потом в algorithm.py.
