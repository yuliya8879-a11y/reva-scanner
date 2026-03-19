# Architecture Patterns

**Domain:** AI-powered Telegram bot + web dashboard (business scanner)
**Researched:** 2026-03-19
**Confidence:** MEDIUM — based on established patterns for this system class; web/fetch tools unavailable for live verification

---

## Recommended Architecture

### System Overview

The system is a monorepo with two runtime entry points (bot + API server) sharing a single PostgreSQL database. The Next.js web app connects to the same API. The AI engine and content pipeline are internal modules, not separate services.

```
┌─────────────────────────────────────────────────────┐
│                   TELEGRAM LAYER                    │
│  @Reva_mentor channel   │   @RevaScanner_bot        │
│  (content auto-posting) │   (user interaction)      │
└──────────────┬──────────┴──────────┬────────────────┘
               │ Telegram API        │ Telegram API
               ▼                     ▼
┌──────────────────────────────────────────────────────┐
│               BACKEND (Python / FastAPI)             │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Bot Module │  │  API Module  │  │  Scheduler  │ │
│  │  (aiogram3) │  │  (FastAPI)   │  │  (APScheduler│ │
│  │             │  │              │  │   or Celery) │ │
│  │ FSM States  │  │ REST routes  │  │             │ │
│  │ Handlers    │  │ Auth (JWT)   │  │ Content gen │ │
│  │ Middleware  │  │ Webhooks     │  │ Auto-posting│ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘ │
│         └────────────────┴──────────────────┘        │
│                          │                           │
│  ┌───────────────────────▼──────────────────────────┐│
│  │              Service Layer                        ││
│  │  ScanService │ PaymentService │ ContentService    ││
│  │  UserService │ AIService      │ ReportService     ││
│  └───────────────────────┬───────────────────────────┘│
└──────────────────────────┼──────────────────────────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
   ┌─────────────┐  ┌────────────┐  ┌──────────────┐
   │ PostgreSQL  │  │ Claude API │  │  ЮKassa API  │
   │             │  │            │  │  TG Stars    │
   │ users       │  │ Analysis   │  │              │
   │ scans       │  │ Report gen │  │              │
   │ payments    │  │ Content gen│  │              │
   │ content_q   │  └────────────┘  └──────────────┘
   └─────────────┘

┌──────────────────────────────────────────────────────┐
│              WEB APP (Next.js)                       │
│                                                      │
│  Personal cabinet → calls FastAPI via REST           │
│  Auth via Telegram Login Widget or magic link        │
│  Displays scan history, full reports, payments       │
└──────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **Bot Module** | User conversation, FSM questionnaire, command handling | Service Layer, PostgreSQL | aiogram 3.x |
| **API Module** | REST endpoints for web app and webhooks | Service Layer, PostgreSQL | FastAPI |
| **Scheduler** | Content generation and auto-posting on schedule | ContentService, Telegram Bot API | APScheduler or Celery+Redis |
| **AI Service** | Wraps Claude API calls, prompt management, retry logic | Claude API (Anthropic) | httpx / anthropic-sdk |
| **Scan Service** | Orchestrates data collection → AI → report storage | AIService, ReportService, DB | Python |
| **Payment Service** | Handles ЮKassa callbacks, Telegram Stars events, subscription logic | ЮKassa API, DB | Python |
| **Content Service** | Generates posts / Reels scripts, schedules them to queue | AIService, DB, Telegram Bot API | Python |
| **Report Service** | Formats AI output into structured report, stores in DB | DB | Python |
| **User Service** | Registration, profile, subscription status | DB | Python |
| **PostgreSQL** | Single source of truth for all persistent state | Backend only | PostgreSQL 16 |
| **Next.js Web App** | Personal cabinet UI (scan history, reports, payments) | FastAPI REST | Next.js 14+ |

**Key boundary rules:**
- Bot Module never calls Claude API directly — always goes through ScanService → AIService
- Next.js never touches DB directly — always through FastAPI REST
- Scheduler runs in same process as backend (APScheduler) or as a separate worker (Celery)
- Payment webhooks arrive at FastAPI, not at the bot

---

## Data Flow

### Flow 1: User completes scan and receives report

```
User → Bot (sends answers via FSM questionnaire)
     → ScanService.create_scan(user_id, answers)
     → DB: scans row created (status=collecting)
     → ScanService.trigger_analysis()
     → AIService.analyze(scan_data)  →  Claude API
     ← AIService returns structured report JSON
     → ReportService.format_and_store(report)
     → DB: scans row updated (status=complete, report_json=...)
     → Bot sends formatted summary to user in TG
     → Bot sends "full report in web cabinet" link
```

### Flow 2: Payment via ЮKassa

```
User → Bot sends /pay or inline keyboard
     → PaymentService.create_invoice(user_id, amount, type)
     → ЮKassa API creates payment, returns payment_url
     → Bot sends payment_url to user
     User pays on ЮKassa page
     → ЮKassa sends webhook POST to FastAPI /webhooks/yukassa
     → PaymentService.process_webhook(payload)
     → DB: payments row created (status=paid)
     → DB: user subscription updated if needed
     → ScanService.unlock_scan(scan_id) or trigger new scan
     → Bot sends confirmation message to user
```

### Flow 3: Payment via Telegram Stars

```
User → Bot sends invoice (send_invoice Telegram API method)
     Telegram handles payment UI natively
     → Bot receives PreCheckoutQuery → bot approves
     → Bot receives SuccessfulPayment event
     → PaymentService.record_stars_payment(user_id, payload)
     → DB: payments row created
     → Bot unlocks scan or subscription
```

### Flow 4: Content auto-posting to @Reva_mentor

```
Scheduler triggers (e.g., daily at 10:00)
     → ContentService.generate_post(topic, type)
     → AIService.generate_content(prompt)  →  Claude API
     ← returns post text / Reels script
     → DB: content_queue row created (status=ready)
     → Scheduler picks up ready items
     → Telegram Bot API: bot.send_message(@Reva_mentor channel_id, text)
     → DB: content_queue status=posted
```

### Flow 5: User views reports in web cabinet

```
User opens Next.js web app
     → Auth: Telegram Login Widget returns user hash
     → Next.js: POST /api/auth/telegram → FastAPI validates hash
     → FastAPI returns JWT
     Next.js stores JWT in cookie
     → Next.js fetches /api/scans  →  FastAPI
     → FastAPI queries DB, returns scan list
     → Next.js renders scan history page
     User clicks scan → Next.js fetches /api/scans/{id}/report
     → FastAPI returns report JSON
     → Next.js renders full report page
```

---

## Database Schema (minimal)

```
users
  id, telegram_id, username, name, birth_date
  subscription_type (none|monthly), subscription_until
  created_at, updated_at

scans
  id, user_id (FK), status (collecting|processing|complete|failed)
  questionnaire_answers (jsonb)
  free_text, social_urls (text[])
  report_json (jsonb)
  paid (bool), payment_id (FK)
  created_at, completed_at

payments
  id, user_id (FK), scan_id (FK nullable)
  provider (yukassa|stars), provider_payment_id
  amount, currency, type (scan|subscription)
  status (pending|paid|failed), paid_at
  created_at

content_queue
  id, type (post|reels_script|content_plan)
  topic, generated_text
  scheduled_for, posted_at, status (draft|ready|posted|failed)
  created_at
```

---

## Patterns to Follow

### Pattern 1: aiogram FSM for questionnaire

**What:** Use aiogram 3.x Finite State Machine to walk user through multi-step questionnaire. Each question is a state; answers are accumulated in FSM storage (Redis or in-memory).

**When:** Any multi-step conversation flow in Telegram bot.

```python
class ScanStates(StatesGroup):
    waiting_for_birth_date = State()
    waiting_for_business_description = State()
    waiting_for_social_urls = State()
    waiting_for_questionnaire_answers = State()
    confirming_payment = State()

@router.message(ScanStates.waiting_for_birth_date)
async def handle_birth_date(message: Message, state: FSMContext):
    await state.update_data(birth_date=message.text)
    await state.set_state(ScanStates.waiting_for_business_description)
    await message.answer("Опишите ваш бизнес...")
```

**Why:** FSM prevents state chaos, handles /cancel gracefully, survives bot restarts if using Redis storage.

### Pattern 2: Single FastAPI backend for both bot and REST

**What:** Run bot (via webhook) and FastAPI REST in the same Python process. Bot registers webhook at startup; FastAPI handles both /webhook/telegram and /api/* routes.

**When:** Budget-constrained deployments where running two separate services is unnecessary overhead.

```python
# main.py
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL + "/webhook/telegram")

@app.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    await dp.process_update(Update(**update))

@app.get("/api/scans")
async def list_scans(user=Depends(get_current_user)):
    ...
```

**Why:** Simpler deployment (one Dockerfile, one Railway service), shared DB connections, no inter-service HTTP.

### Pattern 3: Async Claude API calls with retry

**What:** Wrap all Claude API calls in a service class with retry logic, timeout, and structured output parsing.

**When:** Every AI call in the system.

```python
class AIService:
    async def analyze_scan(self, scan_data: ScanData) -> ReportJSON:
        prompt = build_analysis_prompt(scan_data)
        for attempt in range(3):
            try:
                response = await anthropic_client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return parse_report(response.content[0].text)
            except anthropic.RateLimitError:
                await asyncio.sleep(2 ** attempt)
```

**Why:** Claude API can have transient errors; reports are expensive to discard; structured parsing must be isolated.

### Pattern 4: Telegram Login Widget for web auth

**What:** Next.js uses Telegram Login Widget (or inline button) to authenticate users. Bot validates the hash server-side using bot token as HMAC key. On success, issue JWT.

**Why:** Users already have Telegram accounts; no separate username/password needed; cryptographically secure.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Calling Claude API directly from bot handlers

**What:** Handler function directly awaits Claude API call inline.

**Why bad:** Handler blocks for 5-30 seconds, Telegram times out, error recovery is impossible, no separation of concerns.

**Instead:** Handler calls ScanService which runs AI call as background task; bot sends "анализирую..." message immediately, then sends result when ready.

### Anti-Pattern 2: Polling instead of webhooks in production

**What:** Using `dp.start_polling()` in production deployment.

**Why bad:** Polling uses long-poll connections that consume resources, doesn't scale, causes issues on Railway/Render with sleep/restart.

**Instead:** Use webhooks. FastAPI receives POST from Telegram, processes update, responds 200 immediately.

### Anti-Pattern 3: Storing report JSON as flat text

**What:** Storing Claude's raw response as a text string in DB.

**Why bad:** Can't query sections, can't render structured web UI, hard to migrate format later.

**Instead:** Define a `ReportSchema` (Pydantic) and store as `jsonb` in PostgreSQL. Parser normalizes Claude output to schema before storage.

### Anti-Pattern 4: Monolithic prompt

**What:** One 2000-token prompt that tries to do questionnaire + numerology + social media + recommendations in one call.

**Why bad:** Claude context ceiling, inconsistent output structure, hard to iterate on one section without breaking others.

**Instead:** Compose 2-3 focused prompts (core business analysis, numerology layer, social media audit), merge structured outputs in ReportService.

### Anti-Pattern 5: Scheduler in separate service without shared DB connection pooling

**What:** Running APScheduler or Celery in a separate process that opens its own DB connections without pooling awareness.

**Why bad:** Connection exhaustion on free-tier PostgreSQL (Railway free tier: 5 max connections).

**Instead:** Use a single connection pool (asyncpg + SQLAlchemy async) shared across bot, API, and scheduler in same process. Or use Celery with explicit pool size limits.

---

## Suggested Build Order

The following order reflects hard technical dependencies. Each phase produces something usable and deployable.

```
Phase 1: Foundation (must exist before anything else)
  ├── PostgreSQL schema (users, scans, payments, content_queue)
  ├── FastAPI skeleton with DB connection (SQLAlchemy async + asyncpg)
  ├── User registration via bot (/start handler, save telegram_id)
  └── Basic aiogram bot wired via webhook to FastAPI

Phase 2: Core scan flow (the product)
  ├── FSM questionnaire (all steps, data accumulation)
  ├── AIService with Claude API integration
  ├── ScanService orchestrator (collect → analyze → store)
  ├── Report formatting and delivery via bot message
  └── Background task pattern (bot sends "processing..." immediately)

Phase 3: Payments (monetization)
  ├── ЮKassa integration (create invoice, webhook handler)
  ├── Telegram Stars integration (send_invoice, SuccessfulPayment handler)
  ├── PaymentService (both providers, unified DB recording)
  └── Scan unlock logic (scan created only after payment confirmed)

Phase 4: Web cabinet (Next.js)
  ├── FastAPI auth endpoint (Telegram Login Widget hash validation, JWT)
  ├── FastAPI REST endpoints (/api/scans, /api/scans/{id}/report, /api/payments)
  ├── Next.js project setup with Telegram Login Widget
  ├── Scan history page
  └── Full report render page

Phase 5: Content pipeline
  ├── ContentService (prompt templates for posts, Reels scripts)
  ├── content_queue table + scheduler (APScheduler)
  ├── Auto-posting to @Reva_mentor channel
  └── Admin command to manually trigger content generation
```

**Dependency rules:**
- Phase 2 requires Phase 1 (DB + bot wiring)
- Phase 3 requires Phase 2 (can't pay for something that doesn't exist)
- Phase 4 requires Phase 3 (web shows payment status; auth tied to TG users already in DB)
- Phase 5 is independent of Phase 4; can be built in parallel after Phase 2

---

## Deployment Considerations

### Recommended: Railway (primary choice)

**Why Railway:**
- One-click PostgreSQL add-on, same private network as app (no SSL overhead, no connection string complexity)
- Supports webhook-based bots (stable public URL from day 1)
- Free tier sufficient for early users; paid tier ($5/mo) for production
- Environment variables via dashboard, no secrets in code
- Automatic deploys on git push

**Railway topology for this project:**
```
Railway Project
  ├── Service: backend (Python/FastAPI + aiogram)
  │     Dockerfile: Python 3.12, uvicorn, webhook mode
  │     Env vars: DATABASE_URL, TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY,
  │               YUKASSA_SHOP_ID, YUKASSA_SECRET, WEBHOOK_SECRET
  ├── Service: web (Next.js)
  │     Env vars: NEXT_PUBLIC_API_URL, TELEGRAM_BOT_NAME
  └── Plugin: PostgreSQL 16
```

**Single Dockerfile for backend:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Alternative: Render

Render is functionally similar to Railway. Free tier has cold starts (spin-down after 15 min), which will cause Telegram webhook timeouts. Use paid tier ($7/mo) to keep service warm. Less recommended than Railway for bots specifically.

### Alternative: VPS (Hetzner CX22, ~€4/mo)

Use when: Railway costs exceed $20/mo at scale, or need full control over DB connections.

Setup: Docker Compose with postgres + backend + nginx + certbot. More ops overhead but lower cost at volume.

**Not recommended for initial launch** — Railway's zero-ops setup is worth the cost at this stage.

### HTTPS and Webhook Registration

Telegram requires HTTPS for webhooks. Railway and Render provide HTTPS automatically. On VPS use Caddy or nginx + Let's Encrypt.

Webhook registration at startup:
```python
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/webhook/telegram"
await bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
```

Validate `secret_token` header on every incoming webhook request to prevent spoofing.

---

## Scalability Considerations

| Concern | At 100 users/mo | At 1K users/mo | At 10K users/mo |
|---------|-----------------|-----------------|-----------------|
| DB connections | Railway Postgres default fine | Add pgBouncer or connection pooling | Dedicated Postgres instance |
| Claude API cost | ~$30-100/mo | ~$300-1000/mo | Optimize prompts, cache reports |
| Bot throughput | Single process fine | Single process fine (aiogram is async) | Multiple webhook workers |
| Content pipeline | APScheduler in same process | Same | Separate Celery worker |
| Report generation time | Sync background task in FastAPI | Same | Queue (Celery + Redis) |

At the scale this project starts, a single Railway service handles everything. The architecture is designed so each component can be extracted to its own service later without rewriting business logic.

---

## Sources

- Knowledge of aiogram 3.x FSM patterns, webhook architecture (training data, HIGH confidence)
- Telegram Bot API payment methods: ЮKassa provider, Telegram Stars (training data, MEDIUM confidence — verify Stars API details in Telegram docs before implementation)
- FastAPI + SQLAlchemy async patterns (training data, HIGH confidence)
- Railway deployment topology for Python services (training data, MEDIUM confidence — verify current pricing)
- Telegram Login Widget authentication flow (training data, HIGH confidence — cryptographic spec is stable)
- Claude API structured output patterns (training data, HIGH confidence)

**Note:** Web search and WebFetch were unavailable during this research session. All findings are based on training data (knowledge cutoff August 2025). Verify ЮKassa webhook payload format and Telegram Stars `send_invoice` method signature against current official docs before implementation.
