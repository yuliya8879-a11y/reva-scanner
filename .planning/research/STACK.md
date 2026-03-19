# Technology Stack: Reva Scanner

**Project:** AI Business Scanner — Telegram bot + web cabinet
**Researched:** 2026-03-19
**Knowledge cutoff:** August 2025
**Web tools available:** None (WebSearch and WebFetch denied; Brave API key not set)
**Confidence method:** Training data rated HIGH only for libraries that were stable and mature by mid-2025 with long track records

---

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Backend language | Async support is mature; aiogram 3.x, anthropic SDK, asyncpg all have excellent Python support; faster than 3.11 for async workloads |
| Node.js | 20 LTS | Next.js runtime only | Next.js requires Node; 20 LTS is the stable choice for 2025 |

**Why Python over Node.js for the backend:** aiogram (Telegram bot framework) is Python-native and significantly more mature than Node.js alternatives (telegraf, node-telegram-bot-api) for FSM-heavy bots. The Python data ecosystem (numerology math, text processing) is richer. The Anthropic SDK is first-class in Python. Node.js is used only for Next.js web app.

---

### Telegram Bot Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **aiogram** | **3.x** (3.7+ as of mid-2025) | Telegram bot framework | Recommended choice — see rationale below |

**Rationale for aiogram 3.x over alternatives:**

- **vs python-telegram-bot (PTB):** PTB 20.x is async but its API surface is callback-heavy and less ergonomic. aiogram 3.x uses a router/middleware pattern that scales better as handler count grows. FSM (Finite State Machine) in aiogram 3 is first-class via `StatesGroup`; in PTB it's bolted on via `ConversationHandler` which becomes unwieldy past 5 states.
- **vs Telegraf (Node.js):** Different language ecosystem; would require maintaining Node.js backend alongside Python, splitting AI/payment logic.
- **vs pyTelegramBotAPI (telebot):** Synchronous-only or half-async; not suitable for production bots that call external APIs (Claude, ЮKassa).

**aiogram 3.x key capabilities needed:**
- Async webhook handling — essential for FastAPI integration
- `FSMContext` + `StatesGroup` — questionnaire flow across 12-15 states
- Router-based handler registration — organizes handlers by feature
- Middleware — for user authentication, logging, rate limiting
- `InlineKeyboard` and `ReplyKeyboard` builders — button-driven UX

**Confidence:** HIGH — aiogram 3 has been the de facto standard for Python Telegram bots since 2023; FSM architecture is well-documented and production-tested.

---

### Web Framework (Backend API)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **FastAPI** | **0.111+** | REST API for web cabinet + webhook receiver | First-class async, automatic OpenAPI docs, Pydantic integration |
| **uvicorn** | **0.29+** | ASGI server | Standard uvicorn for FastAPI in production |
| **Pydantic** | **v2** (2.x) | Data validation and report schema | v2 is 5-50x faster than v1; FastAPI 0.100+ ships with Pydantic v2 by default |

**Why FastAPI over Django/Flask:**
- **vs Django:** Django is synchronous by default (async ORM is incomplete); overkill admin and auth machinery not needed here; heavier startup time.
- **vs Flask:** Flask async is an afterthought; no built-in data validation; would need marshmallow or manually wire Pydantic.
- FastAPI is the right tool: async-native, Pydantic for report schemas, OpenAPI for Next.js client generation.

**Why FastAPI also handles the Telegram webhook:**
Single process design (see ARCHITECTURE.md) — bot webhook arrives at `/webhook/telegram` route on FastAPI, saving the need for a separate bot polling process. Simpler deployment, shared DB connections.

**Confidence:** HIGH — FastAPI + uvicorn + Pydantic v2 is the dominant Python async stack as of 2025.

---

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **PostgreSQL** | **16** | Primary database | Required per project spec; JSONB for report storage; reliable |
| **SQLAlchemy** | **2.x** (async) | ORM | Async-native in 2.x; works with asyncpg; Alembic migrations |
| **asyncpg** | **0.29+** | PostgreSQL async driver | Fastest Python async Postgres driver; used under SQLAlchemy async engine |
| **Alembic** | **1.13+** | DB migrations | Standard SQLAlchemy migration tool; schema versioning from day 1 |

**Why SQLAlchemy 2.x over alternatives:**
- **vs Tortoise ORM:** Less ecosystem; fewer StackOverflow answers; harder to debug.
- **vs raw asyncpg:** Writing raw SQL is fine, but Alembic requires a SQLAlchemy model layer anyway for migrations. Use both.
- SQLAlchemy 2.x `async_session` + asyncpg is the production-proven pattern for FastAPI.

**Redis** (optional, Phase 1 can skip):
- If aiogram FSM storage needs persistence across restarts, use `RedisStorage` from aiogram-storage.
- For initial launch: `MemoryStorage` is acceptable while user count is low. Add Redis when Railway budget allows ($2-5/mo add-on).
- Celery (if used for task queue) also requires Redis; defer until Phase 3+.

**Confidence:** HIGH for PostgreSQL + SQLAlchemy 2.x + asyncpg. MEDIUM for Redis deferral (depends on launch traffic).

---

### AI Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **anthropic** (Python SDK) | **0.25+** | Claude API client | Official Anthropic SDK; async client available; streaming support |
| **Claude claude-sonnet-4-5** | latest | Report generation | Best cost-quality tradeoff for long-form structured analysis |
| **Claude Haiku** | latest | Mini-scan / content gen | Fast, cheap for high-volume or low-stakes calls |

**Model selection rationale:**

- **claude-sonnet-4-5 for full reports:** Produces nuanced, specific, structured analysis. A full scan report (800-1500 words with structured sections) requires Sonnet quality. Cost per report: approximately $0.15-0.40 USD at Sonnet pricing — acceptable at 3500₽ price point.
- **Claude Haiku for mini-scan and content generation:** Mini-scan teaser (3-4 sentences) and TG channel posts do not require Sonnet quality. Haiku is 10-20x cheaper. Use Haiku for anything under 500-word output where creativity > precision is acceptable.
- **Do NOT use claude-opus-4-5 by default:** Opus is 3-5x more expensive than Sonnet with marginal quality uplift for structured business analysis. Reserve for edge-case prompt debugging only.

**Async SDK usage:**
```python
import anthropic

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

response = await client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}]
)
```

**Structured output strategy:** Claude does not have a native JSON mode (unlike GPT-4). Use prompt engineering with explicit JSON schema in the prompt + Pydantic parsing of the response. Pattern:
```
"Return your analysis as JSON matching this schema: {...}
Respond with ONLY the JSON object, no other text."
```
Add retry logic for the rare case Claude wraps JSON in markdown fences.

**Confidence:** HIGH for SDK integration pattern. MEDIUM for specific model version names (model IDs change; verify current names in Anthropic docs before implementation).

---

### Payment Processing

#### Option A: ЮKassa (YooKassa)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **yookassa** (Python SDK) | **3.x** | ЮKassa payment creation and webhook handling | Official SDK; handles HMAC webhook verification |
| ЮKassa REST API | v3 | Payment provider | Primary Russian payment gateway; supports cards, SBP, wallets |

**ЮKassa integration flow:**
1. Backend calls `Payment.create()` with amount, description, return URL
2. ЮKassa returns `payment_url` — bot sends this to user as button
3. User pays on ЮKassa page (handles 3DS, SBP, etc.)
4. ЮKassa sends webhook POST to `FastAPI /webhooks/yukassa`
5. Backend validates HMAC signature, updates payment status in DB
6. Bot sends confirmation message to user

**ЮKassa requirements:**
- Must register as IP (individual entrepreneur) or LLC — not available for physical persons
- Test mode available with test card numbers
- Webhook must be HTTPS (Railway provides this)
- SBP (Система Быстрых Платежей) support: available in ЮKassa, highly recommended as Russian users prefer it

**Confidence:** HIGH for integration pattern. MEDIUM for SDK version number (verify current PyPI version before using).

#### Option B: Telegram Stars

| Technology | Purpose | Why |
|------------|---------|-----|
| Telegram Bot API `send_invoice` + `SuccessfulPayment` | Native in-bot payment | No external redirect; lower friction; no Russian legal entity required |

**Telegram Stars integration flow:**
1. Bot calls `send_invoice()` with `provider_token=""` (Stars use empty token), `currency="XTR"`, `prices=[LabeledPrice("Скан", STARS_AMOUNT)]`
2. Telegram shows native payment UI inside app
3. User pays with Stars
4. Bot receives `PreCheckoutQuery` → must answer within 10 seconds with `answer_pre_checkout_query(ok=True)`
5. Bot receives `SuccessfulPayment` event in message handler
6. Backend records payment, unlocks scan

**Stars exchange rate:** Telegram sets XTR (Stars) to USD rate. As of mid-2025, approximately 50 Stars = $1. For 3500₽ (~$38 at current rate), that's approximately 1900 Stars. Stars pricing is less intuitive to Russian users who think in rubles.

**Stars vs ЮKassa recommendation:**
- **Use ЮKassa as primary** — users trust ruble pricing, SBP is ubiquitous in Russia, receipts are expected
- **Use Telegram Stars as secondary** — add as "pay without leaving Telegram" option for users who hold Stars from other purchases, or as fallback if ЮKassa onboarding takes time
- Stars are simpler to implement (no webhook verification, no legal entity required) — good for MVP if ЮKassa setup is blocked

**Confidence:** HIGH for Telegram Stars API mechanics. MEDIUM for Stars exchange rate (verify current rate). MEDIUM for ЮKassa legal requirements (verify current IP/LLC requirements on yookassa.ru).

---

### Web Application (Personal Cabinet)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Next.js** | **14.x** (App Router) | Web cabinet frontend | React framework with SSR; App Router for auth-gated routes |
| **React** | **18.x** | UI library | Bundled with Next.js |
| **Tailwind CSS** | **3.x** | Styling | Utility-first; fast to build dashboard UI; no design system overhead |
| **shadcn/ui** | latest | Component library | Built on Radix primitives + Tailwind; copy-paste components, no dependency lock-in |
| **TypeScript** | **5.x** | Type safety | Essential for API response types and Telegram auth payload validation |

**Why Next.js App Router over Pages Router:**
- Server Components reduce client-side JS; report pages can be server-rendered
- Route handlers replace `pages/api/` for auth callback and proxy endpoints
- Layout-based auth guards are cleaner than HOC patterns in Pages Router

**Why NOT a SPA (Vite + React) without Next.js:**
- SSR matters for initial load time on mobile (most Russian users on phones)
- Next.js handles image optimization, font loading, meta tags out of the box
- Easier deployment on Vercel or Railway compared to configuring nginx for SPA

**Why defer web app to Phase 4 (not MVP):**
- Bot alone can prove product-market fit at lower cost
- Telegram Login Widget (required for web auth) works only with a verified domain, adding DNS setup overhead
- Every user interaction in v1 happens in Telegram; web adds a channel nobody uses yet

**Confidence:** HIGH for Next.js 14 + Tailwind + shadcn/ui stack. MEDIUM for App Router maturity for this specific use case (App Router stabilized in Next.js 13.4; by 14 it is production-ready).

---

### Authentication (Web Cabinet)

| Technology | Purpose | Why |
|------------|---------|-----|
| **Telegram Login Widget** | Web auth via Telegram account | Users already have Telegram; no password needed; cryptographically secure |
| **python-jose** or **PyJWT** | JWT issuance and validation on FastAPI | Issue JWT after Telegram auth validation; include `user_id` claim |
| **HTTP-only cookie** | JWT storage in browser | Safer than localStorage; Next.js middleware can read it for server components |

**Telegram Login Widget validation (server-side in FastAPI):**
```python
import hmac, hashlib

def validate_telegram_auth(data: dict, bot_token: str) -> bool:
    received_hash = data.pop("hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)
```

This is the only cryptographically correct way to validate Telegram Login data. Any shortcut here is a security vulnerability.

**Confidence:** HIGH — Telegram Login Widget crypto spec is stable and documented; JWT issuance pattern is standard.

---

### Content Auto-Posting (TG Channel)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **APScheduler** | **3.x** | Cron-style job scheduling | In-process scheduler; no separate worker needed for simple scheduling |
| Telegram Bot API | current | Post to @Reva_mentor channel | Bot must be admin in channel; uses `send_message` with channel `chat_id` |

**APScheduler vs alternatives:**
- **vs n8n:** n8n is a separate service (Docker container or cloud). Adds infrastructure cost and complexity. Fine for no-code workflows but overkill when the backend already has the content generation logic.
- **vs Celery + Redis:** Celery is the right choice when tasks are high-volume, need retry queues, or run in separate workers. For 1-3 posts/day, APScheduler in-process is sufficient and simpler.
- **vs cron + scripts:** Cron requires server SSH access; not available on Railway without hacks.

**Upgrade path:** If APScheduler becomes insufficient (e.g., task failures need complex retry, or separate scaling is needed), migrate job definitions to Celery tasks with minimal rewrite — the ContentService logic stays the same.

**Confidence:** HIGH for APScheduler for simple scheduling. MEDIUM for long-term sufficiency (depends on posting frequency).

---

### Infrastructure / Deployment

| Technology | Purpose | Why |
|------------|---------|-----|
| **Railway** | Cloud hosting for backend + PostgreSQL | One-click Postgres; public HTTPS URL for webhooks from day 1; automatic deploys on git push |
| **Vercel** | Next.js web app hosting | First-class Next.js support; free tier for low traffic; CDN included |
| **Docker** | Backend containerization | Railway deploys from Dockerfile; ensures reproducible environment |
| **GitHub** | Source control | Triggers Railway and Vercel auto-deploys |

**Railway vs alternatives:**
- **vs Render:** Render free tier has cold starts (spin-down after 15 min inactivity) — fatal for a Telegram webhook bot which must respond in <3s. Railway keeps processes warm.
- **vs Heroku:** Heroku free tier removed; paid tiers are expensive relative to Railway.
- **vs VPS (Hetzner):** Lower long-term cost at scale, but adds nginx, certbot, SSH management, manual Postgres setup. Not worth it for initial launch.

**Cost estimate (Railway):**
- Hobby plan: $5/mo base + usage
- PostgreSQL add-on: $5-10/mo (first 500MB free)
- Backend service: ~$5-10/mo at low traffic
- Total initial: ~$15-25/mo

**Confidence:** HIGH for Railway as best-fit platform for webhook bots. MEDIUM for exact pricing (verify current Railway plans before committing).

---

### Environment and Config

| Technology | Purpose | Why |
|------------|---------|-----|
| **python-dotenv** | Local `.env` loading | Standard; `.env` never committed to git |
| **pydantic-settings** | Config validation via Pydantic | `BaseSettings` class validates all env vars at startup; fails fast on missing secrets |

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    database_url: str
    yukassa_shop_id: str
    yukassa_secret_key: str
    webhook_secret: str
    jwt_secret: str

    class Config:
        env_file = ".env"

settings = Settings()
```

This pattern ensures the app crashes at startup — not at runtime — if a required secret is missing.

**Confidence:** HIGH.

---

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | **8.x** | Test runner | Standard Python testing |
| **pytest-asyncio** | **0.23+** | Async test support | Required for testing FastAPI and aiogram handlers |
| **httpx** | **0.27+** | FastAPI test client | AsyncClient for testing async FastAPI routes |

Minimal testing strategy for MVP: test payment webhook handlers (high risk of silent bugs) and report JSON parsing (high risk of breaking AI output changes). Skip unit tests for bot conversation handlers in Phase 1.

**Confidence:** HIGH.

---

## Full Dependency List

```txt
# requirements.txt

# Bot framework
aiogram==3.7.0

# Web framework
fastapi==0.111.0
uvicorn[standard]==0.29.0

# Database
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1

# AI
anthropic==0.25.0

# Payments
yookassa==3.0.0

# Config
pydantic-settings==2.2.1
python-dotenv==1.0.1

# Auth
python-jose[cryptography]==3.3.0

# Scheduling
apscheduler==3.10.4

# HTTP client (for scraping social URLs, testing)
httpx==0.27.0

# Testing
pytest==8.2.0
pytest-asyncio==0.23.7
```

**IMPORTANT:** Pin versions above are approximations based on training data (August 2025 cutoff). Before initializing the project, run `pip index versions <package>` for each critical dependency and use the actual latest stable versions. Do not blindly copy these versions — they may be stale.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Telegram bot framework | aiogram 3.x | python-telegram-bot 20.x | PTB's ConversationHandler degrades past 5 states; aiogram Router is cleaner |
| Telegram bot framework | aiogram 3.x | Telegraf (Node.js) | Different language; splits AI logic across two runtimes |
| Web framework | FastAPI | Django | Django async is incomplete; too heavy for an API-only backend |
| Web framework | FastAPI | Flask + extensions | Flask async is bolted on; no native Pydantic; more config overhead |
| Web frontend | Next.js 14 | Vue/Nuxt | Smaller ecosystem; shadcn/ui is React-only |
| Web frontend | Next.js 14 | SvelteKit | Smaller ecosystem; less tooling for Telegram Login Widget integration |
| ORM | SQLAlchemy 2.x async | Tortoise ORM | Less documentation; fewer migration tools; smaller community |
| ORM | SQLAlchemy 2.x async | raw asyncpg | No migration support; boilerplate-heavy for CRUD |
| Scheduling | APScheduler | Celery + Redis | Celery requires Redis service; overkill for 1-3 posts/day |
| Scheduling | APScheduler | n8n | Separate service with Docker overhead; no benefit when Python backend already has logic |
| Hosting (backend) | Railway | Render | Render free tier has cold starts; fatal for webhook bots |
| Hosting (backend) | Railway | Heroku | No free tier; higher cost than Railway at same tier |
| Hosting (web) | Vercel | Railway | Vercel has better Next.js optimizations; CDN built-in; free tier for low traffic |
| Payments (primary) | ЮKassa | Stripe | Stripe unavailable for Russian market residents receiving payments |
| Payments (primary) | ЮKassa | CloudPayments | ЮKassa has better SDK support and tighter Telegram bot integration docs in Russian community |
| Claude model (reports) | claude-sonnet-4-5 | claude-opus-4-5 | Opus is 3-5x more expensive with marginal quality difference for structured analysis |
| Claude model (reports) | claude-sonnet-4-5 | GPT-4o | Claude produces more nuanced qualitative analysis; Anthropic is the project's chosen provider |

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| **Polling mode** (`dp.start_polling()`) in production | Consumes persistent connections; causes issues with Railway restart cycles; webhook is correct for production |
| **SQLite** | Not suitable for async concurrent writes from bot + API; use PostgreSQL from day 1 |
| **Django Channels** | WebSocket complexity not needed; REST + Telegram bot handles all real-time needs |
| **GraphQL** | Next.js ↔ FastAPI communication is simple enough for REST; GraphQL adds schema overhead with no benefit |
| **Celery** in Phase 1 | Requires Redis; overkill for MVP scheduling needs; APScheduler is sufficient |
| **MongoDB** | JSONB in PostgreSQL handles the semi-structured report data; no need for a separate document DB |
| **Serverless functions** (Lambda, Vercel Functions for backend) | Cold starts kill Telegram webhook response time; always-on process required |

---

## Installation (Project Bootstrap)

```bash
# Python backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Next.js web app
cd web
npx create-next-app@14 . --typescript --tailwind --eslint --app
npm install @shadcn/ui

# shadcn/ui init
npx shadcn-ui@latest init
```

---

## Environment Variables Required

```bash
# Telegram
TELEGRAM_BOT_TOKEN=          # From @BotFather
WEBHOOK_SECRET=              # Random string; validates webhook origin

# Anthropic
ANTHROPIC_API_KEY=           # From console.anthropic.com

# Database
DATABASE_URL=                # postgresql+asyncpg://user:pass@host/db

# ЮKassa
YUKASSA_SHOP_ID=             # From ЮKassa merchant account
YUKASSA_SECRET_KEY=          # From ЮKassa merchant account

# Auth
JWT_SECRET=                  # Random 32+ char string for JWT signing

# App
WEBHOOK_BASE_URL=            # https://your-app.railway.app
CHANNEL_CHAT_ID=             # @Reva_mentor channel ID (negative number)
```

---

## Confidence Summary

| Area | Confidence | Notes |
|------|------------|-------|
| aiogram 3.x as bot framework | HIGH | Stable, dominant choice since 2023; FSM API well-documented |
| FastAPI + Pydantic v2 | HIGH | Standard Python async API stack; no alternatives close |
| SQLAlchemy 2.x async + asyncpg | HIGH | Production-proven pattern for FastAPI + PostgreSQL |
| Anthropic Python SDK | HIGH | Official SDK; async client available since ~2023 |
| Claude model selection (Sonnet for reports) | MEDIUM | Model names/pricing change; verify current recommended model in Anthropic docs |
| ЮKassa Python SDK | MEDIUM | SDK exists and is maintained; version number and exact webhook payload format need live verification |
| Telegram Stars API | MEDIUM | API mechanics stable but Stars exchange rate and XTR pricing UX need verification |
| Next.js 14 App Router | HIGH | App Router is stable and production-ready as of Next.js 14 |
| Railway as hosting | MEDIUM | Best-fit platform for this use case; verify current pricing before committing |
| APScheduler for content posting | HIGH | Correct tool for in-process scheduling at low frequency |
| Exact package versions | LOW | All versions are training-data approximations; verify on PyPI/npm before use |

---

## Sources

All findings are from training data (knowledge cutoff August 2025). No live web sources were available during this research session.

- aiogram documentation and FSM patterns (training knowledge, HIGH confidence)
- FastAPI official patterns — async, Pydantic v2 integration (training knowledge, HIGH confidence)
- SQLAlchemy 2.x async documentation (training knowledge, HIGH confidence)
- Anthropic Python SDK documentation (training knowledge, HIGH confidence)
- Telegram Bot API — Payments 2.0 (Stars), send_invoice, PreCheckoutQuery, SuccessfulPayment (training knowledge, MEDIUM confidence)
- ЮKassa developer documentation and Python SDK (training knowledge, MEDIUM confidence)
- Next.js 14 App Router documentation (training knowledge, HIGH confidence)
- Railway platform capabilities and pricing (training knowledge, MEDIUM confidence)

**Required pre-implementation verifications:**
1. Check current Claude model names at https://docs.anthropic.com/en/docs/about-claude/models — model IDs are renamed periodically
2. Check ЮKassa webhook payload format and signature verification at https://yookassa.ru/developers/using-api/webhooks — field names may have changed
3. Verify current Telegram Stars to USD rate and whether Stars are available to Russian users paying for bots
4. Check Railway current pricing at https://railway.app/pricing before committing to the platform
5. Verify all package versions on PyPI before writing requirements.txt
