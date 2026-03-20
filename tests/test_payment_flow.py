"""Payment flow test suite — Phase 5 Plan 3.

Tests both PaymentService (unit, mocked AsyncSession) and payment bot handlers
(mocked bot, session, and service dependencies). No real DB or Telegram API.
"""

from __future__ import annotations

import os

# Set required env vars BEFORE any app module is imported.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("STARS_PRICE", "75")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a fully-mocked AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_payment_mock(payment_id: int = 5, scan_id: int = 10, status: str = "pending") -> MagicMock:
    payment = MagicMock()
    payment.id = payment_id
    payment.scan_id = scan_id
    payment.status = status
    payment.paid_at = None
    payment.telegram_payment_charge_id = None
    return payment


def _make_scan_mock(
    scan_id: int = 10,
    user_id: int = 1,
    is_paid: bool = False,
    scan_type: str = "personal",
) -> MagicMock:
    scan = MagicMock()
    scan.id = scan_id
    scan.user_id = user_id
    scan.is_paid = is_paid
    scan.scan_type = scan_type
    scan.payment_id = None
    scan.answers = {}
    return scan


# ---------------------------------------------------------------------------
# PaymentService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_payment_returns_pending_payment():
    """create_payment must insert a Payment with status=pending and call commit."""
    from app.services.payment_service import PaymentService

    session = _make_session()

    captured = {}

    def capture_add(obj):
        captured["payment"] = obj

    session.add.side_effect = capture_add

    svc = PaymentService(session)
    result = await svc.create_payment(
        user_id=1,
        scan_id=10,
        amount_stars=75,
        product_type="personal",
    )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()

    added = captured["payment"]
    assert added.status == "pending"
    assert added.user_id == 1
    assert added.scan_id == 10
    assert added.amount_stars == 75
    assert added.product_type == "personal"


@pytest.mark.asyncio
async def test_confirm_payment_sets_paid_fields():
    """confirm_payment must set status=paid, paid_at, is_paid=True, payment_id on Scan."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    payment_mock = _make_payment_mock(payment_id=5, scan_id=10, status="pending")
    scan_mock = _make_scan_mock(scan_id=10, is_paid=False)

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
    returned = await svc.confirm_payment(telegram_charge_id="charge_abc", scan_id=10)

    assert payment_mock.status == "paid"
    assert payment_mock.paid_at is not None
    assert scan_mock.is_paid is True
    assert scan_mock.payment_id == payment_mock.id
    session.commit.assert_called_once()
    assert returned is payment_mock


@pytest.mark.asyncio
async def test_confirm_payment_idempotent():
    """confirm_payment on already-paid Payment must return it without calling commit."""
    from app.services.payment_service import PaymentService

    session = _make_session()
    payment_mock = _make_payment_mock(status="paid")

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = payment_mock
        return result

    session.execute = fake_execute

    svc = PaymentService(session)
    returned = await svc.confirm_payment(telegram_charge_id="charge_abc", scan_id=10)

    session.commit.assert_not_called()
    assert returned is payment_mock


@pytest.mark.asyncio
async def test_get_pending_payment_returns_none_when_empty():
    """get_pending_payment must return None when no pending payment exists."""
    from app.services.payment_service import PaymentService

    session = _make_session()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    svc = PaymentService(session)
    result = await svc.get_pending_payment(user_id=1, scan_type="personal")

    assert result is None


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_buy_callback_sends_invoice():
    """handle_buy_callback must call bot.send_invoice with currency='XTR' and provider_token=''."""
    from app.bot.handlers.payment import handle_buy_callback

    # Build mock user
    user_mock = MagicMock()
    user_mock.id = 1

    # Build mock scan
    scan_mock = _make_scan_mock(scan_id=10, scan_type="personal")

    # Build callback mock
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "buy:personal"
    callback.from_user = MagicMock()
    callback.from_user.id = 12345
    callback.from_user.username = "testuser"
    callback.from_user.full_name = "Test User"
    callback.message = AsyncMock()
    callback.message.bot = AsyncMock()
    callback.message.chat = MagicMock()
    callback.message.chat.id = 12345
    callback.answer = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    session = _make_session()

    with (
        patch("app.bot.handlers.payment.UserService") as MockUserService,
        patch("app.bot.handlers.payment.ScanService") as MockScanService,
        patch("app.bot.handlers.payment.PaymentService") as MockPaymentService,
    ):
        mock_us = AsyncMock()
        mock_us.get_or_create = AsyncMock(return_value=(user_mock, True))
        MockUserService.return_value = mock_us

        mock_ss = AsyncMock()
        mock_ss.get_incomplete_scan = AsyncMock(return_value=None)
        mock_ss.create_full_scan = AsyncMock(return_value=scan_mock)
        MockScanService.return_value = mock_ss

        mock_ps = AsyncMock()
        mock_ps.create_payment = AsyncMock(return_value=_make_payment_mock())
        MockPaymentService.return_value = mock_ps

        await handle_buy_callback(callback, state, session)

    callback.message.bot.send_invoice.assert_awaited_once()
    call_kwargs = callback.message.bot.send_invoice.call_args
    assert call_kwargs.kwargs.get("currency") == "XTR" or call_kwargs.args[2] == "XTR" or "XTR" in str(call_kwargs)
    # Extract kwargs from the send_invoice call
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    args = call_kwargs.args if call_kwargs.args else ()
    # currency and provider_token are keyword args in the handler
    assert kwargs.get("currency") == "XTR"
    assert kwargs.get("provider_token") == ""


@pytest.mark.asyncio
async def test_handle_pre_checkout_query_answers_ok():
    """handle_pre_checkout_query must call query.answer(ok=True)."""
    from app.bot.handlers.payment import handle_pre_checkout_query

    query = AsyncMock(spec=PreCheckoutQuery)
    query.answer = AsyncMock()

    await handle_pre_checkout_query(query)

    query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_handle_successful_payment_triggers_questionnaire():
    """handle_successful_payment must call confirm_payment then start_questionnaire_after_payment."""
    from app.bot.handlers.payment import handle_successful_payment

    payment_mock = _make_payment_mock(status="paid")
    scan_mock = _make_scan_mock(scan_id=10, is_paid=True, scan_type="personal")

    message = AsyncMock(spec=Message)
    message.successful_payment = MagicMock()
    message.successful_payment.telegram_payment_charge_id = "charge_xyz"
    message.successful_payment.invoice_payload = "scan:10:user:1"
    message.bot = AsyncMock()
    message.chat = MagicMock()
    message.chat.id = 12345
    message.answer = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    session = _make_session()

    with (
        patch("app.bot.handlers.payment.PaymentService") as MockPaymentService,
        patch("app.bot.handlers.payment.ScanService") as MockScanService,
        patch("app.bot.handlers.full_scan.start_questionnaire_after_payment") as mock_start,
    ):
        mock_ps = AsyncMock()
        mock_ps.confirm_payment = AsyncMock(return_value=payment_mock)
        MockPaymentService.return_value = mock_ps

        mock_ss = AsyncMock()
        mock_ss.get_scan = AsyncMock(return_value=scan_mock)
        MockScanService.return_value = mock_ss

        mock_start.return_value = None

        await handle_successful_payment(message, state, session)

    mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_successful_payment_aborts_if_not_paid():
    """handle_successful_payment must NOT call start_questionnaire if scan.is_paid is False."""
    from app.bot.handlers.payment import handle_successful_payment

    payment_mock = _make_payment_mock(status="paid")
    scan_mock = _make_scan_mock(scan_id=10, is_paid=False, scan_type="personal")

    message = AsyncMock(spec=Message)
    message.successful_payment = MagicMock()
    message.successful_payment.telegram_payment_charge_id = "charge_xyz"
    message.successful_payment.invoice_payload = "scan:10:user:1"
    message.bot = AsyncMock()
    message.chat = MagicMock()
    message.chat.id = 12345
    message.answer = AsyncMock()

    state = AsyncMock(spec=FSMContext)
    session = _make_session()

    with (
        patch("app.bot.handlers.payment.PaymentService") as MockPaymentService,
        patch("app.bot.handlers.payment.ScanService") as MockScanService,
        patch("app.bot.handlers.full_scan.start_questionnaire_after_payment") as mock_start,
    ):
        mock_ps = AsyncMock()
        mock_ps.confirm_payment = AsyncMock(return_value=payment_mock)
        MockPaymentService.return_value = mock_ps

        mock_ss = AsyncMock()
        mock_ss.get_scan = AsyncMock(return_value=scan_mock)
        MockScanService.return_value = mock_ss

        mock_start.return_value = None

        await handle_successful_payment(message, state, session)

    mock_start.assert_not_awaited()
    message.answer.assert_awaited()
