# Deferred Items — Phase 05 Payment Gate

## Pre-existing Issue: test_full_scan_flow.py import failure

**Discovered during:** Plan 05-03, Task 1 (full suite run)

**Issue:** `tests/test_full_scan_flow.py` imports `handle_buy_callback` from
`app.bot.handlers.full_scan` (line 18). That function was moved to
`app.bot.handlers.payment` in Plan 05-02.

**Error:**
```
ImportError: cannot import name 'handle_buy_callback' from 'app.bot.handlers.full_scan'
```

**Impact:** `pytest tests/` fails at collection. All other 132 tests pass when
`test_full_scan_flow.py` is excluded.

**Resolution needed:**
- Update `test_full_scan_flow.py` to import `handle_buy_callback` from
  `app.bot.handlers.payment` (or remove the 4 `TestHandleBuyCallback` tests
  since equivalent coverage is now in `test_payment_flow.py`).
- Also update all patch targets inside `TestHandleBuyCallback` from
  `app.bot.handlers.full_scan.*` to `app.bot.handlers.payment.*`.

**Out of scope for 05-03** — this is a pre-existing regression from 05-02 that
requires a dedicated fix (either update or remove the legacy tests).
