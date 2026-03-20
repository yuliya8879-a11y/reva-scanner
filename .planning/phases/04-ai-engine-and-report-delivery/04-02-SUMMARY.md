---
phase: 04-ai-engine-and-report-delivery
plan: "02"
subsystem: bot-delivery
tags: [aiogram, fsm, delivery, split-messages, full-scan, tdd]
dependency_graph:
  requires:
    - 04-01 (FullScanAIService, complete_full_scan, BLOCK_KEYS)
  provides:
    - generate_and_deliver_report() coroutine wired into _advance_to_next
    - 8-message split delivery (status + numerology + 6 blocks)
    - Error handling paths for missing birth_date and AI failure
  affects:
    - app/bot/handlers/full_scan.py (modified — adds delivery pipeline)
    - tests/test_full_scan_ai_delivery.py (created — 12 delivery tests)
    - tests/test_full_scan_flow.py (modified — patches delivery in isolation tests)
tech_stack:
  added: []
  patterns:
    - "AsyncMock patching of FullScanAIService for unit-isolated delivery tests"
    - "Loop-based block delivery with _BLOCK_LABELS dict for header mapping"
    - "Error paths set scan.status directly on ORM object then await session.commit()"
key_files:
  created:
    - tests/test_full_scan_ai_delivery.py
  modified:
    - app/bot/handlers/full_scan.py
    - tests/test_full_scan_flow.py
decisions:
  - "_BLOCK_LABELS maps Russian BLOCK_KEYS to display labels including owner apostrophe ('Энергетические блоки owner\\'а') — matches plan spec exactly"
  - "Loop over BLOCK_KEYS for 6 block messages (2 source parse_mode lines produce 7 runtime calls — functionally correct despite grep count mismatch)"
  - "Existing tests in test_full_scan_flow.py patched with generate_and_deliver_report mock to preserve isolation (Rule 1 auto-fix)"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-20"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 2
  tests_added: 12
  tests_total: 142
---

# Phase 04 Plan 02: AI Report Delivery Pipeline Summary

**One-liner:** Wired FullScanAIService into questionnaire completion, delivering 8 split Telegram messages (status + numerology + 6 bold-header blocks) with graceful error handling for missing birth_date and AI failures.

## What Was Built

### generate_and_deliver_report() — /app/bot/handlers/full_scan.py

New async function added before `_send_question()`:

- **Signature:** `async def generate_and_deliver_report(bot, chat_id, scan_id, scan_type, session)`
- **Step 1:** Sends "Генерирую отчёт... Это займёт около 30 секунд."
- **Step 2:** Fetches scan via `ScanService.get_scan()`, extracts `answers`
- **Step 3:** Parses `birth_date` from answers via `date.fromisoformat()` — sets `scan.status=failed` and sends user error on failure
- **Step 4:** Calls `FullScanAIService().generate_full_report(answers, birth_date, scan_type)` — sets `scan.status=failed` and sends user error on exception
- **Step 5:** Calls `scan_service.complete_full_scan()` to store JSONB before delivery
- **Step 6:** Sends numerology message with soul_number and life_path_number
- **Step 7:** Loops over BLOCK_KEYS, sends each block as `*{label}*\n\n{content}` with `parse_mode="Markdown"`

### _advance_to_next() update

Replaced the old `"Запускаю анализ..."` stub block with:
```python
await bot.send_message(chat_id, "Анкета заполнена!")
await state.clear()
await generate_and_deliver_report(bot, chat_id, scan_id, scan_type, session)
```

### _BLOCK_LABELS dict

Maps Russian BLOCK_KEYS to display labels:
- архитектура -> Архитектура
- слепые_зоны -> Слепые зоны
- энергетические_блоки -> Энергетические блоки owner'а
- команда -> Команда
- деньги -> Деньги
- рекомендации -> Рекомендации

## Tests Created (tests/test_full_scan_ai_delivery.py — 12 tests)

| Class | Tests |
|---|---|
| TestGenerateAndDeliverReportHappyPath | 4 tests: 8-message count, status message text, complete_full_scan called, numerology values |
| TestGenerateAndDeliverReportMissingBirthDate | 3 tests: missing key sets failed, error message sent, invalid format sets failed |
| TestGenerateAndDeliverReportAIFailure | 3 tests: AI exception sets failed, error message sent, complete_full_scan not called |
| TestBlockMessagesContainHeaders | 2 tests: 6 block headers with bold Markdown syntax, parse_mode=Markdown |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 2 existing tests broken by _advance_to_next change**
- **Found during:** GREEN phase — full test suite run
- **Issue:** `test_skip_saves_empty_string` and `test_last_question_sends_completion_message` in `tests/test_full_scan_flow.py` both test the last-question scenario (current_index=14). With the new `generate_and_deliver_report` call in `_advance_to_next`, those tests triggered the real delivery code which called `ScanService.get_scan()` — not mocked in those tests, returning a coroutine object instead of a Scan
- **Fix:** Added `patch("app.bot.handlers.full_scan.generate_and_deliver_report", new=AsyncMock())` to both tests so they remain isolated to their original assertions
- **Files modified:** tests/test_full_scan_flow.py
- **Commit:** fd0752a

**2. [Rule 1 - Bug] Fixed test expected label for энергетические_блоки**
- **Found during:** First test run (RED→GREEN transition)
- **Issue:** Test expected `*Энергетические блоки*` but plan spec says the label is `*Энергетические блоки owner'а*`
- **Fix:** Updated expected_labels in `test_all_6_block_messages_have_bold_headers` to match the implementation spec
- **Files modified:** tests/test_full_scan_ai_delivery.py
- **Commit:** fd0752a

## Commits

| Hash | Type | Description |
|---|---|---|
| fe2c8c4 | test | Add failing tests for generate_and_deliver_report (RED) |
| fd0752a | feat | Wire generate_and_deliver_report into full scan questionnaire (GREEN + fixes) |

## Self-Check: PASSED

- FOUND: tests/test_full_scan_ai_delivery.py
- FOUND: app/bot/handlers/full_scan.py
- FOUND commit: fe2c8c4 (RED tests)
- FOUND commit: fd0752a (GREEN implementation)
