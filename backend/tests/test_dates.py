"""Tests for the smart DOB normalizer."""

from __future__ import annotations

import pytest

from live_underwriter.dates import normalize_dob


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Already canonical
        ("1985-04-12", "1985-04-12"),
        # Named month formats
        ("April 12, 1985", "1985-04-12"),
        ("April 12th 1985", "1985-04-12"),
        ("12 April 1985", "1985-04-12"),
        ("12th April 1985", "1985-04-12"),
        ("Jan 5, 1990", "1990-01-05"),
        # Numeric formats
        ("12/04/1985", "1985-04-12"),  # DD/MM/YYYY
        ("04-12-1985", "1985-12-04"),  # ambiguous -> DD-MM-YYYY (intl standard)
        ("12.04.85", "1985-04-12"),  # DD.MM.YY
        ("04/12/85", "1985-12-04"),  # ambiguous -> DD-MM-YY
        # 2-digit year expansion
        ("12/04/85", "1985-04-12"),
        ("01/01/99", "1999-01-01"),
        # Day > 12 disambiguates
        ("25/12/1990", "1990-12-25"),  # 25 must be day
        ("13/01/1988", "1988-01-13"),  # 13 must be day
    ],
)
def test_normalize_dob(raw: str, expected: str) -> None:
    assert normalize_dob(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not a date",
        "32/13/1990",  # invalid month/day
        "1985-13-01",  # invalid month
    ],
)
def test_normalize_dob_invalid(raw: str | None) -> None:
    assert normalize_dob(raw) is None
