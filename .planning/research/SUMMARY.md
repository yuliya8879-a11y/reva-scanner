# Research Summary: Reva Scanner

**Project:** Reva Scanner — Цифровой сканер бизнеса
**Domain:** AI-powered paid Telegram bot with Russian payment processing and content automation
**Researched:** 2026-03-19
**Confidence:** MEDIUM-HIGH (core stack HIGH; payment/legal decisions MEDIUM)

---

## Executive Summary

Reva Scanner is a paid AI diagnostic Telegram bot that replaces a personal business consultation with a structured questionnaire + Claude-powered analysis for 3500₽. The product is well-understood: this is a standard FSM-driven Telegram funnel (free mini-scan → payment gate → full report) in the Russian InfoBiz niche. The architecture is a Python monorepo with aiogram 3.x for the bot, FastAPI for the API and webhook receiver, PostgreSQL for persistence, and Claude Sonnet for report generation. The web cabinet (Next.js) is deliberately deferred — the bot alone can prove product-market fit.

The highest-quality version of this product lives or dies on two things: prompt quality and payment architecture. Generic AI output triggers refund demands in Telegram communities, destroying Юлия's personal brand. Payment architecture is a pre-code decision — ЮKassa requires a registered ИП/ООО and 2–5 week onboarding, and Telegram Stars revenue cannot be withdrawn as rubles. Both issues must be resolved before a single line of payment code is written.

The critical path is: legal entity + ЮKassa onboarding (start immediately, in parallel with development) → Foundation (bot + DB + webhook) → Core scan flow → Payment gate. Content automation (auto-posting to @Reva_mentor) can be built in parallel after the bot foundation is in place. The web cabinet is Phase 4 — after the bot proves the product.

---

## Key Findings

### Recommended Stack

The backend is Python 3.12 throughout. aiogram 3.x is the clear choice for the Telegram bot layer — its FSM (`StatesGroup` + `FSMContext`) handles the 12–15 question questionnaire cleanly, while python-telegram-bot's `ConversationHandler` degrades past 5 states. FastAPI handles both the Telegram webhook and the REST API for the web cabinet in a single process, sharing DB connections — this is the right cost/complexity tradeoff at early scale.

PostgreSQL 16 with JSONB is the correct storage choice: report data is semi-structured, but relational queries (user → scans → payments) require SQL. SQLAlchemy 2.x async + asyncpg is the production-proven ORM layer. Do not use SQLite or MongoDB. Redis is deferred — aiogram FSM can use in-memory storage for MVP, upgrade to RedisStorage when Railway budget allows.

**Core technologies:**

| Technology | Purpose | Why |
|------------|---------|-----|
| Python 3.12 + aiogram 3.x | Telegram bot and FSM questionnaire | Best-in-class FSM; async; Russian community support |
| FastAPI 0.111+ + Pydantic v2 | REST API + Telegram webhook receiver | Async-native; OpenAPI; single process with bot |
| PostgreSQL 16 + SQLAlchemy 2.x async | Primary database + ORM | JSONB for reports; Alembic migrations from day 1 |
| Claude Sonnet (anthropic SDK 0.25+) | Full scan report generation | Best cost-quality for 800–1500 word structured output |
| Claude Haiku | Mini-scan teaser + content generation | 10–20x cheaper; sufficient for short outputs |
| ЮKassa Python SDK 3.x | Payment processing (primary) | Only viable RUB gateway; ИП/ООО required |
| Telegram Stars (Bot API) | Payment processing (secondary/fallback) | No legal entity needed; good while ЮKassa onboarding pending |
| APScheduler 3.x | Content auto-posting scheduler | In-process; no Redis needed for 1–3 posts/day |
| Railway | Backend hosting + PostgreSQL | Always-on (no cold starts); webhook-compatible; Postgres included |
| Next.js 14 + Tailwind + shadcn/ui | Web cabinet (Phase 4) | SSR for mobile; Telegram Login Widget auth |

**Do not use:** polling mode in production, SQLite, MongoDB, Django, Celery (Phase 1), serverless functions, GraphQL.

See `/planning/research/STACK.md` for full rationale, alternatives considered, and package version list.

---

### Expected Features

The product has a clear funnel: TG channel subscriber → /start → free mini-scan (5 questions) → teaser result → 3500₽ payment → full 12–15 question scan → Claude report. This is table stakes; anything below this line is not a product.

**Must have (v1 table stakes):**
- Free mini-scan (5 questions) → teaser report (3–4 sentences) → payment CTA
- Payment gate — ЮKassa invoice or Telegram Stars, inline keyboard, no external redirect
- Payment confirmation + scan unlock in under 5 seconds (webhook-driven, not polling)
- Full questionnaire FSM (12–15 questions, button-driven to minimize drop-off)
- Numerology computation from birth date — the "this is specifically about YOU" hook
- Free-text situation field — AI extracts hidden patterns
- Social media URL input (optional enrichment — never a hard dependency)
- Full report via Claude Sonnet, delivered as split Telegram messages (4096 char limit)
- Session persistence — user can return mid-flow and resume
- Results stored in DB per user
- Content generation for @Reva_mentor + auto-posting scheduler (admin-side v1 requirement)

**Should have (differentiators, v1 if time allows):**
- Named diagnosis categories: "Слепые зоны", "Утечки денег", "Энергетические блоки" — branded copy, not extra code
- Report personalization signals — user's name, niche, and specific numbers they gave must appear in output
- Progress indicator (вопрос X из Y) — reduces drop-off during questionnaire
- Refund admin command (`/refund <user_id>`) — triggers ЮKassa API + DB revocation

**Defer to v2+:**
- PDF report with branding
- Web app personal cabinet (Phase 4)
- Subscription model with monthly recurring billing
- "What changed" re-scan comparison
- Referral mechanic
- Report sharing / screenshot card

**The aha-moment that drives payment:** The mini-scan teaser must name one specific, slightly uncomfortable truth. Generic output ("you should focus on marketing") kills conversion. The prompt for the teaser is the highest-leverage piece of work in the entire product.

See `/planning/research/FEATURES.md` for onboarding flow diagram, completion rate risk points, and report quality requirements.

---

### Architecture Approach

Single Python monorepo, single Railway service. FastAPI handles Telegram webhooks and REST API in one process. aiogram bot is wired into FastAPI via a `/webhook/telegram` route — no separate polling process. PostgreSQL is the only persistence layer in v1. APScheduler runs in-process for content scheduling. The Next.js web app is a separate service connecting via REST (Phase 4).

The service layer is the key architectural boundary: bot handlers never call Claude directly — they call ScanService → AIService. This keeps handlers thin and enables background task patterns (send "анализирую..." immediately, deliver report when ready).

**Major components and build order:**

| Component | Responsibility |
|-----------|---------------|
| Bot Module (aiogram 3.x) | FSM questionnaire, command handling, UX delivery |
| API Module (FastAPI) | REST endpoints for web + webhook receiver for Telegram and ЮKassa |
| Scheduler (APScheduler) | Content generation trigger and channel auto-posting |
| AIService | Wraps Claude API, prompt management, retry logic, token logging |
| ScanService | Orchestrates: collect answers → analyze → format → store → deliver |
| PaymentService | ЮKassa and Stars webhooks, unified DB recording, scan unlock |
| ContentService | Generates posts/Reels scripts, queues them, posts to @Reva_mentor |
| ReportService | Parses Claude JSON output into ReportSchema, splits for Telegram delivery |
| PostgreSQL | Single source of truth: users, scans, payments, content_queue |
| Next.js Web App | Personal cabinet (Phase 4); reads from FastAPI via REST + JWT auth |

**Key patterns:**
- Compose 2–3 focused Claude prompts (core business analysis / numerology layer / social media audit), merge in ReportService — never a single 2000-token monolith prompt
- Store reports as JSONB with Pydantic schema, never as raw text
- Webhook-only in production — never polling

See `/planning/research/ARCHITECTURE.md` for data flow diagrams, DB schema, and deployment topology.

---

### Top 5 Pitfalls

1. **Payment provider not decided before coding** — ЮKassa requires a registered ИП/ООО and 2–5 week onboarding. Telegram Stars revenue cannot be withdrawn as RUB. Decide in Week 1, start ЮKassa legal onboarding immediately and in parallel with development. Use Stars as fallback only if ЮKassa is blocked.

2. **Claude hallucination presented as expert diagnosis** — The bot presents itself as a specific expert's methodology. When Claude fabricates confident-sounding conclusions unsupported by the questionnaire, users demand refunds publicly in the Telegram communities that are the entire acquisition funnel. Mitigation: prompt must instruct Claude to say "недостаточно данных" when signals are thin; require evidence references; include output disclaimer; Юлия reviews first 20–30 scans before autonomous operation.

3. **54-ФЗ fiscal receipt compliance missing** — Every digital payment in Russia requires a fiscal receipt (чек). ЮKassa has built-in support but it must be configured correctly (tax system, VAT, `payment_subject`). Test mode does not enforce this. Consult a Russian accountant before writing any payment code. Non-compliance: fines + ЮKassa account suspension.

4. **Claude API cost overrun** — At Claude Sonnet pricing, a full scan costs approximately $0.15–0.40. Without token logging and prompt size discipline, costs silently creep toward $1–2 per scan. Subscription "unlimited" plans become loss-making. Mitigation: log `input_tokens`/`output_tokens` per request from day one; keep system prompt under 2000 tokens; cap subscription scans (e.g., 5/month) or use Haiku for re-scans.

5. **Async payment webhook race condition** — ЮKassa webhooks arrive seconds after the user sees "payment successful" in Telegram. Granting scan access before webhook confirmation creates an exploitable window. Waiting silently for the webhook makes the bot appear frozen. Mitigation: full payment state machine (`pending → awaiting_confirmation → confirmed → fulfilled`); show "Ждем подтверждения, обычно 10–30 секунд"; 5-minute timeout with manual fallback message.

See `/planning/research/PITFALLS.md` for 14 pitfalls with prevention strategies and phase-specific warnings.

---

## Key Decisions Needed Before Coding

These are blockers. Do not write code in the affected areas until resolved.

| Decision | Why It's Blocking | Deadline |
|----------|------------------|----------|
| ЮKassa or Telegram Stars as primary payment | ЮKassa = ИП required + 2–5 week onboarding; Stars = no RUB withdrawal. Wrong choice = rewrite or no revenue | Before Phase 1 starts |
| ИП or ООО registered? If not, when? | ЮKassa cannot onboard without legal entity | Before Phase 1 starts |
| Tax system (УСН / ОСНО) and VAT rate for digital services | Required for 54-ФЗ fiscal receipt configuration in ЮKassa payment calls | Before any live payment code |
| Claude model names (current) | Model IDs rename periodically; `claude-sonnet-4-5` may not be the current name | Before AIService implementation |
| Subscription price and scan cap | 2900₽/mo "unlimited" is loss-making at Sonnet prices; must cap or use Haiku for subscription tier | Before Phase 3 |
| Юлия reviews first 20–30 scan outputs | Human calibration loop must be built into launch plan, not an afterthought | Before public launch |

---

## Implications for Roadmap

Research confirms a 5-phase build order with clear hard dependencies. Phase 5 (content pipeline) can run in parallel after Phase 1.

### Phase 1: Foundation + Pre-Coding Decisions
**Rationale:** Nothing else can be built without the bot/DB skeleton and resolved payment decisions. Legal onboarding takes 2–5 weeks — start it on Day 1, run in parallel.
**Delivers:** Working bot on Railway with /start, DB schema, webhook registration, user registration. Payment provider contractually confirmed.
**Implements:** FastAPI + aiogram webhook wiring, PostgreSQL schema (users/scans/payments/content_queue), pydantic-settings config validation
**Avoids:** Payment provider rewrite later; fiscal compliance scramble post-launch
**Pre-code blockers:** ИП status confirmed, ЮKassa onboarding started, accountant consulted on 54-ФЗ, Claude model name verified

### Phase 2: Core Scan Flow (the product)
**Rationale:** This is the value delivery. Must work correctly before adding payment — otherwise payment unlocks a broken product.
**Delivers:** Full FSM questionnaire, AIService with Claude integration, ScanService orchestrator, background task pattern, report delivery in Telegram messages
**Features:** Questionnaire (12–15 questions), birth date + numerology, free-text field, social URL (optional), report generation, session persistence
**Avoids:** Monolithic prompt (use 2–3 composed prompts); direct Claude call in handlers (use ScanService); raw text report storage (use JSONB + ReportSchema); Telegram message length overflow (split at section boundaries)
**Research flag:** Prompt engineering for the numerology layer and the mini-scan teaser is high-stakes and non-standard — allocate deliberate iteration time, not just a ticket

### Phase 3: Payment Gate (monetization)
**Rationale:** Payments can only be added after the scan flow is proven to work end-to-end. Paying users have zero tolerance for a broken scan.
**Delivers:** ЮKassa invoice creation, webhook handler, Telegram Stars flow, payment state machine, scan unlock logic, fiscal receipts, refund admin command
**Avoids:** Async webhook race condition; missing fiscal receipts; no refund policy
**Research flag:** ЮKassa webhook payload format and `receipt` object field names must be verified against current yookassa.ru docs — training data may be stale

### Phase 4: Web Cabinet (Next.js)
**Rationale:** Deferred intentionally. All v1 user interaction is in Telegram. Build only after bot proves product-market fit. Requires Telegram Login Widget domain verification (DNS overhead).
**Delivers:** Scan history page, full report render, Telegram auth, FastAPI JWT endpoints
**Avoids:** Building an unused surface before validating the core product
**Research flag:** Standard Next.js + App Router + shadcn/ui patterns; skip deep research phase

### Phase 5: Content Pipeline (can start after Phase 1)
**Rationale:** Юлии нужно для @Reva_mentor. Not on the scan revenue path — independent of Phases 2–4.
**Delivers:** ContentService (posts, Reels scripts, content plan), APScheduler, auto-posting to channel, admin command for manual trigger
**Avoids:** Serverless scheduler (use persistent APScheduler in same process); burst posting (rate-limit to 1 post/minute); bot losing admin status silently (monitor and alert)

### Phase Ordering Rationale

- Phase 1 before everything: no webhook, no DB, no bot = nothing works
- Phase 2 before Phase 3: pay for nothing → broken experience → refund demands
- Phase 3 before Phase 4: web cabinet shows payment history; auth tied to users already in DB
- Phase 4 after product-market fit: web is cost without proven need
- Phase 5 is parallel: content automation is the owner's tool, not the user funnel

### Research Flags

Phases needing deeper research or deliberate iteration during planning:
- **Phase 2 (prompt engineering):** Mini-scan teaser and numerology prompts are the core product differentiators — not standard patterns. Plan prompt iteration sprints, not just implementation tickets.
- **Phase 3 (ЮKassa integration):** Webhook payload format and 54-ФЗ `receipt` object fields must be verified against live ЮKassa docs before implementation. Do not code from training data alone.

Phases with standard well-documented patterns:
- **Phase 1:** FastAPI + aiogram webhook wiring is a well-established pattern; skip deep research
- **Phase 4:** Next.js App Router + Telegram Login Widget auth is standard; skip deep research
- **Phase 5:** APScheduler + Telegram Bot API channel posting is straightforward; skip deep research

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (core) | HIGH | aiogram 3.x, FastAPI, PostgreSQL, SQLAlchemy async — stable, dominant choices since 2023 |
| Stack (exact versions) | LOW | All versions are training-data approximations; verify on PyPI/npm before writing requirements.txt |
| Features | HIGH for table stakes; MEDIUM for differentiators | Table stakes patterns consistent across Telegram bot products; differentiator value inferred from InfoBiz market patterns |
| Architecture | HIGH | Monorepo + service layer + webhook patterns well-established; dependency order is deterministic |
| Pitfalls (technical) | HIGH | LLM hallucination, async webhooks, message length — universally documented patterns |
| Pitfalls (legal/payment) | MEDIUM | 54-ФЗ and ЮKassa requirements are stable law/docs but field-level details need live verification |
| Claude model pricing/naming | MEDIUM | Cost estimates directionally correct; model names and exact pricing must be verified at docs.anthropic.com |
| Telegram Stars economics | MEDIUM | API mechanics stable; XTR withdrawal mechanics and rate need live verification |

**Overall confidence:** MEDIUM-HIGH — sufficient to begin Phase 1 development with the pre-code decisions resolved. Two areas require live doc verification before implementation: ЮKassa receipt API and current Claude model names.

### Gaps to Address

- **Claude model names:** Verify current recommended model IDs at https://docs.anthropic.com/en/docs/about-claude/models before writing any `anthropic.messages.create()` calls
- **ЮKassa receipt fields:** Verify `receipt` object structure for 54-ФЗ compliance at https://yookassa.ru/developers before writing PaymentService
- **Telegram Stars withdrawal:** Confirm whether Stars can be converted to RUB by the time of launch; this determines whether Stars-only launch is viable
- **Competitor analysis:** Manually search Telegram for existing business diagnostic bots to calibrate differentiation and pricing
- **Юлия's ИП status:** Confirm registered or registration timeline; this is the longest lead-time item in the entire project

---

## Sources

### Primary (HIGH confidence — training data, stable APIs)
- aiogram 3.x FSM patterns and webhook architecture
- FastAPI + Pydantic v2 + SQLAlchemy 2.x async integration
- Telegram Bot API: message limits, FSM, inline keyboards, channel posting
- Anthropic Python SDK async client patterns
- Claude hallucination behavior in structured-output tasks
- Payment state machine and async webhook handling patterns

### Secondary (MEDIUM confidence — training data, may need live verification)
- ЮKassa Python SDK 3.x integration pattern and webhook payload format
- 54-ФЗ fiscal receipt requirements for digital services
- Russian InfoBiz/coaching market product patterns (2023–2025)
- Telegram Stars economics and XTR exchange rate
- Railway deployment pricing and capabilities
- Claude API pricing tiers and rate limits

### Tertiary (LOW confidence — verify before use)
- Exact package versions (all training-data approximations; run `pip index versions` before use)
- Current Claude model IDs (renamed periodically; check Anthropic docs)
- Specific ЮKassa API field names for `receipt` object

---

*Research completed: 2026-03-19*
*Ready for roadmap: yes — pending resolution of pre-code decisions listed above*
