---
phase: 05-payment-gate
plan: "02"
subsystem: bot-payment-handlers
tags: [payment, telegram-stars, handlers, router, fsm]
dependency_graph:
  requires:
    - 05-01  # PaymentService (create_payment, confirm_payment)
  provides:
    - payment router registered in main_router
    - Stars invoice flow end-to-end wired
    - start_questionnaire_after_payment() public function
  affects:
    - app/bot/handlers/full_scan.py
    - app/bot/router.py
tech_stack:
  added: []
  patterns:
    - deferred-import to break circular dependency between payment.py and full_scan.py
    - empty provider_token for Telegram Stars (XTR currency)
    - idempotency guard via scan.is_paid check before starting questionnaire
key_files:
  created:
    - app/bot/handlers/payment.py
  modified:
    - app/bot/handlers/full_scan.py
    - app/bot/router.py
decisions:
  - Deferred import of start_questionnaire_after_payment inside handle_successful_payment body to avoid circular import at module load time
  - payment router registered before full_scan router so buy:* callbacks are intercepted by payment.py, not full_scan.py
  - handle_buy_callback removed entirely from full_scan.py — questionnaire no longer starts on buy tap, only after Stars payment confirmed
metrics:
  duration: 10min
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_changed: 3
---

# Phase 05 Plan 02: Payment Handler Wiring Summary

**One-liner:** Telegram Stars invoice flow wired end-to-end — buy:* callbacks send XTR invoice, successful_payment confirms payment and launches full scan questionnaire.

## What Was Built

Three file changes wire the Stars payment gate into the bot:

**app/bot/handlers/payment.py (new)** — Payment router with three handlers:
- `handle_buy_callback`: intercepts `buy:personal`/`buy:business` callbacks, creates Scan + Payment records, sends Telegram Stars invoice (`currency="XTR"`, `provider_token=""`)
- `handle_pre_checkout_query`: answers `ok=True` with no database work (satisfies 10-second Telegram requirement)
- `handle_successful_payment`: confirms payment via `PaymentService.confirm_payment()`, guards on `scan.is_paid` (race-condition protection), then calls `start_questionnaire_after_payment()`

**app/bot/handlers/full_scan.py (modified):**
- Removed `handle_buy_callback` entirely — questionnaire no longer starts immediately on buy tap
- Added `start_questionnaire_after_payment()` as a public function (no underscore prefix), callable by payment handler without circular import. Resumes from the first unanswered question or question 0 for fresh scans.

**app/bot/router.py (modified):**
- Added `payment` to handler imports
- Registered `payment.router` before `full_scan.router` so `buy:*` callbacks are captured by the payment handler

## Key Design Choices

| Decision | Rationale |
|---|---|
| Deferred import of `start_questionnaire_after_payment` inside function body | Prevents circular import at module load: payment.py → full_scan.py, full_scan.py does not import payment.py |
| payment router before full_scan in main_router | Ensures `buy:personal`/`buy:business` callbacks reach payment handler first |
| `scan.is_paid` guard after `confirm_payment` | Protects against race condition from Telegram webhook retries — questionnaire only starts if payment truly persisted |

## Commits

| Task | Commit | Description |
|---|---|---|
| 1 | e6f4477 | feat(05-02): create payment.py — Telegram Stars invoice flow |
| 2 | 5a3cb24 | feat(05-02): refactor full_scan.py and update router.py for payment gate |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] app/bot/handlers/payment.py created (141 lines, 3 handlers)
- [x] handle_buy_callback absent from full_scan.py
- [x] start_questionnaire_after_payment present in full_scan.py at line 210
- [x] payment.router in main_router before full_scan.router
- [x] commit e6f4477 exists
- [x] commit 5a3cb24 exists
