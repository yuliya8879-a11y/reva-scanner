# Агенты продвижения @Eye888888_bot

Автоматизация контент-маркетинга для проекта Юлии Ревой.
Метод: нумерология + 4 уровня блоков + чакры.

---

## Что делает каждый агент

| Файл | Что делает |
|------|-----------|
| `trends_watcher.py` | Собирает тренды в нише, даёт топ-5 тем на неделю |
| `content_generator.py` | Генерирует посты / карусели / Reels через Claude API |
| `telegram_poster.py` | Публикует готовые посты в @bizscanner |
| `run_weekly.py` | Запускает всё сразу — полный недельный цикл |

---

## Быстрый старт

### 1. Настрой .env

В файле `~/reva-scanner/.env` должны быть:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=7...
```

Получить ключи:
- Anthropic API: https://console.anthropic.com/
- Telegram Bot Token: через @BotFather → создай нового бота или используй существующего

> Важно: бот должен быть администратором канала @bizscanner с правом публикации.

### 2. Установи зависимости

```bash
cd ~/reva-scanner
pip install anthropic python-dotenv requests
```

---

## Команды

### Полный недельный цикл (запускай раз в неделю)

```bash
python ~/reva-scanner/agents/run_weekly.py
```

Делает всё автоматически:
1. Собирает тренды
2. Генерирует 3 поста для Telegram
3. Генерирует карусель для Instagram
4. Генерирует Reels-сценарий
5. Сохраняет всё в `~/content/бизнес/НЕДЕЛЯ_[дата].md`

Опции:
```bash
python run_weekly.py --skip-trends          # если тренды уже собраны
python run_weekly.py --topics "деньги,чакры" # дополнительные темы
```

---

### Только тренды

```bash
python ~/reva-scanner/agents/trends_watcher.py
```

Сохраняет в: `~/content/бизнес/ТРЕНДЫ_[дата].md`

Запускай еженедельно, лучше в воскресенье вечером.

---

### Только контент (один пост / карусель / reels)

```bash
# Пост для Telegram/Instagram
python ~/reva-scanner/agents/content_generator.py \
  --type post \
  --topic "блоки в деньгах — нумерологический взгляд"

# Карусель Instagram (10 слайдов)
python ~/reva-scanner/agents/content_generator.py \
  --type carousel \
  --topic "4 типа архетипа предпринимателя"

# Reels-сценарий
python ~/reva-scanner/agents/content_generator.py \
  --type reels \
  --topic "почему бизнес не растёт — 3 скрытых причины"
```

Сохраняет в: `~/content/бизнес/АВТО_[ТИП]_[дата].md`

---

### Публикация в Telegram

```bash
# Опубликовать текст прямо сейчас
python ~/reva-scanner/agents/telegram_poster.py \
  --now "Текст поста..."

# Выбрать пост из недельного плана (интерактивно)
python ~/reva-scanner/agents/telegram_poster.py --schedule

# Выбрать из конкретного файла
python ~/reva-scanner/agents/telegram_poster.py \
  --file ~/content/бизнес/НЕДЕЛЯ_2026-03-29.md
```

---

## Расписание

| Когда | Что запускать |
|-------|--------------|
| Воскресенье, 20:00 | `python run_weekly.py` — полный цикл |
| Понедельник, 09:00 | `telegram_poster.py --schedule` — первый пост |
| Среда, 10:00 | `telegram_poster.py --schedule` — второй пост |
| Пятница, 11:00 | `telegram_poster.py --schedule` — третий пост |
| Вторник–Четверг | Публикуй Instagram посты вручную из файла НЕДЕЛЯ |

---

## Как добавлять идеи в ИДЕИ.md

Открой файл и добавь в раздел "Твои идеи и наработки":

```bash
# Открыть в редакторе
open ~/content/бизнес/ИДЕИ.md
```

Формат для идеи:
```markdown
- [дата] Кейс из сессии: клиент с числом судьбы 8 и блоком "богатые плохие" —
  три года топчется на одном доходе. Интересно написать про это.
```

Агенты читают ИДЕИ.md перед каждой генерацией.

---

## Структура файлов контента

```
~/content/бизнес/
├── ИДЕИ.md                    ← сюда добавляй свои идеи
├── ТРЕНДЫ_2026-03-29.md       ← генерирует trends_watcher.py
├── АВТО_POST_2026-03-29.md    ← генерирует content_generator.py
├── АВТО_CAROUSEL_2026-03-29.md
├── АВТО_REELS_2026-03-29.md
├── НЕДЕЛЯ_2026-03-29.md       ← собирает run_weekly.py
└── ИНСТА_2026-03-29.md        ← создаёт Claude-агент reva-instagram
```

---

## Claude-агенты (в ~/.claude/agents/)

Эти агенты работают через Claude Code — вызывай их в чате:

- **reva-instagram** — карусели, Reels, посты для @biz.architect
- **reva-trends** — исследование трендов интерактивно
- **reva-promo** — стратегия продвижения в Telegram-чатах
- **reva-week** — создать недельный план в диалоге

Пример вызова в Claude Code:
```
Создай карусель на тему "ловушка мастера"
```
(Claude автоматически использует агент reva-instagram)

---

## Устранение проблем

### "ANTHROPIC_API_KEY не найден"
Проверь файл `~/reva-scanner/.env` — ключ должен быть там.

### "TELEGRAM_BOT_TOKEN не найден"
То же самое — проверь `.env`. Убедись что бот — администратор @bizscanner.

### Пост опубликован с ошибкой форматирования
Проверь что в тексте нет незакрытых HTML-тегов.
Telegram принимает: `<b>`, `<i>`, `<code>`, `<a href="">`.

### run_weekly.py завис
Таймаут каждого шага — 2 минуты. Если завис — Ctrl+C и запусти нужный скрипт отдельно.

---

## Связь и поддержка

Проект Юлии Ревой — @Eye888888_bot
По вопросам: @Reva_Yulya6
