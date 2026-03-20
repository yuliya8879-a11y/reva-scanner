"""Unit tests for FullScanAIService and calculate_life_path_number.

Tests mock anthropic.AsyncAnthropic to avoid real API calls.
Real numerology calculations are tested without mocking.
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.full_scan_ai_service import (
    BLOCK_KEYS,
    FullScanAIService,
    calculate_life_path_number,
)
from app.services.numerology import calculate_soul_number


# ---------------------------------------------------------------------------
# Tests: calculate_life_path_number
# ---------------------------------------------------------------------------


def test_life_path_number_example_from_plan():
    """15.05.1990: day=1+5=6, month=5, year=1+9+9+0=19->1+9=10->1+0=1; 6+5+1=12->3."""
    assert calculate_life_path_number(date(1990, 5, 15)) == 3


def test_life_path_number_all_single_digit_components():
    """01.01.2000: day=1, month=1, year=2+0+0+0=2; 1+1+2=4."""
    assert calculate_life_path_number(date(2000, 1, 1)) == 4


def test_life_path_number_returns_single_digit():
    """Result must always be a single digit (1-9)."""
    result = calculate_life_path_number(date(1985, 12, 31))
    assert 1 <= result <= 9


# ---------------------------------------------------------------------------
# Helpers for AI service tests
# ---------------------------------------------------------------------------


def _make_valid_claude_response(block_keys: list[str]) -> str:
    """Return a JSON string with all block keys set to 'test value'."""
    return json.dumps({k: "test value for block" for k in block_keys})


def _make_mock_client(response_text: str, input_tokens: int = 100, output_tokens: int = 200):
    """Return a mock AsyncAnthropic client whose messages.create returns a mock response."""
    mock_usage = MagicMock()
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens

    mock_content = MagicMock()
    mock_content.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    return mock_client


# ---------------------------------------------------------------------------
# Tests: FullScanAIService.generate_full_report — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_full_report_returns_all_block_keys():
    """generate_full_report must return dict containing all 6 block keys."""
    valid_json = _make_valid_claude_response(BLOCK_KEYS)

    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client(valid_json)
        service = FullScanAIService()
        birth_date = date(1990, 5, 15)
        result = await service.generate_full_report(
            answers={"name": "Иван", "business_area": "IT"},
            birth_date=birth_date,
            scan_type="personal",
        )

    for key in BLOCK_KEYS:
        assert key in result, f"Missing block key: {key}"

    assert result["архитектура"] == "test value for block"


@pytest.mark.asyncio
async def test_generate_full_report_returns_numerology():
    """generate_full_report must include numerology with soul_number, life_path_number, birth_date."""
    valid_json = _make_valid_claude_response(BLOCK_KEYS)
    birth_date = date(1990, 5, 15)

    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client(valid_json)
        service = FullScanAIService()
        result = await service.generate_full_report(
            answers={},
            birth_date=birth_date,
            scan_type="personal",
        )

    assert "numerology" in result
    numerology = result["numerology"]
    assert numerology["soul_number"] == calculate_soul_number(birth_date)
    assert numerology["life_path_number"] == calculate_life_path_number(birth_date)
    assert numerology["birth_date"] == birth_date.isoformat()


@pytest.mark.asyncio
async def test_generate_full_report_returns_token_usage():
    """generate_full_report must include token_usage with input_tokens and output_tokens."""
    valid_json = _make_valid_claude_response(BLOCK_KEYS)

    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client(valid_json, input_tokens=100, output_tokens=200)
        service = FullScanAIService()
        result = await service.generate_full_report(
            answers={},
            birth_date=date(1990, 5, 15),
            scan_type="personal",
        )

    assert "token_usage" in result
    assert result["token_usage"]["input_tokens"] == 100
    assert result["token_usage"]["output_tokens"] == 200


# ---------------------------------------------------------------------------
# Tests: FullScanAIService.generate_full_report — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_full_report_raises_value_error_on_bad_json():
    """generate_full_report must raise ValueError when Claude returns non-JSON text."""
    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client("not json at all")
        service = FullScanAIService()

        with pytest.raises(ValueError):
            await service.generate_full_report(
                answers={},
                birth_date=date(1990, 5, 15),
                scan_type="personal",
            )


# ---------------------------------------------------------------------------
# Tests: FullScanAIService.generate_full_report — thin answers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_full_report_with_empty_answers_still_returns_all_keys():
    """generate_full_report must return all required keys even when all answers are empty."""
    valid_json = _make_valid_claude_response(BLOCK_KEYS)

    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client(valid_json)
        service = FullScanAIService()
        empty_answers = {
            "name": "",
            "business_area": "",
            "business_age": "",
            "role": "",
            "team_size": "",
            "client_source": "",
            "avg_check": "",
            "main_pain": "",
            "growth_blocker": "",
            "superpower": "",
            "decision_style": "",
            "year_goal": "",
            "current_situation": "",
            "social_url": "",
        }
        result = await service.generate_full_report(
            answers=empty_answers,
            birth_date=date(1990, 5, 15),
            scan_type="personal",
        )

    assert len(result) >= 8  # 6 blocks + numerology + token_usage
    for key in BLOCK_KEYS:
        assert key in result
    assert "numerology" in result
    assert "token_usage" in result


@pytest.mark.asyncio
async def test_generate_full_report_uses_fallback_for_missing_claude_keys():
    """When Claude omits a block key, the fallback 'недостаточно данных' string is used."""
    # Claude returns JSON missing some keys
    partial_json = json.dumps({"архитектура": "some text"})

    with patch("app.services.full_scan_ai_service.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value = _make_mock_client(partial_json)
        service = FullScanAIService()
        result = await service.generate_full_report(
            answers={},
            birth_date=date(1990, 5, 15),
            scan_type="personal",
        )

    # All 6 keys must be present
    for key in BLOCK_KEYS:
        assert key in result
        assert isinstance(result[key], str)
        assert len(result[key]) > 0

    # The missing ones get the fallback string
    assert "недостаточно данных" in result["слепые_зоны"]
