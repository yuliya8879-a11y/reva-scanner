"""Unit tests for PaymentService using mocked AsyncSession.

JSONB columns in the Scan model are PostgreSQL-specific. Tests mock the
AsyncSession at the service boundary, testing field assignments, status
transitions, and idempotency — without requiring a live database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.payment import Payment
from app.models.scan import Scan


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


def _make_payment_mock(
    payment_id: int = 10,
    user_id: int = 42,
    scan_id: int = 5,
    status: str = "pending",
) -> MagicMock:
    """Return a MagicMock that behaves like a Payment ORM instance."""
    payment = MagicMock(spec=Payment)
    payment.id = payment_id
    payment.user_id = user_id
    payment.scan_id = scan_id
    payment.amount_stars = 100
    payment.product_type = "personal"
    payment.status = status
    payment.telegram_payment_charge_id = None
    payment.paid_at = None
    payment.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return payment


def _make_scan_mock(
    scan_id: int = 5,
    user_id: int = 42,
    scan_type: str = "personal",
) -> MagicMock:
    """Return a MagicMock that behaves like a Scan ORM instance."""
    scan = MagicMock(spec=Scan)
    scan.id = scan_id
    scan.user_id = user_id
    scan.scan_type = scan_type
    scan.is_paid = False
    scan.payment_id = None
    return scan


def _make_execute_result(obj) -> AsyncMock:
    """Wrap obj in a mock that mimics session.execute result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    execute_result = AsyncMock()
    execute_result.__await__ = AsyncMock(return_value=result).__await__
    return result


# ---------------------------------------------------------------------------
# Tests: create_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_payment_inserts_pending_payment():
    """create_payment must insert a Payment with status=pending."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    payment_mock = _make_payment_mock()

    # After refresh the service returns whatever is in payment_mock
    # Capture the Payment object passed to session.add
    captured = {}

    def capture_add(obj):
        captured["payment"] = obj

    session.add.side_effect = capture_add
    session.refresh.side_effect = None  # no-op

    svc = PaymentService(session)
    # We need refresh to return a proper payment — after session.add we
    # make execute return our mock on subsequent calls but for create_payment
    # the service does not call execute; it just adds, commits, refreshes.
    # Let's just call it and verify add+commit+refresh are called.

    # To test the returned object we make refresh set attributes on the Payment
    # passed to session.add after commit
    async def fake_refresh(obj):
        obj.id = 10  # simulate DB-assigned PK

    session.refresh.side_effect = fake_refresh

    result = await svc.create_payment(
        user_id=42,
        scan_id=5,
        amount_stars=100,
        product_type="personal",
    )

    # session.add was called once
    session.add.assert_called_once()
    # commit was called
    session.commit.assert_called_once()
    # refresh was called with the payment object
    session.refresh.assert_called_once()

    # The payment added had status=pending
    added_payment = captured["payment"]
    assert added_payment.status == "pending"
    assert added_payment.user_id == 42
    assert added_payment.scan_id == 5
    assert added_payment.amount_stars == 100
    assert added_payment.product_type == "personal"


@pytest.mark.asyncio
async def test_create_payment_returns_payment_after_refresh():
    """create_payment must return the ORM object after refresh."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    svc = PaymentService(session)

    result = await svc.create_payment(
        user_id=1, scan_id=2, amount_stars=50, product_type="business"
    )

    # Result is the Payment instance (same object as passed to refresh)
    assert result is not None
    # It should be a Payment (real class, not mock — because create_payment
    # constructs Payment(...) directly)
    assert isinstance(result, Payment)


# ---------------------------------------------------------------------------
# Tests: confirm_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_payment_sets_paid_status_and_scan_fields():
    """confirm_payment must set status=paid, paid_at, charge_id on Payment
    and is_paid=True, payment_id on Scan in one commit."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    payment_mock = _make_payment_mock(status="pending")
    scan_mock = _make_scan_mock()

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.scalar_one_or_none.return_value = payment_mock
        else:
            result.scalar_one_or_none.return_value = scan_mock
        call_count += 1
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    returned = await svc.confirm_payment(
        telegram_charge_id="charge_abc123", scan_id=5
    )

    assert payment_mock.status == "paid"
    assert payment_mock.telegram_payment_charge_id == "charge_abc123"
    assert payment_mock.paid_at is not None
    assert scan_mock.is_paid is True
    assert scan_mock.payment_id == payment_mock.id
    session.commit.assert_called_once()
    assert returned is payment_mock


@pytest.mark.asyncio
async def test_confirm_payment_idempotent_when_already_paid():
    """confirm_payment called twice must not re-set paid_at or raise."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    original_paid_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    payment_mock = _make_payment_mock(status="paid")
    payment_mock.paid_at = original_paid_at

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = payment_mock
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    returned = await svc.confirm_payment(
        telegram_charge_id="charge_xyz", scan_id=5
    )

    # No commit on already-paid payment
    session.commit.assert_not_called()
    # paid_at unchanged
    assert payment_mock.paid_at == original_paid_at
    assert returned is payment_mock


@pytest.mark.asyncio
async def test_confirm_payment_raises_when_no_payment():
    """confirm_payment raises ValueError when no Payment found for scan_id."""
    from app.services.payment_service import PaymentService

    session = _make_session()

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    with pytest.raises(ValueError, match="No payment found"):
        await svc.confirm_payment(telegram_charge_id="x", scan_id=99)


# ---------------------------------------------------------------------------
# Tests: get_pending_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pending_payment_returns_payment_when_found():
    """get_pending_payment returns the most recent pending Payment."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    payment_mock = _make_payment_mock(status="pending")

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = payment_mock
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    result = await svc.get_pending_payment(user_id=42, scan_type="personal")
    assert result is payment_mock


@pytest.mark.asyncio
async def test_get_pending_payment_returns_none_when_not_found():
    """get_pending_payment returns None when no pending payment exists."""
    from app.services.payment_service import PaymentService

    session = _make_session()

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    result = await svc.get_pending_payment(user_id=99, scan_type="business")
    assert result is None
