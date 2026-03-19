# Phase 1: Foundation - Research

**Researched:** 2026-03-19
**Domain:** aiogram 3 + FastAPI webhook + SQLAlchemy async + Alembic + Railway deployment
**Confidence:** HIGH (core patterns verified against official docs and PyPI)

---

## Summary

Phase 1 builds the deployable skeleton that every later phase extends. It has three distinct concerns: (1) a working Telegram bot reachable via webhook on a live Railway URL, (2) a complete PostgreSQL schema with Alembic migrations, and (3) user auto-registration on /start. All three must be production-ready from the start — this is not a prototype, it is the foundation.

The critical architectural decision (already locked in STATE.md) is to run aiogram and FastAPI in one process. The bot registers its webhook path as a FastAPI route; uvicorn handles everything. This avoids two Railway services and two Dockerfiles. The pattern is straightforward: incoming Telegram updates arrive at a POST route, are validated as `aiogram.types.Update` objects, and fed into the dispatcher via `await dp.feed_update(bot, update)`.

Alembic must be configured with the `-t async` template from day 1 because SQLAlchemy 2.x async sessions are incompatible with Alembic's default synchronous `env.py`. The async template uses `run_sync()` inside an async connection to execute migrations — this is the only supported pattern.

**Primary recommendation:** Use the manual FastAPI integration pattern (feed_update) rather than the aiohttp-native `SimpleRequestHandler`, since SimpleRequestHandler is aiohttp-specific and does not apply to FastAPI.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BOT-01 | User sends /start and receives a welcome message describing the scanner | aiogram Router + CommandStart filter; auto-create user row in handler |
| DB-01 | System saves user profile (telegram_id, name, birth_date, created_at) | `users` table in schema; UserService.get_or_create() called from /start handler |
| DB-02 | System saves scan history (questions, answers, report, date) | `scans` table with JSONB columns; created in later phases but schema must exist in Phase 1 |
| DB-03 | System saves payment status for each scan | `payments` table linked to scans; schema must exist in Phase 1 even if unpopulated |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Async mature, required by aiogram 3.x (supports >=3.10) |
| aiogram | 3.26.0 | Telegram bot framework | Latest stable (released 2026-03-02); FSM-first, async-native |
| FastAPI | 0.135.1 | ASGI app + webhook receiver | Latest stable (released 2026-03-01); async-native, Pydantic v2 |
| uvicorn | 0.42.0 | ASGI server | Latest stable (released 2026-03-16); runs FastAPI in production |
| SQLAlchemy | 2.0.48 | ORM (async mode) | Latest stable (released 2026-03-02); async engine is first-class in 2.x |
| asyncpg | 0.31.0 | PostgreSQL async driver | Latest stable (released 2025-11-24); fastest Python async Postgres driver |
| Alembic | 1.18.4 | DB migrations | Latest stable (released 2026-02-10); official SQLAlchemy migration tool |
| pydantic-settings | 2.13.1 | Config validation | Latest stable (released 2026-02-19); validates env vars at startup |
| python-dotenv | 1.0.x | Local .env loading | Standard local dev pattern; pydantic-settings reads it automatically |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Test runner | All test execution |
| pytest-asyncio | 0.23+ | Async test support | Testing async handlers and DB operations |
| httpx | 0.27+ | HTTP client + test client | Testing FastAPI routes (AsyncClient) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual feed_update in FastAPI | SimpleRequestHandler | SimpleRequestHandler is aiohttp-only; does not integrate with FastAPI |
| Manual feed_update in FastAPI | aiogram-fastapi-server (3rd party) | Extra dependency with thin value; manual approach is 10 lines and well understood |
| SQLAlchemy 2.x async | Tortoise ORM | Less documentation, fewer Alembic equivalents |
| asyncpg | psycopg3 | asyncpg is faster and has broader SQLAlchemy 2.x async ecosystem coverage |

**Installation:**
```bash
pip install aiogram==3.26.0 fastapi==0.135.1 "uvicorn[standard]==0.42.0" \
  "sqlalchemy[asyncio]==2.0.48" asyncpg==0.31.0 alembic==1.18.4 \
  pydantic-settings==2.13.1 python-dotenv httpx pytest pytest-asyncio
```

**Version note:** Versions above verified against PyPI on 2026-03-19.

---

## Architecture Patterns

### Recommended Project Structure

```
reva-scanner/
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py              # async-configured
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── main.py             # FastAPI app + lifespan
│   ├── config.py           # pydantic-settings Settings
│   ├── database.py         # engine, session factory, Base
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── scan.py
│   │   ├── payment.py
│   │   └── content_queue.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── router.py       # main router aggregating all sub-routers
│   │   └── handlers/
│   │       └── start.py    # /start handler + user auto-creation
│   └── services/
│       └── user_service.py # get_or_create user logic
└── tests/
    ├── conftest.py
    └── test_webhook.py
```

### Pattern 1: FastAPI + aiogram 3 Webhook Integration

**What:** FastAPI lifespan registers the webhook on startup and deletes it on shutdown. A POST route receives Telegram updates, validates them as aiogram Update objects, and feeds them to the dispatcher.

**When to use:** Always — this is the single-process design locked in STATE.md.

**Example:**
```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from app.config import settings
from app.bot.router import router as bot_router

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
dp.include_router(bot_router)

WEBHOOK_PATH = "/webhook/telegram"

@asynccontextmanager
async def lifespan(app: FastAPI):
    webhook_url = f"{settings.webhook_base_url}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.webhook_secret:
        return {"ok": False}
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
```

**Source:** Verified against aiogram docs and Habr article pattern (2025).

### Pattern 2: SQLAlchemy 2.x Async Engine + Session Factory

**What:** Create a single async engine and session factory at module level. Provide a `get_db_session` async generator for FastAPI dependency injection.

**When to use:** All database access throughout the application.

```python
# app/database.py
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

engine = create_async_engine(
    settings.database_url,  # must use postgresql+asyncpg:// scheme
    echo=False,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

**Source:** Verified against berkkaraal.com guide (September 2024) and official SQLAlchemy 2.x docs.

### Pattern 3: Alembic Async Configuration

**What:** Initialize Alembic with the async template, set `sqlalchemy.url` dynamically in `env.py`, import all models so autogenerate works.

**When to use:** Migrations setup in Phase 1 Wave 0.

```bash
# Init with async template (run once)
alembic init -t async alembic
```

```python
# alembic/env.py (key modifications only)
from app.config import settings
from app.database import Base
# CRITICAL: import all models so their tables appear in metadata
from app.models import user, scan, payment, content_queue  # noqa: F401

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

```ini
# alembic.ini — leave sqlalchemy.url blank (set dynamically in env.py)
sqlalchemy.url =
```

**Generate and run migration:**
```bash
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

**Source:** Verified against Alembic official cookbook and berkkaraal.com guide.

### Pattern 4: pydantic-settings Config

**What:** Centralize all settings in a `Settings` class that validates at startup. Fails fast on missing secrets.

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str
    webhook_base_url: str       # https://your-app.railway.app
    webhook_secret: str         # random 32-char string
    database_url: str           # postgresql+asyncpg://...
    anthropic_api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

**Note:** `model_config = SettingsConfigDict(...)` is the pydantic-settings v2 syntax. The old `class Config:` inner class is deprecated in v2.

### Pattern 5: User Auto-Creation on /start

**What:** /start handler looks up user by telegram_id, creates if not found, returns existing record. Idempotent.

```python
# app/bot/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user = await UserService.get_or_create(
        session=session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await message.answer(
        "Привет! Я Глаз Бога — AI-сканер вашего бизнеса.\n\n"
        "За 15 минут я найду:\n"
        "• Где утекают деньги\n"
        "• Слепые зоны\n"
        "• Где вы сами тормозите\n\n"
        "Напишите /scan чтобы начать."
    )
```

**How to inject session into aiogram handlers:** Pass the session factory as middleware data or use aiogram's dependency injection. The cleanest approach for Phase 1 is to add the session factory to dispatcher's data at startup and retrieve it in handlers via a middleware:

```python
# In lifespan, add session factory to dispatcher data:
dp["session_factory"] = async_session_factory

# In handler, receive it:
async def cmd_start(message: Message, session_factory):
    async with session_factory() as session:
        user = await UserService.get_or_create(session, ...)
```

### Pattern 6: Dockerfile for Railway

**What:** Single-stage Python 3.12-slim Dockerfile. Railway injects `$PORT` at runtime via environment variable. CMD must use shell form so `$PORT` expands.

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Shell form (not exec form) so $PORT expands
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Railway environment variables to set in dashboard:**
```
TELEGRAM_BOT_TOKEN=
WEBHOOK_BASE_URL=https://your-service-name.railway.app
WEBHOOK_SECRET=<random 32-char string>
DATABASE_URL=postgresql+asyncpg://${{PGUSER}}:${{PGPASSWORD}}@${{PGHOST}}:${{PGPORT}}/${{PGDATABASE}}
ANTHROPIC_API_KEY=
```

**Railway DATABASE_URL note:** Railway provides `DATABASE_URL` automatically for the PostgreSQL plugin, but it uses the `postgresql://` scheme (psycopg2). You must either override it with `postgresql+asyncpg://` prefix or construct it manually from Railway's individual `${{PG*}}` variables. Set your own `DATABASE_URL` variable with the asyncpg prefix to avoid confusion.

**Source:** Verified via Railway docs on Dockerfiles and community help station posts.

### Anti-Patterns to Avoid

- **Using `SimpleRequestHandler` with FastAPI:** SimpleRequestHandler lives in `aiogram.webhook.aiohttp_server` and is aiohttp-specific. It does not work with FastAPI. Use the manual `dp.feed_update(bot, update)` pattern instead.
- **Using `@app.on_event("startup")`:** This is deprecated in FastAPI since 0.95.0. Use the `lifespan` asynccontextmanager pattern.
- **Using polling in production:** `dp.start_polling()` conflicts with Railway's process model and doesn't work with the webhook-only architecture. Never use it.
- **Skipping the asyncpg prefix in DATABASE_URL:** Railway's default `DATABASE_URL` uses `postgresql://` (psycopg2 scheme). SQLAlchemy async engine requires `postgresql+asyncpg://`. These are not interchangeable — asyncpg will refuse to connect with the wrong prefix.
- **Empty `target_metadata` in env.py:** If models are not imported in `alembic/env.py`, autogenerate produces empty migrations. Always import all model modules explicitly.
- **Exec form CMD for $PORT:** `CMD ["uvicorn", "app.main:app", "--port", "$PORT"]` will NOT expand `$PORT`. Must use shell form: `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Webhook secret validation | Custom HMAC verification | `secret_token` parameter in `bot.set_webhook()` + header check | Telegram sends `X-Telegram-Bot-Api-Secret-Token` header automatically |
| Update deserialization | Manual JSON → dict mapping | `Update.model_validate(json, context={"bot": bot})` | aiogram handles all Telegram API type complexity |
| DB migration state tracking | Manual schema version table | Alembic | Handles rollbacks, dependencies, autogenerate |
| Env var validation | Try/except on os.environ.get | pydantic-settings `BaseSettings` | Validates types, provides defaults, fails fast with clear errors |
| Async session lifecycle | Manual try/finally | `async with async_session_factory() as session` | asynccontextmanager handles commit/rollback/close |

**Key insight:** The aiogram + FastAPI integration surface is small (one POST route, one lifespan function). Do not over-engineer this. The complexity lives in handlers, not the webhook plumbing.

---

## Common Pitfalls

### Pitfall 1: Railway DATABASE_URL scheme mismatch

**What goes wrong:** `asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress` or `sqlalchemy.exc.ArgumentError: Could not parse rfc1738 URL from string` on deployment.

**Why it happens:** Railway's auto-provisioned `DATABASE_URL` uses the `postgresql://` scheme. asyncpg requires `postgresql+asyncpg://`. SQLAlchemy tries to use psycopg2 (not installed), crashes.

**How to avoid:** In Railway dashboard, create a separate env var `DATABASE_URL_ASYNC` constructed as `postgresql+asyncpg://...` from Railway's `${{PGUSER}}`, `${{PGPASSWORD}}`, `${{PGHOST}}`, `${{PGPORT}}`, `${{PGDATABASE}}` variables. Or transform in `config.py`:
```python
@property
def database_url_async(self) -> str:
    return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
```

**Warning signs:** Import error mentioning psycopg2, or "can't find driver" at startup.

### Pitfall 2: Webhook not set on Railway but set locally

**What goes wrong:** Bot responds in local dev (if using polling) but not on Railway. Or webhook is registered to localhost, which Telegram can't reach.

**Why it happens:** `WEBHOOK_BASE_URL` points to localhost or is missing. Telegram tries to POST to an unreachable URL.

**How to avoid:** Always set `WEBHOOK_BASE_URL` to the actual Railway public domain (e.g., `https://reva-scanner-production.up.railway.app`). Verify webhook is registered: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`.

**Warning signs:** `getWebhookInfo` shows `url: ""` or a localhost URL. Bot ignores all messages in production.

### Pitfall 3: Alembic autogenerate produces empty migrations

**What goes wrong:** `alembic revision --autogenerate` generates a migration with empty `upgrade()` and `downgrade()` functions. Running `alembic upgrade head` creates no tables.

**Why it happens:** Model files are not imported in `alembic/env.py`. Python never executes the `Table(...)` or `class User(Base)` definitions, so `Base.metadata` is empty.

**How to avoid:** In `alembic/env.py`, explicitly import every model module:
```python
from app.models import user, scan, payment, content_queue  # noqa: F401
```
This must happen before `target_metadata = Base.metadata`.

**Warning signs:** Migration file shows `def upgrade() -> None: pass`. Tables don't exist after `upgrade head`.

### Pitfall 4: `$PORT` not expanding in Dockerfile CMD

**What goes wrong:** Container starts but Railway health check fails — service unreachable on the expected port.

**Why it happens:** Exec form `CMD ["uvicorn", ..., "$PORT"]` passes the literal string `$PORT` to uvicorn, not the environment variable value. uvicorn tries to bind to port named `$PORT` and crashes.

**How to avoid:** Use shell form CMD:
```dockerfile
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Warning signs:** Deploy logs show `ValueError: invalid literal for int() with base 10: '$PORT'`.

### Pitfall 5: `model_config` vs `class Config` in pydantic-settings v2

**What goes wrong:** `DeprecationWarning` about `class Config` being deprecated, or settings fail to load `.env` file.

**Why it happens:** pydantic-settings v2 replaced the inner `class Config` with `model_config = SettingsConfigDict(...)`. Old tutorials use the v1 syntax.

**How to avoid:** Use v2 syntax:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
```

### Pitfall 6: Session not closed after exceptions in handler

**What goes wrong:** Connection pool exhaustion after a few errors. Bot stops responding.

**Why it happens:** If an exception occurs inside a manually managed `async with session_factory() as session:` block and the exception is caught at a higher level, the session may not be properly closed.

**How to avoid:** Always use `async with` for sessions — SQLAlchemy's asynccontextmanager handles rollback and close on exception automatically. Never store sessions as module-level globals.

---

## Database Schema

Exact table definitions for Phase 1 migration. These are the canonical definitions — all later phases extend, never recreate.

```python
# app/models/user.py
import datetime
from sqlalchemy import BigInteger, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[datetime.date | None] = mapped_column(nullable=True)  # set in Phase 2
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

```python
# app/models/scan.py
import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
import enum
from app.database import Base

class ScanStatus(str, enum.Enum):
    collecting = "collecting"
    processing = "processing"
    complete = "complete"
    failed = "failed"

class ScanType(str, enum.Enum):
    mini = "mini"
    full = "full"

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[ScanType] = mapped_column(String(10), default=ScanType.full)
    status: Mapped[ScanStatus] = mapped_column(String(20), default=ScanStatus.collecting)
    questionnaire_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    free_text: Mapped[str | None] = mapped_column(nullable=True)
    social_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

```python
# app/models/payment.py
import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(20))  # "stars" | "yukassa"
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)       # Stars or kopeks
    currency: Mapped[str] = mapped_column(String(10))  # "XTR" or "RUB"
    type: Mapped[str] = mapped_column(String(20))      # "scan" | "subscription"
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|paid|failed
    paid_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

```python
# app/models/content_queue.py
import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ContentQueue(Base):
    __tablename__ = "content_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(30))          # "post" | "reels_script" | "content_plan"
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    posted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|ready|posted|failed
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Note on circular FK:** `scans.payment_id` references `payments.id` and `payments.scan_id` references `scans.id`. This creates a circular dependency in Alembic. The safest resolution: define both FKs but add one of them (e.g., `scans.payment_id`) as nullable with `use_alter=True` in the migration, or simply add it in a second migration after both tables exist.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 creates it |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-01 | POST /webhook/telegram with /start update returns 200 and sends welcome message | integration | `pytest tests/test_webhook.py::test_start_command -x` | Wave 0 |
| DB-01 | UserService.get_or_create creates user row on first call, returns same row on second call | unit | `pytest tests/test_user_service.py::test_get_or_create -x` | Wave 0 |
| DB-02 | `scans` table exists with correct columns after `alembic upgrade head` | smoke | `pytest tests/test_migrations.py::test_scans_table_exists -x` | Wave 0 |
| DB-03 | `payments` table exists with correct columns after `alembic upgrade head` | smoke | `pytest tests/test_migrations.py::test_payments_table_exists -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps

- [ ] `tests/conftest.py` — async test DB session fixture, test bot/dispatcher setup
- [ ] `tests/test_webhook.py` — covers BOT-01
- [ ] `tests/test_user_service.py` — covers DB-01
- [ ] `tests/test_migrations.py` — covers DB-02, DB-03 (checks tables exist via asyncpg inspection)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` with `asyncio_mode = "auto"`
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` asynccontextmanager | FastAPI 0.95.0 (April 2023) | Old decorator still works but triggers DeprecationWarning |
| `class Config:` in BaseSettings | `model_config = SettingsConfigDict(...)` | pydantic-settings v2 (2023) | Old syntax deprecated, will break in future versions |
| `alembic init alembic` | `alembic init -t async alembic` | Alembic 1.7+ | Without `-t async`, env.py is synchronous and incompatible with async engines |
| `dp.start_polling()` | Webhook via FastAPI | aiogram 3.x standard | Polling is valid for dev but wrong for Railway deployment |
| `Session.execute(...)` synchronous | `async with session: await session.execute(...)` | SQLAlchemy 2.0 async (2023) | Sync session in async context causes `MissingGreenlet` error |

**Deprecated/outdated:**
- `from aiogram.webhook.aiohttp_server import SimpleRequestHandler`: Only works with aiohttp, not FastAPI.
- `Bot(token=..., parse_mode=...)`: Deprecated in aiogram 3.x. Use `DefaultBotProperties(parse_mode=...)` instead.

---

## Open Questions

1. **Circular FK between scans and payments**
   - What we know: Both tables reference each other; Alembic may struggle with autogenerate ordering.
   - What's unclear: Whether Alembic 1.18.x handles this gracefully with `use_alter=True`.
   - Recommendation: Add `scans.payment_id` FK in a second migration or use `use_alter=True`. Keep `payments.scan_id` as the primary FK in the first migration.

2. **aiogram session injection pattern**
   - What we know: aiogram 3.x supports middleware and `dp.workflow_data` for passing dependencies to handlers.
   - What's unclear: Whether passing `session_factory` through dispatcher data vs. a dedicated middleware is cleaner for this project's scale.
   - Recommendation: Start with `dp["session_factory"] = async_session_factory` in lifespan, retrieve in handlers directly. Add proper middleware if/when it becomes repetitive in Phase 2+.

3. **Railway PORT handling for Alembic migrations**
   - What we know: Alembic runs as a CLI command, not as an HTTP server; doesn't need PORT.
   - What's unclear: Whether to run migrations as part of the Dockerfile CMD or as a separate Railway "deploy command".
   - Recommendation: Add `alembic upgrade head` to a Railway release command (`railway.json` `"deploymentOverlapSeconds"` section) so migrations run before the new container starts serving traffic.

---

## Sources

### Primary (HIGH confidence)

- [aiogram 3.26.0 docs — Webhook](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html) — confirmed webhook patterns, `dp.feed_update`, `set_webhook` params
- [PyPI: aiogram 3.26.0](https://pypi.org/project/aiogram/) — version and release date verified 2026-03-19
- [PyPI: FastAPI 0.135.1](https://pypi.org/project/fastapi/) — version verified 2026-03-19
- [PyPI: SQLAlchemy 2.0.48](https://pypi.org/project/sqlalchemy/) — version verified 2026-03-19
- [PyPI: asyncpg 0.31.0](https://pypi.org/project/asyncpg/) — version verified 2026-03-19
- [PyPI: Alembic 1.18.4](https://pypi.org/project/alembic/) — version verified 2026-03-19
- [PyPI: uvicorn 0.42.0](https://pypi.org/project/uvicorn/) — version verified 2026-03-19
- [PyPI: pydantic-settings 2.13.1](https://pypi.org/project/pydantic-settings/) — version verified 2026-03-19

### Secondary (MEDIUM confidence)

- [Habr: aiogram 3.x webhook with FastAPI](https://habr.com/ru/articles/819955/) — community article, patterns cross-verified against official docs
- [berkkaraal.com: FastAPI + async SQLAlchemy 2 + Alembic + Docker (Sep 2024)](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/) — async env.py pattern, naming conventions
- [Railway docs: Dockerfiles](https://docs.railway.com/builds/dockerfiles) — PORT handling, shell vs exec form
- [Railway help: uvicorn on Railway](https://station.railway.com/questions/run-a-uvicorn-python-app-on-railway-0181b041) — $PORT expansion confirmed

### Tertiary (LOW confidence)

- Training data (aiogram FSM patterns, SQLAlchemy async session best practices) — used for code structure recommendations not explicitly verified via web sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI on 2026-03-19
- Architecture: HIGH — webhook pattern verified against aiogram docs and community articles
- Database schema: HIGH — standard SQLAlchemy 2.x mapped_column syntax, columns derived from ARCHITECTURE.md
- Alembic setup: HIGH — `alembic init -t async` confirmed as the correct approach
- Railway deployment: MEDIUM — verified via docs but Railway UI/config can change; verify PORT and DATABASE_URL in actual deploy
- Pitfalls: HIGH — most verified by actual error messages documented in search results

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable ecosystem; aiogram/FastAPI/SQLAlchemy versions may update but patterns won't change)
