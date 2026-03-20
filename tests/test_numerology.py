"""Unit tests for numerology soul number calculation."""

from datetime import date

import pytest

from app.services.numerology import calculate_soul_number


def test_soul_number_typical_date():
    """1990-05-15: digits 1+9+9+0+0+5+1+5=30, 3+0=3."""
    assert calculate_soul_number(date(1990, 5, 15)) == 3


def test_soul_number_all_nines():
    """1999-09-09: digits 1+9+9+9+0+9+0+9=46, 4+6=10, 1+0=1."""
    assert calculate_soul_number(date(1999, 9, 9)) == 1


def test_soul_number_zeros():
    """2000-01-01: digits 2+0+0+0+0+1+0+1=4."""
    assert calculate_soul_number(date(2000, 1, 1)) == 4


def test_soul_number_returns_single_digit():
    """Result must always be between 1 and 9."""
    for year in range(1950, 2010, 7):
        for month in range(1, 13, 3):
            for day in [1, 9, 15, 28]:
                try:
                    result = calculate_soul_number(date(year, month, day))
                except ValueError:
                    continue  # invalid date (e.g. month=12, day=31 fine; but month=2 day=30 fails)
                assert 1 <= result <= 9, f"Got {result} for {year}-{month}-{day}"


def test_soul_number_reduces_to_nine_not_zero():
    """Soul numbers must not be 0. For dates that sum to multiples of 9, result must be 9."""
    # 2007-09-09: 2+0+0+7+0+9+0+9=27, 2+7=9
    assert calculate_soul_number(date(2007, 9, 9)) == 9


def test_soul_number_returns_int():
    """Return type must be int."""
    result = calculate_soul_number(date(1985, 3, 22))
    assert isinstance(result, int)
