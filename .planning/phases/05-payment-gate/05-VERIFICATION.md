---
phase: 05-payment-gate
verified: 2026-03-21T00:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "End-to-end Telegram Stars invoice flow"
    expected: "Tapping buy:personal sends a live Stars invoice in Telegram; pre_checkout query is answered within 10 seconds; after payment the questionnaire starts automatically"
    why_human: "Requires a live Telegram bot token and a real Stars payment — cannot simulate Telegram network calls programmatically"
---

# Phase 5: Payment Gate Verification Report

**Phase Goal:** Users must pay via Telegram Stars before the full scan runs, the payment state machine is race-condition-safe, and every transaction is logged.
**Verified:** 2026-03-21
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PaymentService.create_payment() inserts a Payment row with status=pending and returns the ORM object | VERIFIED | `app/services/payment_service.py` lines 43-53: constructs Payment(status="pending"), session.add, commit, refresh, return. Test `test_create_payment_returns_pending_payment` asserts status=="pending" and commit called — passes. |
| 2 | PaymentService.confirm_payment() sets Payment.status=paid, Payment.paid_at, Scan.is_paid=True, Scan.payment_id — atomically in one commit | VERIFIED | Lines 93-106: sets all four fields then calls `await self.session.commit()` once. Test `test_confirm_payment_sets_paid_fields` asserts all four fields and `commit.assert_called_once()` — passes. |
| 3 | PaymentService.get_pending_payment() returns the most recent pending Payment for a user+scan_type, or None | VERIFIED | Lines 126-137: JOIN Payment+Scan, WHERE status="pending" AND scan_type AND user_id, order by created_at DESC, limit 1. Test `test_get_pending_payment_returns_none_when_empty` passes. |
| 4 | Double-confirm is idempotent: calling confirm_payment() twice does not set paid_at twice or raise | VERIFIED | Lines 90-91: early-return if `payment.status == "paid"` with no commit. Test `test_confirm_payment_idempotent` asserts `commit.assert_not_called()` — passes. |
| 5 | Tapping buy:personal or buy:business sends a Telegram Stars invoice (currency=XTR, empty provider_token, payload=scan:{scan_id}:user:{user_id}) | VERIFIED | `app/bot/handlers/payment.py` lines 69-77: `send_invoice(currency="XTR", provider_token="", payload=f"scan:{scan.id}:user:{user.id}")`. Test `test_handle_buy_callback_sends_invoice` asserts both kwargs — passes. |
| 6 | Full scan questionnaire does NOT start until handle_successful_payment fires — buy:personal/business in full_scan.py no longer starts the questionnaire | VERIFIED | `handle_buy_callback` is absent from `app/bot/handlers/full_scan.py` (import assertion in integration check passes). The function exists only in payment.py and sends an invoice; no FSM state transitions occur there. |
| 7 | handle_pre_checkout_query answers True within 10 seconds (no database calls needed) | VERIFIED | `app/bot/handlers/payment.py` lines 86-89: single `await query.answer(ok=True)` with no session argument in handler signature. Test `test_handle_pre_checkout_query_answers_ok` — passes. |
| 8 | handle_successful_payment calls confirm_payment() then calls start_questionnaire_after_payment() — but only if scan.is_paid is True after confirm | VERIFIED | Lines 110-141: calls confirm_payment, fetches scan, guards on `scan.is_paid`, then calls start_questionnaire_after_payment. Tests `test_handle_successful_payment_triggers_questionnaire` and `test_handle_successful_payment_aborts_if_not_paid` both pass. |
| 9 | start_questionnaire_after_payment() is a standalone async function in full_scan.py, callable by payment handler without circular import | VERIFIED | `full_scan.py` line 210: `async def start_questionnaire_after_payment(...)` — no underscore, public. Deferred import in payment.py line 132 breaks the circular dependency. `python3 -c "from app.bot.handlers.full_scan import start_questionnaire_after_payment"` exits 0. |
| 10 | payment router is included in main_router before full_scan router | VERIFIED | `app/bot/router.py` line 10: `main_router.include_router(payment.router)` appears before line 11: `main_router.include_router(full_scan.router)`. |
| 11 | Tests prove PaymentService state machine correct — all 8 tests pass | VERIFIED | `pytest tests/test_payment_flow.py -v` — 8 collected, 8 passed, exits 0. |
| 12 | Every transaction is logged in the database (Payment row with user_id, amount_stars, status, created_at, telegram_payment_charge_id) | VERIFIED | `app/models/payment.py` defines all required columns. `PaymentService.create_payment` inserts on every buy callback; `confirm_payment` writes telegram_payment_charge_id and paid_at. Payment row persists for both pending and paid states. |
| 13 | Full test suite has no collection errors from phase 5 changes | VERIFIED | `pytest tests/` — 157 passed, 0 failures, 0 errors. The previously-documented `test_full_scan_flow.py` import breakage was fixed: line 16 now correctly imports `handle_buy_callback` from `app.bot.handlers.payment`. |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/payment_service.py` | PaymentService class with create_payment, confirm_payment, get_pending_payment | VERIFIED | 138 lines, all three async methods present, idempotent guard at line 90, atomic commit at line 105 |
| `app/bot/handlers/payment.py` | payment router with handle_buy_callback, handle_pre_checkout_query, handle_successful_payment | VERIFIED | 142 lines, Router(name="payment"), all three handlers registered |
| `app/bot/handlers/full_scan.py` | start_questionnaire_after_payment() public function; handle_buy_callback removed | VERIFIED | start_questionnaire_after_payment at line 210, no handle_buy_callback present |
| `app/bot/router.py` | payment router included before full_scan router | VERIFIED | 12 lines, payment.router at position 3 (before full_scan.router at position 4) |
| `tests/test_payment_flow.py` | Full test coverage of PaymentService and payment bot handlers | VERIFIED | 336 lines, 8 tests, all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/payment_service.py` | `app/models/payment.py Payment` | ORM writes: amount_stars, product_type, status, telegram_payment_charge_id, paid_at | WIRED | Lines 43-48: Payment constructor sets all fields; line 94-95: paid fields set on confirm |
| `app/services/payment_service.py` | `app/models/scan.py Scan` | confirm_payment sets scan.is_paid and scan.payment_id | WIRED | Lines 101-103: `scan.is_paid = True` and `scan.payment_id = payment.id` |
| `app/bot/handlers/payment.py handle_buy_callback` | `app/services/payment_service.py PaymentService.create_payment` | creates Payment row before sending invoice | WIRED | Lines 60-66: `payment_service.create_payment(...)` called before `send_invoice` |
| `app/bot/handlers/payment.py handle_successful_payment` | `app/services/payment_service.py PaymentService.confirm_payment` | payment.successful_payment.telegram_payment_charge_id | WIRED | Lines 110-114: `await payment_service.confirm_payment(telegram_charge_id=charge_id, scan_id=scan_id)` |
| `app/bot/handlers/payment.py handle_successful_payment` | `app/bot/handlers/full_scan.py start_questionnaire_after_payment` | called after confirm; passes bot, chat_id, scan_id, scan_type, state | WIRED | Lines 132-141: deferred import then `await start_questionnaire_after_payment(...)` with all required args |
| `tests/test_payment_flow.py` | `app/services/payment_service.py` | mocked AsyncSession, direct method calls | WIRED | Lines 73, 106, 143, 165: PaymentService imported and invoked in 4 tests |
| `tests/test_payment_flow.py` | `app/bot/handlers/payment.py` | AsyncMock bot, mocked session, mocked services | WIRED | Lines 184, 247, 261, 301: handle_buy_callback, handle_pre_checkout_query, handle_successful_payment all tested |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PAY-01 | 05-02, 05-03 | User can pay for full scan via Telegram Stars | SATISFIED | Stars invoice sent with currency=XTR, provider_token="" in handle_buy_callback; test_handle_buy_callback_sends_invoice passes |
| PAY-02 | 05-01, 05-02, 05-03 | System checks payment before launching full scan and does not launch without confirmation | SATISFIED | handle_successful_payment guards on scan.is_paid after confirm_payment; buy:* callback in full_scan removed; test_handle_successful_payment_aborts_if_not_paid proves the guard works |
| PAY-03 | 05-02, 05-03 | User receives scan automatically after successful payment | SATISFIED | handle_successful_payment calls start_questionnaire_after_payment after confirm; test_handle_successful_payment_triggers_questionnaire passes |
| PAY-04 | 05-01, 05-03 | System logs all transactions to DB (telegram_id, amount, status, timestamp) | SATISFIED | Payment model has user_id (FK to users.telegram_id), amount_stars, status, created_at, paid_at, telegram_payment_charge_id; create_payment inserts on every buy; confirm_payment updates on completion |

All four requirements are satisfied. No orphaned requirements for Phase 5 found in REQUIREMENTS.md.

---

### Anti-Patterns Found

No blockers or warnings found in phase 5 files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TODO/FIXME/placeholder comments found | — | — |
| — | — | No empty return stubs (return null / return {}) found | — | — |
| — | — | No console.log-only implementations | — | — |

One deferred item was documented (`deferred-items.md`) regarding a test regression in `test_full_scan_flow.py`. This was subsequently fixed within the phase — the import was updated to `from app.bot.handlers.payment import handle_buy_callback`. The full suite now runs 157 tests with 0 failures.

---

### Human Verification Required

#### 1. Live Telegram Stars Payment Flow

**Test:** In a real Telegram conversation with the bot, tap the "buy:personal" or "buy:business" button.
**Expected:** A Stars invoice appears in the chat. After paying, the bot immediately sends "Оплата получена!" and the first questionnaire question appears.
**Why human:** Requires a live bot token, real Telegram Stars balance, and Telegram network — cannot replicate pre_checkout timing or real invoice rendering in unit tests.

#### 2. Pre-checkout Query 10-Second Window

**Test:** Trigger a live Stars payment and observe that the pre_checkout query is answered without any visible delay.
**Expected:** No "payment timed out" or "payment failed" error from Telegram.
**Why human:** The 10-second SLA is enforced by Telegram servers, not verifiable via mock tests.

#### 3. Business Scan Price (150 XTR)

**Test:** Tap "buy:business" and verify the invoice shows 150 Stars.
**Expected:** Invoice amount is double the personal price (150 XTR at default STARS_PRICE=75).
**Why human:** Unit test only verifies currency and provider_token, not the actual Stars amount displayed to the user.

---

### Gaps Summary

No gaps. All 13 observable truths are verified. All artifacts exist, are substantive (non-stub), and are wired. All four requirements (PAY-01 through PAY-04) are satisfied with test evidence. The full test suite passes with 157 tests and zero collection errors.

Three items are flagged for human verification — these are live Telegram network behaviors that cannot be proven programmatically but do not block the phase goal assessment.

---

_Verified: 2026-03-21_
_Verifier: Claude (gsd-verifier)_
