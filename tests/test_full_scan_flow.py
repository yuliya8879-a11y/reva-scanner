"""Tests for full scan FSM flow: dynamic question routing, progress indicator, resume logic."""

from __future__ import annotations

import os

# Set required env vars BEFORE any app module is imported.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.handlers.payment import handle_buy_callback
from app.bot.handlers.full_scan import (
    _send_question,
    handle_keyboard_answer,
    handle_skip_answer,
    handle_text_answer,
    handle_resume_scan,
    handle_cancel_scan,
)
from app.bot.questions import PERSONAL_QUESTIONS, BUSINESS_QUESTIONS, get_questions_for_type, get_total_questions
from app.bot.states import FullScanStates


# ---------------------------------------------------------------------------
# FullScanStates: structural tests
# ---------------------------------------------------------------------------


class TestFullScanStates:
    """Verify FullScanStates has all required states q0-q14 and completing."""

    def test_has_q0_through_q14(self):
        for i in range(15):
            state = getattr(FullScanStates, f"q{i}", None)
            assert state is not None, f"FullScanStates.q{i} is missing"

    def test_has_completing_state(self):
        assert FullScanStates.completing is not None

    def test_has_sixteen_states_total(self):
        # q0-q14 (15) + completing (1) = 16
        state_count = len(FullScanStates.__states__)
        assert state_count == 16, f"Expected 16 states, got {state_count}"

    def test_all_q_states_are_full_scan_states(self):
        for i in range(15):
            state = getattr(FullScanStates, f"q{i}")
            # Each state's string includes the class group name
            assert "FullScanStates" in state.state


# ---------------------------------------------------------------------------
# Progress indicator format tests
# ---------------------------------------------------------------------------


class TestProgressIndicator:
    """Verify progress indicator format 'Вопрос X из Y' is correct."""

    @pytest.mark.asyncio
    async def test_send_question_progress_format_first_question(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[0]  # birth_date

        await _send_question(bot, chat_id=123, question=question, index=0, total=15)

        call_args = bot.send_message.call_args
        text = call_args[0][1] if call_args[0] else call_args[1].get("text", "")
        # Accept text from either positional or keyword arg
        if not text:
            text = str(call_args)
        assert "Вопрос 1 из 15" in text

    @pytest.mark.asyncio
    async def test_send_question_progress_format_last_question(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[14]  # social_url

        await _send_question(bot, chat_id=123, question=question, index=14, total=15)

        call_args = bot.send_message.call_args
        text = call_args[0][1] if call_args[0] else call_args[1].get("text", "")
        if not text:
            text = str(call_args)
        assert "Вопрос 15 из 15" in text

    @pytest.mark.asyncio
    async def test_send_question_birth_date_has_example_hint(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[0]  # birth_date

        await _send_question(bot, chat_id=123, question=question, index=0, total=15)

        call_args = bot.send_message.call_args
        text = call_args[0][1] if call_args[0] else call_args[1].get("text", "")
        if not text:
            text = str(call_args)
        assert "15.05.1990" in text

    @pytest.mark.asyncio
    async def test_send_question_keyboard_uses_fq_prefix(self):
        """Keyboard questions should produce buttons with fq:{key}:{value} callback."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[2]  # business_area — keyboard

        await _send_question(bot, chat_id=123, question=question, index=2, total=15)

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        keyboard = call_kwargs.get("reply_markup")
        assert keyboard is not None
        # Check at least one button uses the fq: prefix
        flat_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        assert any(btn.callback_data.startswith("fq:") for btn in flat_buttons)

    @pytest.mark.asyncio
    async def test_send_question_optional_text_has_skip_button(self):
        """Optional text questions should include a 'Пропустить' button."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[14]  # social_url — optional text

        await _send_question(bot, chat_id=123, question=question, index=14, total=15)

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        keyboard = call_kwargs.get("reply_markup")
        assert keyboard is not None
        flat_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        assert any("Пропустить" in btn.text for btn in flat_buttons)
        assert any(btn.callback_data.startswith("fq_skip:") for btn in flat_buttons)

    @pytest.mark.asyncio
    async def test_send_question_required_text_has_no_keyboard(self):
        """Required text questions should not get a skip button."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        question = PERSONAL_QUESTIONS[1]  # name — required text

        await _send_question(bot, chat_id=123, question=question, index=1, total=15)

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs.get("reply_markup") is None


# ---------------------------------------------------------------------------
# handle_buy_callback tests
# ---------------------------------------------------------------------------


def _make_callback(data: str, user_id: int = 42) -> MagicMock:
    """Build a minimal CallbackQuery mock."""
    callback = MagicMock()
    callback.data = data
    callback.from_user.id = user_id
    callback.from_user.username = "test_user"
    callback.from_user.full_name = "Test User"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()
    callback.message.bot = MagicMock()
    callback.message.bot.send_message = AsyncMock()
    callback.message.bot.send_invoice = AsyncMock()
    callback.message.chat.id = 999
    return callback


def _make_state(data: dict | None = None) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


def _make_session() -> MagicMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


class TestHandleBuyCallback:
    """Test entry point for buy:personal and buy:business."""

    @pytest.mark.asyncio
    async def test_buy_personal_creates_scan(self):
        callback = _make_callback("buy:personal")
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=10)
        mock_scan = MagicMock(id=100, answers={}, scan_type="personal")

        with (
            patch(
                "app.bot.handlers.payment.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, True)),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.create_full_scan",
                new=AsyncMock(return_value=mock_scan),
            ),
            patch(
                "app.bot.handlers.payment.PaymentService",
                new=MagicMock(return_value=MagicMock(create_payment=AsyncMock())),
            ),
        ):
            await handle_buy_callback(callback, state, session)

        # New behavior: sends invoice, does not set FSM state directly
        callback.message.bot.send_invoice.assert_awaited_once()
        call_kwargs = callback.message.bot.send_invoice.call_args[1]
        assert call_kwargs["currency"] == "XTR"

    @pytest.mark.asyncio
    async def test_buy_business_creates_scan(self):
        callback = _make_callback("buy:business")
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=11)
        mock_scan = MagicMock(id=101, answers={}, scan_type="business")

        with (
            patch(
                "app.bot.handlers.payment.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.create_full_scan",
                new=AsyncMock(return_value=mock_scan),
            ),
            patch(
                "app.bot.handlers.payment.PaymentService",
                new=MagicMock(return_value=MagicMock(create_payment=AsyncMock())),
            ),
        ):
            await handle_buy_callback(callback, state, session)

        # New behavior: sends invoice for business scan
        callback.message.bot.send_invoice.assert_awaited_once()
        call_kwargs = callback.message.bot.send_invoice.call_args[1]
        assert call_kwargs["currency"] == "XTR"

    @pytest.mark.asyncio
    async def test_buy_personal_resumes_same_type_incomplete_scan(self):
        """If incomplete scan exists with same type, resume from current_index."""
        callback = _make_callback("buy:personal")
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=12)
        # Existing scan with 3 answers already saved
        mock_scan = MagicMock(
            id=200,
            scan_type="personal",
            answers={"birth_date": "1990-01-01", "name": "Alice", "business_area": "services"},
        )

        with (
            patch(
                "app.bot.handlers.payment.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=mock_scan),
            ),
            patch(
                "app.bot.handlers.payment.PaymentService",
                new=MagicMock(return_value=MagicMock(create_payment=AsyncMock())),
            ),
        ):
            await handle_buy_callback(callback, state, session)

        # Resumes existing scan — sends invoice for it
        callback.message.bot.send_invoice.assert_awaited_once()
        call_kwargs = callback.message.bot.send_invoice.call_args[1]
        assert "scan:200:" in call_kwargs["payload"]

    @pytest.mark.asyncio
    async def test_buy_business_cancels_different_type_incomplete_scan(self):
        """If incomplete scan is different type, cancel old and create new."""
        callback = _make_callback("buy:business")
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=13)
        mock_existing = MagicMock(
            id=300,
            scan_type="personal",
            answers={},
        )
        mock_new_scan = MagicMock(id=301, answers={}, scan_type="business")

        with (
            patch(
                "app.bot.handlers.payment.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=mock_existing),
            ),
            patch(
                "app.bot.handlers.payment.ScanService.create_full_scan",
                new=AsyncMock(return_value=mock_new_scan),
            ),
            patch(
                "app.bot.handlers.payment.PaymentService",
                new=MagicMock(return_value=MagicMock(create_payment=AsyncMock())),
            ),
        ):
            await handle_buy_callback(callback, state, session)

        # Old scan should be marked failed
        assert mock_existing.status == "failed"
        session.commit.assert_called()
        # Invoice sent for new scan
        callback.message.bot.send_invoice.assert_awaited_once()
        call_kwargs = callback.message.bot.send_invoice.call_args[1]
        assert call_kwargs["currency"] == "XTR"
        assert "scan:301:" in call_kwargs["payload"]


# ---------------------------------------------------------------------------
# handle_keyboard_answer tests
# ---------------------------------------------------------------------------


class TestHandleKeyboardAnswer:
    """Test keyboard answer handler with fq:{key}:{value} callback data."""

    @pytest.mark.asyncio
    async def test_keyboard_answer_saves_and_advances(self):
        callback = _make_callback("fq:business_area:services")
        state = _make_state(
            data={"scan_id": 50, "scan_type": "personal", "current_index": 2}
        )
        session = _make_session()

        with (
            patch(
                "app.bot.handlers.full_scan.ScanService.save_answer",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "app.bot.handlers.full_scan.ScanService.complete_questionnaire",
                new=AsyncMock(return_value=MagicMock()),
            ),
        ):
            await handle_keyboard_answer(callback, state, session)

        state.update_data.assert_called()
        state.set_state.assert_called()


# ---------------------------------------------------------------------------
# handle_skip_answer tests
# ---------------------------------------------------------------------------


class TestHandleSkipAnswer:
    """Test skip handler saves empty string for optional questions."""

    @pytest.mark.asyncio
    async def test_skip_saves_empty_string(self):
        callback = _make_callback("fq_skip:social_url")
        state = _make_state(
            data={"scan_id": 60, "scan_type": "personal", "current_index": 14}
        )
        session = _make_session()

        saved_key = None
        saved_value = None

        async def mock_save_answer(self_inner, scan_id, key, value):
            nonlocal saved_key, saved_value
            saved_key = key
            saved_value = value
            return MagicMock()

        with (
            patch(
                "app.bot.handlers.full_scan.ScanService.save_answer",
                new=mock_save_answer,
            ),
            patch(
                "app.bot.handlers.full_scan.ScanService.complete_questionnaire",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "app.bot.handlers.full_scan.generate_and_deliver_report",
                new=AsyncMock(),
            ),
        ):
            await handle_skip_answer(callback, state, session)

        assert saved_key == "social_url"
        assert saved_value == ""


# ---------------------------------------------------------------------------
# Completion message test
# ---------------------------------------------------------------------------


class TestCompletionMessage:
    """Test that 'Анкета заполнена' is sent after last question."""

    @pytest.mark.asyncio
    async def test_last_question_sends_completion_message(self):
        """After the final question (index 14 for personal), completion message must contain 'Анкета заполнена'."""
        # social_url (index 14) is the last personal question — skip it
        callback = _make_callback("fq_skip:social_url")
        bot_mock = callback.message.bot

        state = _make_state(
            data={"scan_id": 70, "scan_type": "personal", "current_index": 14}
        )
        session = _make_session()

        with (
            patch(
                "app.bot.handlers.full_scan.ScanService.save_answer",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "app.bot.handlers.full_scan.ScanService.complete_questionnaire",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "app.bot.handlers.full_scan.generate_and_deliver_report",
                new=AsyncMock(),
            ),
        ):
            await handle_skip_answer(callback, state, session)

        # Check that send_message was called with completion text
        call_args_list = bot_mock.send_message.call_args_list
        sent_texts = [str(c) for c in call_args_list]
        assert any("Анкета заполнена" in t for t in sent_texts), (
            f"'Анкета заполнена' not found in calls: {sent_texts}"
        )


# ---------------------------------------------------------------------------
# Resume and cancel tests
# ---------------------------------------------------------------------------


class TestResumeScan:
    """Test resume_scan callback restores exact question position."""

    @pytest.mark.asyncio
    async def test_resume_scan_sets_correct_index(self):
        callback = _make_callback("resume_scan:500")
        state = _make_state()
        session = _make_session()

        # Scan with 5 answers saved
        mock_scan = MagicMock(
            id=500,
            user_id=42,
            scan_type="personal",
            answers={
                "birth_date": "1990-01-01",
                "name": "Alice",
                "business_area": "services",
                "business_age": "1to3",
                "role": "founder",
            },
        )

        with patch(
            "app.bot.handlers.full_scan.ScanService.get_scan",
            new=AsyncMock(return_value=mock_scan),
        ):
            await handle_resume_scan(callback, state, session)

        call_kwargs = state.update_data.call_args[1]
        assert call_kwargs["current_index"] == 5  # 5 answers -> next is index 5
        # FSM state should be q5
        set_state_arg = state.set_state.call_args[0][0]
        assert set_state_arg == FullScanStates.q5

    @pytest.mark.asyncio
    async def test_resume_scan_not_found_sends_message(self):
        callback = _make_callback("resume_scan:999")
        state = _make_state()
        session = _make_session()

        with patch(
            "app.bot.handlers.full_scan.ScanService.get_scan",
            new=AsyncMock(return_value=None),
        ):
            await handle_resume_scan(callback, state, session)

        callback.message.answer.assert_called_once()
        assert "не найден" in callback.message.answer.call_args[0][0]


class TestCancelScan:
    """Test cancel_scan callback sets scan status to failed."""

    @pytest.mark.asyncio
    async def test_cancel_scan_sets_failed_status(self):
        callback = _make_callback("cancel_scan:600")
        state = _make_state()
        session = _make_session()

        mock_scan = MagicMock(id=600, status="collecting")

        with patch(
            "app.bot.handlers.full_scan.ScanService.get_scan",
            new=AsyncMock(return_value=mock_scan),
        ):
            await handle_cancel_scan(callback, state, session)

        assert mock_scan.status == "failed"
        session.commit.assert_called()
        state.clear.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_scan_sends_message(self):
        callback = _make_callback("cancel_scan:601")
        state = _make_state()
        session = _make_session()

        mock_scan = MagicMock(id=601, status="collecting")

        with patch(
            "app.bot.handlers.full_scan.ScanService.get_scan",
            new=AsyncMock(return_value=mock_scan),
        ):
            await handle_cancel_scan(callback, state, session)

        callback.message.answer.assert_called_once()
        msg = callback.message.answer.call_args[0][0]
        assert "Скан отменён" in msg


# ---------------------------------------------------------------------------
# /start incomplete scan detection tests
# ---------------------------------------------------------------------------


def _make_message(user_id: int = 42) -> MagicMock:
    """Build a minimal Message mock for /start handler."""
    msg = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = "test_user"
    msg.from_user.full_name = "Test User"
    msg.answer = AsyncMock()
    return msg


class TestStartHandlerResume:
    """Test /start handler detects incomplete scans and shows resume prompt."""

    @pytest.mark.asyncio
    async def test_start_with_incomplete_scan_shows_resume_prompt(self):
        from app.bot.handlers.start import cmd_start

        message = _make_message()
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=20)
        mock_scan = MagicMock(id=700, scan_type="personal")

        with (
            patch(
                "app.bot.handlers.start.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.start.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=mock_scan),
            ),
        ):
            await cmd_start(message, session, state)

        message.answer.assert_called_once()
        text = message.answer.call_args[0][0]
        assert "незавершённый скан" in text
        # FSM state should NOT be cleared (return early)
        state.clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_with_incomplete_scan_shows_resume_and_cancel_buttons(self):
        from app.bot.handlers.start import cmd_start

        message = _make_message()
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=21)
        mock_scan = MagicMock(id=701, scan_type="business")

        with (
            patch(
                "app.bot.handlers.start.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.start.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=mock_scan),
            ),
        ):
            await cmd_start(message, session, state)

        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args[1]
        keyboard = call_kwargs.get("reply_markup")
        assert keyboard is not None
        flat_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_callbacks = [btn.callback_data for btn in flat_buttons]
        assert any(cb.startswith("resume_scan:") for cb in button_callbacks)
        assert any(cb.startswith("cancel_scan:") for cb in button_callbacks)
        button_texts = [btn.text for btn in flat_buttons]
        assert any("Продолжить" in t for t in button_texts)

    @pytest.mark.asyncio
    async def test_start_without_incomplete_scan_shows_normal_menu(self):
        from app.bot.handlers.start import cmd_start

        message = _make_message()
        state = _make_state()
        session = _make_session()

        mock_user = MagicMock(id=22)

        with (
            patch(
                "app.bot.handlers.start.UserService.get_or_create",
                new=AsyncMock(return_value=(mock_user, False)),
            ),
            patch(
                "app.bot.handlers.start.ScanService.get_incomplete_scan",
                new=AsyncMock(return_value=None),
            ),
        ):
            await cmd_start(message, session, state)

        # Normal menu shown: FSM cleared, message answered with scan options
        state.clear.assert_called_once()
        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args[1]
        keyboard = call_kwargs.get("reply_markup")
        assert keyboard is not None
        flat_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_callbacks = [btn.callback_data for btn in flat_buttons]
        assert "scan_type:mini" in button_callbacks


# ---------------------------------------------------------------------------
# Router includes full_scan
# ---------------------------------------------------------------------------


class TestRouterIncludes:
    def test_full_scan_in_router(self):
        from app.bot import router as bot_router

        included_names = [r.name for r in bot_router.main_router.sub_routers]
        assert "full_scan" in included_names, (
            f"full_scan router not found in main_router. Found: {included_names}"
        )
