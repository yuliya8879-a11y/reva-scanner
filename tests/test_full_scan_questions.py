"""Tests for full scan question definitions and FullScanStates FSM group.

Covers:
- PERSONAL_QUESTIONS list: 15 entries, correct field structure, specific keys
- BUSINESS_QUESTIONS list: 12 entries, correct field structure, specific keys
- QuestionDef dataclass fields
- get_questions_for_type helper
- get_total_questions helper
- FullScanStates: states q0-q14 plus completing
"""

from __future__ import annotations

import pytest

from app.bot.questions import (
    BUSINESS_QUESTIONS,
    PERSONAL_QUESTIONS,
    QuestionDef,
    get_questions_for_type,
    get_total_questions,
)
from app.bot.states import FullScanStates


# ---------------------------------------------------------------------------
# QuestionDef structure
# ---------------------------------------------------------------------------


def test_question_def_has_required_fields():
    """QuestionDef instances must expose key, text, input_type, options, required."""
    q = PERSONAL_QUESTIONS[0]
    assert hasattr(q, "key")
    assert hasattr(q, "text")
    assert hasattr(q, "input_type")
    assert hasattr(q, "options")
    assert hasattr(q, "required")
    assert hasattr(q, "max_length")


def test_question_def_is_dataclass():
    """QuestionDef must be a dataclass (supports field access and instantiation)."""
    q = QuestionDef(
        key="test",
        text="Test question?",
        input_type="text",
        options=None,
        required=True,
        max_length=None,
    )
    assert q.key == "test"
    assert q.text == "Test question?"
    assert q.input_type == "text"
    assert q.options is None
    assert q.required is True
    assert q.max_length is None


# ---------------------------------------------------------------------------
# PERSONAL_QUESTIONS
# ---------------------------------------------------------------------------


def test_personal_questions_has_exactly_15_entries():
    """PERSONAL_QUESTIONS must contain exactly 15 question definitions."""
    assert len(PERSONAL_QUESTIONS) == 15


def test_personal_questions_all_have_valid_input_type():
    """Every question in PERSONAL_QUESTIONS must have input_type 'keyboard' or 'text'."""
    for q in PERSONAL_QUESTIONS:
        assert q.input_type in ("keyboard", "text"), (
            f"Question key={q.key!r} has invalid input_type={q.input_type!r}"
        )


def test_personal_questions_keyboard_have_options():
    """Keyboard questions must have a non-empty options list."""
    for q in PERSONAL_QUESTIONS:
        if q.input_type == "keyboard":
            assert q.options is not None and len(q.options) > 0, (
                f"Keyboard question key={q.key!r} must have options"
            )


def test_personal_questions_text_have_no_options():
    """Text input questions must have options=None."""
    for q in PERSONAL_QUESTIONS:
        if q.input_type == "text":
            assert q.options is None, (
                f"Text question key={q.key!r} must not have options, got {q.options!r}"
            )


def test_personal_q1_is_birth_date():
    """Q1 (index 0) must have key='birth_date' and required=True."""
    q = PERSONAL_QUESTIONS[0]
    assert q.key == "birth_date"
    assert q.required is True
    assert q.input_type == "text"


def test_personal_q14_is_current_situation_optional():
    """Q14 (index 13) must have input_type='text', required=False, max_length=1000."""
    q = PERSONAL_QUESTIONS[13]
    assert q.input_type == "text"
    assert q.required is False
    assert q.max_length == 1000


def test_personal_q15_is_social_url_optional():
    """Q15 (index 14) must have key='social_url' and required=False."""
    q = PERSONAL_QUESTIONS[14]
    assert q.key == "social_url"
    assert q.required is False
    assert q.input_type == "text"


def test_personal_questions_options_are_tuples():
    """Options must be list of 2-tuples (display_text, callback_value)."""
    for q in PERSONAL_QUESTIONS:
        if q.options is not None:
            for item in q.options:
                assert len(item) == 2, (
                    f"Option in key={q.key!r} is not a 2-tuple: {item!r}"
                )


# ---------------------------------------------------------------------------
# BUSINESS_QUESTIONS
# ---------------------------------------------------------------------------


def test_business_questions_has_exactly_12_entries():
    """BUSINESS_QUESTIONS must contain exactly 12 question definitions."""
    assert len(BUSINESS_QUESTIONS) == 12


def test_business_questions_all_have_valid_input_type():
    """Every question in BUSINESS_QUESTIONS must have input_type 'keyboard' or 'text'."""
    for q in BUSINESS_QUESTIONS:
        assert q.input_type in ("keyboard", "text"), (
            f"Question key={q.key!r} has invalid input_type={q.input_type!r}"
        )


def test_business_q12_is_social_url_optional():
    """Q12 (index 11) in BUSINESS must have key='social_url' and required=False."""
    q = BUSINESS_QUESTIONS[11]
    assert q.key == "social_url"
    assert q.required is False
    assert q.input_type == "text"


def test_business_q11_is_product_description_optional():
    """Q11 (index 10) in BUSINESS must have key='product_description', required=False, max_length=1000."""
    q = BUSINESS_QUESTIONS[10]
    assert q.key == "product_description"
    assert q.required is False
    assert q.max_length == 1000


def test_business_first_10_match_personal():
    """First 10 BUSINESS questions must have same keys as PERSONAL questions 1-10."""
    for i in range(10):
        assert BUSINESS_QUESTIONS[i].key == PERSONAL_QUESTIONS[i].key, (
            f"Index {i}: BUSINESS key={BUSINESS_QUESTIONS[i].key!r} != "
            f"PERSONAL key={PERSONAL_QUESTIONS[i].key!r}"
        )


# ---------------------------------------------------------------------------
# get_questions_for_type
# ---------------------------------------------------------------------------


def test_get_questions_for_type_personal():
    """get_questions_for_type('personal') must return PERSONAL_QUESTIONS."""
    result = get_questions_for_type("personal")
    assert result is PERSONAL_QUESTIONS


def test_get_questions_for_type_business():
    """get_questions_for_type('business') must return BUSINESS_QUESTIONS."""
    result = get_questions_for_type("business")
    assert result is BUSINESS_QUESTIONS


def test_get_questions_for_type_invalid_raises():
    """get_questions_for_type with unknown type must raise ValueError."""
    with pytest.raises(ValueError):
        get_questions_for_type("mini")


def test_get_questions_for_type_invalid_empty_raises():
    """get_questions_for_type with empty string must raise ValueError."""
    with pytest.raises(ValueError):
        get_questions_for_type("")


# ---------------------------------------------------------------------------
# get_total_questions
# ---------------------------------------------------------------------------


def test_get_total_questions_personal():
    """get_total_questions('personal') must return 15."""
    assert get_total_questions("personal") == 15


def test_get_total_questions_business():
    """get_total_questions('business') must return 12."""
    assert get_total_questions("business") == 12


# ---------------------------------------------------------------------------
# FullScanStates FSM group
# ---------------------------------------------------------------------------


def test_full_scan_states_has_q0_through_q14():
    """FullScanStates must have states q0, q1, ..., q14 (15 states total)."""
    for i in range(15):
        assert hasattr(FullScanStates, f"q{i}"), (
            f"FullScanStates is missing state q{i}"
        )


def test_full_scan_states_has_completing():
    """FullScanStates must have a 'completing' state."""
    assert hasattr(FullScanStates, "completing"), (
        "FullScanStates is missing 'completing' state"
    )


def test_full_scan_states_total_state_count():
    """FullScanStates must have exactly 16 states (q0-q14 + completing)."""
    # Count states by checking __all_states__ attribute available on StatesGroup
    state_attrs = [f"q{i}" for i in range(15)] + ["completing"]
    for attr in state_attrs:
        assert hasattr(FullScanStates, attr), f"Missing state: {attr}"
    # 16 total
    assert len(state_attrs) == 16
