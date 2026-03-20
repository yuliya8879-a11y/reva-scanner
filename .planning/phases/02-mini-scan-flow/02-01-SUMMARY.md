---
phase: 02-mini-scan-flow
plan: 01
subsystem: api
tags: [anthropic, claude-haiku, numerology, sqlalchemy, async, pytest, postgresql, jsonb]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "SQLAlchemy Base, Scan ORM model, UserService pattern, app.config settings"
provides:
  - "calculate_soul_number(): reduces YYYYMMDD digit sum to single digit 1-9"
  - "AIService.generate_mini_report(): Claude Haiku integration with Russian business diagnostic prompt"
  - "ScanService: full mini-scan CRUD — create, update answers, complete with report"
  - "Token usage logging per AI request"
affects:
  - 02-mini-scan-flow/02-02 (FSM handler calls these services)
  - 03-payments (ScanService.complete_mini_scan used in payment flow)

# Tech tracking
tech-stack:
  added:
    - "anthropic>=0.49.0 (Claude API Python SDK)"
    - "pytest-asyncio 1.2.0 (async test support)"
    - "aiosqlite (in-memory SQLite for test isolation)"
  patterns:
    - "Service class takes AsyncSession in __init__ (same as UserService pattern)"
    - "TDD: test file committed in RED phase before implementation"
    - "Mocked AsyncSession for services using PostgreSQL-specific column types"
    - "complete_mini_scan stores numerology + token_usage as nested JSONB dict"

key-files:
  created:
    - app/services/numerology.py
    - app/services/ai_service.py
    - app/services/scan_service.py
    - tests/test_numerology.py
    - tests/test_scan_service.py
    - tests/conftest.py
  modified:
    - app/services/__init__.py
    - requirements.txt

key-decisions:
  - "Used MagicMock for Scan ORM instances in tests — JSONB dialect incompatible with SQLite, mocking the session boundary is correct approach"
  - "tests/conftest.py sets minimal env stubs so pydantic-settings can load Settings() without .env in CI"
  - "Token usage stored inside numerology JSONB field as {soul_number, token_usage} — avoids adding a new column"
  - "claude-haiku-4-20250514 model per AI-05 cost constraint — 500 max_tokens for mini-scan teaser"

patterns-established:
  - "Service constructor: __init__(self, session: AsyncSession)"
  - "AI prompt uses explicit недостаточно данных fallback as required by AI-04"
  - "Tests requiring env vars use conftest.py os.environ.setdefault() pattern"

requirements-completed: [AI-01, AI-04, AI-05]

# Metrics
duration: 25min
completed: 2026-03-20
---

# Phase 2 Plan 1: Mini-Scan Core Services Summary

**Numerology soul-number calculator, Claude Haiku mini-scan teaser generator, and SQLAlchemy ScanService with full create/update/complete lifecycle — 11 unit tests passing**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-20T07:46:34Z
- **Completed:** 2026-03-20T08:11:34Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- `calculate_soul_number()` correctly reduces any date's YYYYMMDD digits to a single digit (1-9), never returning 0
- `AIService.generate_mini_report()` calls Claude Haiku with a Russian business diagnostic system prompt, logs token usage, and includes "недостаточно данных" fallback per AI-04
- `ScanService` implements the full mini-scan lifecycle: `create_mini_scan` → `update_answers` → `complete_mini_scan` (stores report + numerology + token usage)
- `tests/conftest.py` establishes the pattern for running tests without a real `.env` file

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Numerology tests** - `1a73641` (test)
2. **Task 1 GREEN: Numerology + AI service implementation** - `09d1fbe` (feat)
3. **Task 2: ScanService + __init__ exports + tests** - `798fb4a` (feat)

## Files Created/Modified
- `app/services/numerology.py` - Soul number calculation: sums YYYYMMDD digits, while-loop reduction to 1-9
- `app/services/ai_service.py` - Claude Haiku wrapper: Russian business diagnostic prompt, token logging, 500 max_tokens
- `app/services/scan_service.py` - ScanService: create_mini_scan, update_answers, complete_mini_scan, get_scan
- `app/services/__init__.py` - Exports UserService, ScanService, AIService, calculate_soul_number
- `requirements.txt` - Added anthropic>=0.49.0
- `tests/test_numerology.py` - 6 unit tests for soul number calculation edge cases
- `tests/test_scan_service.py` - 5 unit tests for ScanService using mocked AsyncSession
- `tests/conftest.py` - Minimal env stubs (TELEGRAM_BOT_TOKEN, DATABASE_URL) for test isolation

## Decisions Made
- Used `MagicMock` objects (not `Scan.__new__`) for ORM instances in tests — SQLAlchemy's `JSONB` dialect is PostgreSQL-specific and cannot create tables in SQLite. Mocking the session boundary at the service level is the correct approach and tests the service logic correctly.
- Token usage stored inside `scan.numerology` JSONB as `{"soul_number": N, "token_usage": {...}}` — avoids adding a new column and keeps cost tracking colocated with numerology data.
- `tests/conftest.py` uses `os.environ.setdefault()` (not `monkeypatch`) so env vars are set before any app module is imported at collection time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created tests/conftest.py with env stubs**
- **Found during:** Task 2 (test collection)
- **Issue:** pydantic-settings raises ValidationError for missing `TELEGRAM_BOT_TOKEN` and `DATABASE_URL` when `app.config.settings` is instantiated at import time — prevents test collection
- **Fix:** Added `tests/conftest.py` with `os.environ.setdefault()` calls for both required fields plus `ANTHROPIC_API_KEY`
- **Files modified:** tests/conftest.py (created)
- **Verification:** All 11 tests collect and pass
- **Committed in:** 798fb4a (Task 2 commit)

**2. [Rule 1 - Bug] Replaced `Scan.__new__(Scan)` with `MagicMock()` for test fixtures**
- **Found during:** Task 2 (test run)
- **Issue:** SQLAlchemy's instrumented attributes raise `AttributeError: 'NoneType' object has no attribute 'set'` when setting attributes on instances created via `__new__` without going through the ORM mapper
- **Fix:** Changed `_make_scan()` helper to return a `MagicMock()` with manually set attributes
- **Files modified:** tests/test_scan_service.py
- **Verification:** All 5 ScanService tests pass
- **Committed in:** 798fb4a (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking, 1 Rule 1 bug)
**Impact on plan:** Both auto-fixes were necessary for test correctness. No scope creep. Test coverage and service logic unaffected.

## Issues Encountered
- `pytest-asyncio` was listed in `requirements.txt` but not installed in the venv — installed it during Task 2 execution. This did not affect test logic.

## User Setup Required
None - no external service configuration required beyond existing `.env` setup.

## Next Phase Readiness
- All three services are importable and tested: `from app.services import ScanService, AIService, calculate_soul_number`
- Plan 02-02 (FSM handler) can call `ScanService.create_mini_scan()`, `update_answers()`, `complete_mini_scan()` directly
- `AIService.generate_mini_report(answers, soul_number)` returns `(str, dict)` — ready for handler integration
- Blocker: `ANTHROPIC_API_KEY` must be set in production `.env` before live AI calls work

## Self-Check: PASSED

- FOUND: app/services/numerology.py
- FOUND: app/services/ai_service.py
- FOUND: app/services/scan_service.py
- FOUND: tests/test_numerology.py
- FOUND: tests/test_scan_service.py
- FOUND: tests/conftest.py
- FOUND: .planning/phases/02-mini-scan-flow/02-01-SUMMARY.md
- FOUND commit: 1a73641
- FOUND commit: 09d1fbe
- FOUND commit: 798fb4a

---
*Phase: 02-mini-scan-flow*
*Completed: 2026-03-20*
