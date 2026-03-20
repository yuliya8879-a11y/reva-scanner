# Roadmap: Reva Scanner

## Overview

Reva Scanner is built in eight phases that follow a strict dependency chain: infrastructure first, then the free scan funnel that proves the product, then the payment gate that monetizes it, then admin and content automation that make it self-running. The web cabinet is deferred to v2. Every v1 requirement maps to exactly one phase; no phase delivers work that the next phase depends on being absent.

## Phases

**Phase Numbering:**
- Integer phases (1-8): Planned milestone work
- Decimal phases: Urgent insertions (marked INSERTED)

- [ ] **Phase 1: Foundation** - Project skeleton, Railway deploy, PostgreSQL schema, bot webhook wired
- [ ] **Phase 2: Mini-Scan Flow** - Free 5-question FSM, AI teaser generation, birth date capture
- [ ] **Phase 3: Full Scan Questionnaire** - 12-15 question FSM, social URL input, upgrade CTA from mini-scan
- [ ] **Phase 4: AI Engine and Report Delivery** - Full 6-block Claude report, numerology layer, Telegram delivery
- [ ] **Phase 5: Payment Gate** - Telegram Stars payment, state machine, scan unlock after confirmation
- [ ] **Phase 6: Admin Panel** - Client list command, manual message dispatch, basic operations
- [ ] **Phase 7: Content Generation** - Post drafts, Reels scripts, monthly content plan via Claude
- [ ] **Phase 8: Content Scheduler** - APScheduler, auto-posting to @Reva_mentor, admin trigger command

## Phase Details

### Phase 1: Foundation
**Goal**: A deployable bot skeleton on Railway with a working webhook and a complete database schema that every later phase builds on.
**Depends on**: Nothing (first phase)
**Requirements**: BOT-01, DB-01, DB-02, DB-03
**Success Criteria** (what must be TRUE):
  1. User sends /start to the bot and receives a welcome message describing the scanner.
  2. Bot is reachable via Telegram webhook (not polling) on a live Railway URL.
  3. PostgreSQL schema is migrated: tables for users, scans, payments, and content_queue exist.
  4. User profile row (telegram_id, name, registration date) is created automatically on first /start.
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Config, database layer, all four ORM models, UserService, test scaffold
- [ ] 01-02-PLAN.md — Alembic async migration for all four tables, Railway release command
- [ ] 01-03-PLAN.md — FastAPI webhook integration, /start handler, Dockerfile, webhook integration tests

### Phase 2: Mini-Scan Flow
**Goal**: Users can complete a free 5-question diagnostic and receive a teaser report that names one specific business pain point, setting up the paid conversion.
**Depends on**: Phase 1
**Requirements**: BOT-02, BOT-04, BOT-05, BOT-07, AI-01, AI-04, AI-05
**Success Criteria** (what must be TRUE):
  1. User navigates the mini-scan entirely via inline keyboard buttons (no free-text required except the optional situation field).
  2. User enters a birth date and the system stores it in their profile for later numerology analysis.
  3. User sees a "сканирую..." message immediately after submitting answers — the bot never appears frozen.
  4. User receives a teaser report naming one specific, uncomfortable business truth (not a generic tip).
  5. A full mini-scan costs less than $0.05 in Claude API (Haiku used; token usage logged per request).
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Core services: numerology calculator, Claude AI teaser service, scan persistence service
- [ ] 02-02-PLAN.md — FSM mini-scan flow: /start keyboard, 5-question FSM, scanning feedback, report delivery, upsell

### Phase 3: Full Scan Questionnaire
**Goal**: Users who have seen the teaser can launch the full 12-15 question scan with one button, provide a social/site URL, and have all inputs persisted for the AI engine.
**Depends on**: Phase 2
**Requirements**: BOT-03, BOT-06
**Success Criteria** (what must be TRUE):
  1. User taps one button inside the teaser report and the full scan questionnaire starts immediately.
  2. User progresses through 12-15 button-driven questions with a visible progress indicator (вопрос X из Y).
  3. User can optionally enter a URL to a social media profile or website; the field is skippable.
  4. User can close Telegram mid-questionnaire and resume exactly where they left off on next /start.
**Plans**: TBD

### Phase 4: AI Engine and Report Delivery
**Goal**: The full Claude-powered diagnostic is generated correctly — 6 structured blocks, numerology layer, delivered as split Telegram messages — and every generated report is stored in the database.
**Depends on**: Phase 3
**Requirements**: BOT-08, AI-02, AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. User receives a full report with all six named blocks: Архитектура, Слепые зоны, Энергетические блоки, Команда, Деньги, Рекомендации.
  2. Report references the user's birth date in a numerology section that is visibly specific to their date (not a generic template).
  3. When questionnaire answers are thin or ambiguous, the report explicitly says "недостаточно данных" for that block instead of fabricating conclusions.
  4. Report is stored as JSONB in the database (not raw text) and is retrievable by telegram_id.
  5. Full report cost per scan does not exceed $0.40 in Claude API (Sonnet for report; token usage logged).
**Plans**: TBD

### Phase 5: Payment Gate
**Goal**: Users must pay via Telegram Stars before the full scan runs, the payment state machine is race-condition-safe, and every transaction is logged.
**Depends on**: Phase 4
**Requirements**: PAY-01, PAY-02, PAY-03, PAY-04
**Success Criteria** (what must be TRUE):
  1. User is presented with a Telegram Stars payment invoice (3500 RUB equivalent) when they attempt to start a full scan.
  2. Full scan does not start until payment webhook confirms success — no exploit window exists where payment is bypassed.
  3. User sees a "ждем подтверждения..." message after paying and receives the full report automatically within 60 seconds of confirmation.
  4. Every transaction is logged in the database with telegram_id, amount, status, and timestamp.
**Plans**: TBD

### Phase 6: Admin Panel
**Goal**: Yulia can inspect all clients and their scans, and send arbitrary messages to any client directly through the bot, without touching the database.
**Depends on**: Phase 5
**Requirements**: ADM-01, ADM-02
**Success Criteria** (what must be TRUE):
  1. Yulia sends /admin and receives a paginated list of clients showing telegram_id, name, and scan count.
  2. Yulia can send a custom text message to any client by user ID via a bot command and the client receives it in Telegram.
  3. /admin command is protected — non-admin users receive no response or an access-denied message.
**Plans**: TBD

### Phase 7: Content Generation
**Goal**: Yulia can generate post drafts, Reels scripts, and a 30-topic monthly content plan for @Reva_mentor on demand, all via the bot.
**Depends on**: Phase 1
**Requirements**: CNT-01, CNT-02, CNT-03
**Success Criteria** (what must be TRUE):
  1. Yulia provides a topic and the bot returns a complete post draft for @Reva_mentor (hook, body, CTA) in one Claude call.
  2. Yulia provides a topic and the bot returns a Reels script with a named hook, body, and CTA — formatted for direct use.
  3. Yulia requests a content plan and the bot returns 30 topic-title pairs covering a calendar month, ready to copy into a planner.
**Plans**: TBD

### Phase 8: Content Scheduler
**Goal**: Posts queued in the database are published to @Reva_mentor automatically on schedule, without Yulia needing to trigger each one manually.
**Depends on**: Phase 7
**Requirements**: CNT-04
**Success Criteria** (what must be TRUE):
  1. A post queued in the content_queue table is published to @Reva_mentor at its scheduled time without manual intervention.
  2. Yulia can trigger immediate publishing of a queued post via an admin command.
  3. If the bot loses its admin status in the channel, it logs the failure and does not silently drop the post.
**Plans**: TBD

## Progress

**Execution Order:**
Phases 1 → 2 → 3 → 4 → 5 → 6 in sequence. Phase 7 can start after Phase 1 (parallel track). Phase 8 depends on Phase 7.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Not started | - |
| 2. Mini-Scan Flow | 1/2 | In Progress|  |
| 3. Full Scan Questionnaire | 0/TBD | Not started | - |
| 4. AI Engine and Report Delivery | 0/TBD | Not started | - |
| 5. Payment Gate | 0/TBD | Not started | - |
| 6. Admin Panel | 0/TBD | Not started | - |
| 7. Content Generation | 0/TBD | Not started | - |
| 8. Content Scheduler | 0/TBD | Not started | - |
