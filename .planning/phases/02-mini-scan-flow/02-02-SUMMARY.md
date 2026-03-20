---
phase: 02-mini-scan-flow
plan: 02
subsystem: ui
tags: [aiogram, fsm, telegram, bot, inline-keyboard, mini-scan, ai-integration]

requires:
  - phase: 02-mini-scan-flow/02-01
    provides: ScanService, AIService, UserService, calculate_soul_number numerology helper

provides:
  - MiniScanStates FSM state group (6 states)
  - /start handler with 3 inline keyboard buttons (personal 3500, business 7000, mini-scan free)
  - 5-question mini-scan FSM flow via app/bot/handlers/mini_scan.py
  - UserService.update_birth_date method
  - AI generation with scanning feedback and upsell buttons
  - 21 tests covering FSM states, callback patterns, and date parsing

affects: [03-content-engine, 05-payment-flow, 04-admin-panel]

tech-stack:
  added: []
  patterns:
    - "aiogram FSM with StatesGroup for multi-step conversation flows"
    - "_make_keyboard helper for building one-button-per-row InlineKeyboardMarkup"
    - "Lambda filters on callback_query for callback_data prefix routing (area:, age:, pain:)"
    - "Parse + validate before state transition; stay in state on error"
    - "Immediate scanning feedback (send 'Сканирую...' before async AI call)"
    - "All generation logic in a single async helper _generate_and_send_report"

key-files:
  created:
    - app/bot/states.py
    - app/bot/handlers/mini_scan.py
    - tests/test_mini_scan_flow.py
  modified:
    - app/bot/handlers/start.py
    - app/bot/router.py
    - app/services/user_service.py

key-decisions:
  - "parse_birth_date extracted as a standalone function for testability (not inlined in handler)"
  - "birth_date stored as ISO string in FSM data to survive JSON serialization; re-parsed before numerology call"
  - "scan_type:personal and scan_type:business redirect to mini-scan with explanatory message (payment flow deferred to Phase 5)"
  - "_generate_and_send_report uses message_obj.bot (not imported bot) to avoid circular import with app.main"

patterns-established:
  - "Pattern 1: Callback lambda filters — use lambda c: c.data == 'exact' for exact match, lambda c: c.data.startswith('prefix:') for prefix routing"
  - "Pattern 2: FSM data dict mutation — always copy with dict(data.get('answers', {})) before mutating"
  - "Pattern 3: Scanning feedback — send placeholder message, do async work, delete placeholder, send result"

requirements-completed: [BOT-02, BOT-04, BOT-05, BOT-06, BOT-07]

duration: 12min
completed: 2026-03-20
---

# Phase 2 Plan 2: Mini-Scan Telegram Flow Summary

**aiogram FSM 5-question mini-scan with inline keyboards, birth-date validation, Claude Haiku teaser generation, and upsell buttons wired into existing ScanService/UserService**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-20T08:36:56Z
- **Completed:** 2026-03-20T08:49:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Complete mini-scan Telegram flow: /start inline keyboard -> 5-question FSM -> AI teaser -> upsell
- UserService.update_birth_date persists birth date immediately after Q1 validation
- "Сканирую..." message sent before AI call prevents frozen bot UX; deleted after report arrives
- All 58 project tests pass (21 new + 37 from prior plans)

## Task Commits

1. **Task 1: FSM states, /start update, and birth date handler** - `a324c5f` (feat)
2. **Task 2: Questions 3-5, AI generation with scanning feedback, and upsell** - `19e2284` (feat)

## Files Created/Modified

- `app/bot/states.py` - MiniScanStates FSM group with 6 states
- `app/bot/handlers/start.py` - Updated /start with 3 inline buttons; FSMContext to clear stale state
- `app/bot/handlers/mini_scan.py` - Full 5-question FSM, AI generation helper, upsell keyboard (270 lines)
- `app/bot/router.py` - Includes mini_scan router in addition to start router
- `app/services/user_service.py` - Added update_birth_date method
- `tests/test_mini_scan_flow.py` - 21 tests: MiniScanStates structure, callback data patterns, date parsing

## Decisions Made

- parse_birth_date extracted as a standalone function for testability (not inlined in handler)
- birth_date stored as ISO string in FSM data to survive JSON serialization; re-parsed before numerology call
- scan_type:personal and scan_type:business redirect to mini-scan (payment flow deferred to Phase 5)
- _generate_and_send_report uses message_obj.bot (not imported bot) to avoid circular import with app.main

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Mini-scan flow is complete and tested; ready for Phase 3 (content engine / AI prompt tuning)
- Phase 5 payment flow can attach to existing scan_type:personal and scan_type:business callback entry points
- buy:personal and buy:business callback stubs exist in upsell keyboard for Phase 5 to handle

---
*Phase: 02-mini-scan-flow*
*Completed: 2026-03-20*
