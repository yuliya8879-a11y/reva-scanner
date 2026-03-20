"""Unit tests for ScanService using mocked AsyncSession.

JSONB columns in the Scan model are PostgreSQL-specific and cannot be
created in an SQLite in-memory database. Tests therefore mock the
AsyncSession at the service boundary, testing the service's logic
(field assignments, status transitions, commit/refresh calls) without
requiring a live database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.scan import ScanStatus, ScanType
from app.services.scan_service import ScanService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a fully-mocked AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()  # synchronous
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_scan_mock(scan_id: int = 1, user_id: int = 42) -> MagicMock:
    """Return a MagicMock that behaves like a Scan ORM instance."""
    scan = MagicMock()
    scan.id = scan_id
    scan.user_id = user_id
    scan.scan_type = ScanType.mini.value
    scan.status = ScanStatus.collecting.value
    scan.answers = None
    scan.numerology = None
    scan.mini_report = None
    scan.completed_at = None
    return scan


# ---------------------------------------------------------------------------
# Tests: create_mini_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_mini_scan_sets_type_and_status():
    """create_mini_scan must set scan_type=mini and status=collecting."""
    session = _make_session()
    created_scan = _make_scan_mock()

    session.refresh.return_value = None  # no-op

    service = ScanService(session)

    with patch("app.services.scan_service.Scan") as MockScan:
        MockScan.return_value = created_scan
        result = await service.create_mini_scan(user_id=42)

    MockScan.assert_called_once_with(
        user_id=42,
        scan_type=ScanType.mini.value,
        status=ScanStatus.collecting.value,
    )
    session.add.assert_called_once_with(created_scan)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created_scan)
    assert result is created_scan


# ---------------------------------------------------------------------------
# Tests: update_answers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_answers_stores_answers_and_changes_status():
    """update_answers must set answers JSONB field and status=in_progress."""
    session = _make_session()
    existing_scan = _make_scan_mock(scan_id=5)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_scan
    session.execute.return_value = mock_result
    session.refresh.return_value = None

    service = ScanService(session)
    answers = {"business_area": "IT", "business_age": "2 years", "main_pain": "no clients"}

    result = await service.update_answers(scan_id=5, answers=answers)

    assert result.answers == answers
    assert result.status == ScanStatus.in_progress.value
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(existing_scan)


# ---------------------------------------------------------------------------
# Tests: complete_mini_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_mini_scan_sets_all_fields():
    """complete_mini_scan must set mini_report, numerology, status, and completed_at."""
    session = _make_session()
    existing_scan = _make_scan_mock(scan_id=7)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_scan
    session.execute.return_value = mock_result
    session.refresh.return_value = None

    service = ScanService(session)
    report = "Твой бизнес теряет клиентов из-за слабого оффера."
    numerology = {"soul_number": 3}
    token_usage = {"input_tokens": 150, "output_tokens": 80}

    before = datetime.now(timezone.utc)
    result = await service.complete_mini_scan(
        scan_id=7,
        mini_report=report,
        numerology=numerology,
        token_usage=token_usage,
    )
    after = datetime.now(timezone.utc)

    assert result.mini_report == report
    assert result.status == ScanStatus.completed.value
    assert result.numerology == {"soul_number": 3, "token_usage": token_usage}
    assert result.completed_at is not None
    assert before <= result.completed_at <= after
    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: get_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_scan_returns_scan_when_found():
    """get_scan must return the Scan when it exists."""
    session = _make_session()
    existing_scan = _make_scan_mock(scan_id=3)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_scan
    session.execute.return_value = mock_result

    service = ScanService(session)
    result = await service.get_scan(scan_id=3)

    assert result is existing_scan


@pytest.mark.asyncio
async def test_get_scan_returns_none_when_not_found():
    """get_scan must return None when scan does not exist."""
    session = _make_session()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    service = ScanService(session)
    result = await service.get_scan(scan_id=999)

    assert result is None
