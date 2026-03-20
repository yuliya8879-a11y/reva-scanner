---
phase: 03-full-scan-questionnaire
plan: 01
subsystem: database
tags: [aiogram, fsm, sqlalchemy, jsonb, questionnaire, bot]

# Dependency graph
requires:
  - phase: 02-mini-scan-flow
    provides: ScanService with AsyncSession mock pattern, ScanType/ScanStatus enums, Scan JSONB model

provides:
  - QuestionDef dataclass and PERSONAL_QUESTIONS (15) / BUSINESS_QUESTIONS (12) lists in app/bot/questions.py
  - FullScanStates FSM group (q0-q14 + completing) in app/bot/states.py
  - ScanStatus.questionnaire_complete enum value in app/models/scan.py
  - ScanService.create_full_scan(), save_answer(), get_incomplete_scan(), complete_questionnaire(), get_answer_count()

affects:
  - 03-02-full-scan-fsm-handlers (consumes QuestionDef, FullScanStates, and all 5 new service methods)
  - 04-full-scan-ai-generation (consumes complete_questionnaire and questionnaire_complete status)
  - 05-payments (reads scan.answers for report generation trigger)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - QuestionDef dataclass for typed question definitions with keyboard/text input variants
    - BUSINESS_QUESTIONS reuses first 10 entries from PERSONAL_QUESTIONS via list slicing
    - ScanService answer merging uses dict spread {**(scan.answers or {}), key: value} for SQLAlchemy JSONB mutation detection
    - TDD with AsyncMock session boundary (no live DB) carried forward from Phase 02

key-files:
  created:
    - app/bot/questions.py
    - tests/test_full_scan_questions.py
  modified:
    - app/bot/states.py
    - app/models/scan.py
    - app/services/scan_service.py
    - tests/test_scan_service.py

key-decisions:
  - "BUSINESS_QUESTIONS Q1-Q10 share exact same QuestionDef objects as PERSONAL_QUESTIONS via list slicing — avoids duplication, both scan types ask the same opening 10 questions"
  - "FullScanStates has 15 numbered states (q0-q14) to cover max personal question count; business scan uses only q0-q11 but same FSM group works for both"
  - "ScanStatus.questionnaire_complete inserted between in_progress and completed to represent state after all questions answered but before AI report generation"

patterns-established:
  - "QuestionDef.max_length set only on text questions with an explicit limit (current_situation: 1000, product_description: 1000); None means no limit"
  - "get_questions_for_type() raises ValueError for unknown types — fail-fast over silent fallback"
  - "save_answer() never changes status — questionnaire stays in 'collecting' throughout all question answers, only complete_questionnaire() advances it"

requirements-completed: [BOT-03, BOT-06]

# Metrics
duration: 5min
completed: 2026-03-20
---

# Phase 3 Plan 01: Full Scan Questionnaire Foundation Summary

**QuestionDef dataclass with 15-question personal and 12-question business lists, FullScanStates FSM group, and 5 new ScanService methods for incremental answer persistence and scan resumption**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T09:25:50Z
- **Completed:** 2026-03-20T09:30:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Created `app/bot/questions.py` with typed `QuestionDef` dataclass and complete Russian-text question lists for both personal (15 questions) and business (12 questions) scan types, including helper functions `get_questions_for_type()` and `get_total_questions()`
- Extended `app/bot/states.py` with `FullScanStates` FSM group covering q0-q14 (15 indexed states) plus a `completing` state for post-questionnaire transition
- Extended `app/models/scan.py` and `app/services/scan_service.py` with `questionnaire_complete` status and five new service methods enabling incremental answer persistence and incomplete scan lookup for resume capability

## Task Commits

Each task was committed atomically:

1. **Task 1: Question definitions module and FullScanStates** - `91594f7` (feat)
2. **Task 2: Extend ScanService for full scan persistence** - `67bfc4d` (feat)

_Note: Both tasks used TDD — tests written RED first, implementation GREEN._

## Files Created/Modified

- `app/bot/questions.py` - QuestionDef dataclass, PERSONAL_QUESTIONS (15), BUSINESS_QUESTIONS (12), get_questions_for_type(), get_total_questions()
- `app/bot/states.py` - Added FullScanStates with q0-q14 + completing; MiniScanStates unchanged
- `app/models/scan.py` - Added ScanStatus.questionnaire_complete between in_progress and completed
- `app/services/scan_service.py` - Added create_full_scan, save_answer, get_incomplete_scan, complete_questionnaire, get_answer_count
- `tests/test_full_scan_questions.py` - 24 new tests for question definitions and FSM states
- `tests/test_scan_service.py` - 12 new tests for ScanService full scan methods (17 total, all pass)

## Decisions Made

- BUSINESS_QUESTIONS reuses first 10 QuestionDef objects from PERSONAL_QUESTIONS via list slicing (`*PERSONAL_QUESTIONS[:10]`) — Q1-Q10 are identical for both scan types, eliminating duplication
- `FullScanStates` has 15 numbered states to cover personal scan's max question count; business scan (12 questions) uses only q0-q11 — same FSM group serves both types
- `save_answer()` uses dict spread `{**(scan.answers or {}), key: value}` to create a new dict object, ensuring SQLAlchemy JSONB mutation detection triggers a DB write

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-02 (FSM handlers) can now consume `PERSONAL_QUESTIONS`, `BUSINESS_QUESTIONS`, `FullScanStates`, and all 5 new `ScanService` methods
- Data contracts fully established: question iteration, state mapping, incremental persistence, and scan resumption are all available
- No blockers for Plan 03-02 execution

---
*Phase: 03-full-scan-questionnaire*
*Completed: 2026-03-20*
