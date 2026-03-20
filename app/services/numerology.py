"""Numerology soul number calculation."""

from datetime import date


def calculate_soul_number(birth_date: date) -> int:
    """Calculate numerology soul number from birth date.

    Sums ALL digits of the date in YYYYMMDD format, then repeatedly
    reduces (digit sums) until a single digit (1-9) is reached.
    Does NOT map 9 to 0 — result is always in range [1, 9].

    Examples:
        date(1990, 5, 15) -> 1+9+9+0+0+5+1+5=30, 3+0=3 -> 3
        date(1999, 9, 9)  -> 1+9+9+9+0+9+0+9=46, 4+6=10, 1+0=1 -> 1
        date(2000, 1, 1)  -> 2+0+0+0+0+1+0+1=4 -> 4
    """
    # Format as YYYYMMDD and collect all digits
    date_str = birth_date.strftime("%Y%m%d")
    number = sum(int(ch) for ch in date_str)

    # Reduce repeatedly until single digit
    while number > 9:
        number = sum(int(ch) for ch in str(number))

    # Ensure result is at least 1 (edge case: all-zero date, though invalid in practice)
    return number if number > 0 else 9
