"""Unit tests for full scan AI report delivery flow.

Tests cover generate_and_deliver_report() wired into _advance_to_next():
- Happy path: 8 messages sent (1 status + 1 numerology + 6 blocks)
- Missing birth_date: error message sent, scan.status set to failed
- AI service failure: error message sent, scan.status set to failed
- Block message headers: each of the 6 blocks has a bold Russian header
"""

from __future__ import annotations

import os

# Set required env vars BEFORE any app module is imported.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.bot.handlers.full_scan import generate_and_deliver_report
from app.services.full_scan_ai_service import BLOCK_KEYS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_report() -> dict:
    """Return a minimal valid report dict matching FullScanAIService output."""
    return {
        "архитектура": "Бизнес-архитектура описание",
        "слепые_зоны": "Слепые зоны описание",
        "энергетические_блоки": "Энергетические блоки описание",
        "команда": "Команда описание",
        "деньги": "Деньги описание",
        "рекомендации": "Рекомендации описание",
        "numerology": {
            "soul_number": 7,
            "life_path_number": 3,
            "birth_date": "1990-05-15",
        },
        "token_usage": {
            "input_tokens": 500,
            "output_tokens": 800,
        },
    }


def _make_mock_scan(answers: dict | None = None) -> MagicMock:
    """Build a MagicMock Scan instance with the given answers."""
    scan = MagicMock()
    scan.answers = answers if answers is not None else {"birth_date": "1990-05-15"}
    scan.status = "questionnaire_complete"
    return scan


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGenerateAndDeliverReportHappyPath:
    """Verify the successful 8-message delivery flow."""

    @pytest.mark.asyncio
    async def test_send_message_called_8_times(self):
        """1 status + 1 numerology + 6 blocks = 8 total send_message calls."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        assert bot.send_message.call_count == 8, (
            f"Expected 8 send_message calls, got {bot.send_message.call_count}"
        )

    @pytest.mark.asyncio
    async def test_first_message_is_generating_status(self):
        """First message should be 'Генерирую отчёт...' status notification."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        first_call_text = bot.send_message.call_args_list[0][0][1]
        assert "Генерирую отчёт" in first_call_text

    @pytest.mark.asyncio
    async def test_complete_full_scan_called_before_delivery(self):
        """complete_full_scan must be called (storing JSONB) before sending blocks."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        mock_scan_service.complete_full_scan.assert_called_once_with(1, report, report["token_usage"])

    @pytest.mark.asyncio
    async def test_numerology_message_shows_soul_and_life_path_numbers(self):
        """Second message (numerology) must contain soul and life path numbers."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        numerology_call_text = bot.send_message.call_args_list[1][0][1]
        assert "7" in numerology_call_text  # soul_number
        assert "3" in numerology_call_text  # life_path_number
        assert "Нумерология" in numerology_call_text


# ---------------------------------------------------------------------------
# Missing birth_date
# ---------------------------------------------------------------------------


class TestGenerateAndDeliverReportMissingBirthDate:
    """Verify error path when birth_date is absent or invalid in scan.answers."""

    @pytest.mark.asyncio
    async def test_missing_birth_date_sets_scan_status_failed(self):
        """When birth_date key is absent, scan.status must be set to failed."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({})  # No birth_date key

        with patch("app.bot.handlers.full_scan.ScanService") as MockScanService:
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        from app.models.scan import ScanStatus
        assert scan.status == ScanStatus.failed.value

    @pytest.mark.asyncio
    async def test_missing_birth_date_sends_error_message(self):
        """When birth_date is absent, user must receive an error message."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({})  # No birth_date

        with patch("app.bot.handlers.full_scan.ScanService") as MockScanService:
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        # Should have sent: status message + error message = 2 calls total
        assert bot.send_message.call_count >= 2
        all_texts = " ".join(
            c[0][1] for c in bot.send_message.call_args_list if c[0]
        )
        assert "дату рождения" in all_texts or "рождения" in all_texts

    @pytest.mark.asyncio
    async def test_invalid_birth_date_format_sets_scan_status_failed(self):
        """When birth_date is malformed, scan.status must be set to failed."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({"birth_date": "not-a-date"})

        with patch("app.bot.handlers.full_scan.ScanService") as MockScanService:
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        from app.models.scan import ScanStatus
        assert scan.status == ScanStatus.failed.value


# ---------------------------------------------------------------------------
# AI service failure
# ---------------------------------------------------------------------------


class TestGenerateAndDeliverReportAIFailure:
    """Verify error path when FullScanAIService.generate_full_report raises."""

    @pytest.mark.asyncio
    async def test_ai_failure_sets_scan_status_failed(self):
        """When AI raises, scan.status must be set to ScanStatus.failed."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.side_effect = ValueError("Claude error")
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        from app.models.scan import ScanStatus
        assert scan.status == ScanStatus.failed.value

    @pytest.mark.asyncio
    async def test_ai_failure_sends_user_error_message(self):
        """When AI raises, the user must receive an error message."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.side_effect = ValueError("Claude error")
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        all_texts = " ".join(
            c[0][1] for c in bot.send_message.call_args_list if c[0]
        )
        assert "ошибка" in all_texts.lower() or "ошибке" in all_texts.lower()

    @pytest.mark.asyncio
    async def test_ai_failure_does_not_call_complete_full_scan(self):
        """complete_full_scan must NOT be called when AI raises."""
        bot = AsyncMock()
        session = AsyncMock()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.side_effect = ValueError("Claude error")
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        mock_scan_service.complete_full_scan.assert_not_called()


# ---------------------------------------------------------------------------
# Block message headers
# ---------------------------------------------------------------------------


class TestBlockMessagesContainHeaders:
    """Verify each block message includes its bold Russian header."""

    @pytest.mark.asyncio
    async def test_all_6_block_messages_have_bold_headers(self):
        """Each of the 6 block send_message calls must contain a bold header (*Label*)."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        # Calls: [0]=status, [1]=numerology, [2..7]=6 blocks
        block_calls = bot.send_message.call_args_list[2:]
        assert len(block_calls) == 6, f"Expected 6 block calls, got {len(block_calls)}"

        # Verify each block message has a bold header (starts with *...)
        expected_labels = [
            "Архитектура",
            "Слепые зоны",
            "Энергетические блоки",
            "Команда",
            "Деньги",
            "Рекомендации",
        ]
        for i, (blk_call, label) in enumerate(zip(block_calls, expected_labels)):
            text = blk_call[0][1]
            assert f"*{label}*" in text, (
                f"Block {i} message missing bold header '*{label}*'. Got: {text[:100]}"
            )

    @pytest.mark.asyncio
    async def test_block_messages_use_markdown_parse_mode(self):
        """All block messages must use parse_mode='Markdown' for bold headers."""
        bot = AsyncMock()
        session = AsyncMock()
        report = _make_mock_report()
        scan = _make_mock_scan({"birth_date": "1990-05-15"})

        with (
            patch("app.bot.handlers.full_scan.ScanService") as MockScanService,
            patch("app.bot.handlers.full_scan.FullScanAIService") as MockAIService,
        ):
            mock_scan_service = AsyncMock()
            mock_scan_service.get_scan.return_value = scan
            mock_scan_service.complete_full_scan.return_value = scan
            MockScanService.return_value = mock_scan_service

            mock_ai = AsyncMock()
            mock_ai.generate_full_report.return_value = report
            MockAIService.return_value = mock_ai

            await generate_and_deliver_report(
                bot=bot,
                chat_id=123,
                scan_id=1,
                scan_type="personal",
                session=session,
            )

        # Calls [1..7] (numerology + 6 blocks) should all use Markdown
        markdown_calls = bot.send_message.call_args_list[1:]
        for i, blk_call in enumerate(markdown_calls):
            kwargs = blk_call[1] if blk_call[1] else {}
            # parse_mode can be in kwargs or positional args
            parse_mode = kwargs.get("parse_mode", "")
            assert parse_mode == "Markdown", (
                f"Call {i + 1} missing parse_mode='Markdown'. Got kwargs: {kwargs}"
            )
