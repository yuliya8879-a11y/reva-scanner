"""Integration tests for mini-scan FSM states and flow logic."""

from __future__ import annotations

import os

# Set required env vars BEFORE any app module is imported.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAtest_token_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")

from datetime import date

import pytest

from app.bot.states import MiniScanStates
from app.bot.handlers.mini_scan import (
    parse_birth_date,
    _AREA_LABELS,
    _AGE_LABELS,
    _PAIN_LABELS,
)


class TestMiniScanStates:
    """Verify that MiniScanStates has all required state definitions."""

    def test_has_six_states(self):
        state_names = [s.state for s in MiniScanStates.__states__]
        assert len(state_names) == 6, f"Expected 6 states, got {len(state_names)}: {state_names}"

    def test_has_birth_date_state(self):
        assert MiniScanStates.birth_date is not None

    def test_has_business_area_state(self):
        assert MiniScanStates.business_area is not None

    def test_has_business_age_state(self):
        assert MiniScanStates.business_age is not None

    def test_has_main_pain_state(self):
        assert MiniScanStates.main_pain is not None

    def test_has_situation_state(self):
        assert MiniScanStates.situation is not None

    def test_has_generating_state(self):
        assert MiniScanStates.generating is not None


class TestCallbackDataPatterns:
    """Verify callback data keys are consistent across handler dicts."""

    def test_area_labels_keys_match_expected(self):
        expected_keys = {"services", "products", "it", "trade", "other"}
        assert set(_AREA_LABELS.keys()) == expected_keys

    def test_age_labels_keys_match_expected(self):
        expected_keys = {"lt1", "1to3", "3to7", "7plus"}
        assert set(_AGE_LABELS.keys()) == expected_keys

    def test_pain_labels_keys_match_expected(self):
        expected_keys = {"no_clients", "no_team", "no_system", "no_money", "everything"}
        assert set(_PAIN_LABELS.keys()) == expected_keys

    def test_area_callback_prefix_pattern(self):
        """All area callbacks should be prefixed 'area:'."""
        for key in _AREA_LABELS:
            callback = f"area:{key}"
            assert callback.startswith("area:"), f"Unexpected prefix: {callback}"

    def test_age_callback_prefix_pattern(self):
        """All age callbacks should be prefixed 'age:'."""
        for key in _AGE_LABELS:
            callback = f"age:{key}"
            assert callback.startswith("age:"), f"Unexpected prefix: {callback}"

    def test_pain_callback_prefix_pattern(self):
        """All pain callbacks should be prefixed 'pain:'."""
        for key in _PAIN_LABELS:
            callback = f"pain:{key}"
            assert callback.startswith("pain:"), f"Unexpected prefix: {callback}"


class TestParseBirthDate:
    """Verify date parsing helper function."""

    def test_valid_date_returns_date_object(self):
        result = parse_birth_date("15.05.1990")
        assert result == date(1990, 5, 15)

    def test_valid_date_with_leading_zeros(self):
        result = parse_birth_date("01.01.2000")
        assert result == date(2000, 1, 1)

    def test_valid_date_with_surrounding_whitespace(self):
        result = parse_birth_date("  15.05.1990  ")
        assert result == date(1990, 5, 15)

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_birth_date("abc")

    def test_wrong_separator_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_birth_date("1990-05-15")

    def test_partial_date_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_birth_date("15.05")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_birth_date("")

    def test_specific_numerology_example(self):
        """date(1990, 5, 15) used in numerology docstring."""
        result = parse_birth_date("15.05.1990")
        assert result == date(1990, 5, 15)
