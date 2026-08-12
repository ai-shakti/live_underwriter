"""Smart date-of-birth normalization.

The LLM understands natural language in the transcript but may return the DOB
in many formats (e.g. "April 12, 1985", "12/04/1985", "04-12-85", "1985-04-12").
This module normalizes any of these into a canonical ``YYYY-MM-DD`` string,
disambiguating ambiguous numeric formats using sensible rules.
"""

from __future__ import annotations

import re
from datetime import date

# Month names -> number.
_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Named month pattern: "April 12, 1985" or "12 April 1985".
_NAMED_RE = re.compile(
    r"(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?[,]?\s+(?P<year>\d{2,4})"
    r"|(?P<day2>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month2>[A-Za-z]+)[,]?\s+(?P<year2>\d{2,4})"
)

# Numeric pattern: captures up to 3 numeric groups separated by - / . or spaces.
_NUMERIC_RE = re.compile(r"(\d{1,4})[\s\-/.](\d{1,2})[\s\-/.](\d{2,4})")


def _expand_year(year: int) -> int:
    """Expand a 2-digit year to a 4-digit year (e.g. 85 -> 1985)."""
    if year < 100:
        return 1900 + year if year >= 30 else 2000 + year
    return year


def _is_valid(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False


def _normalize_named(text: str) -> str | None:
    """Handle 'April 12, 1985' and '12 April 1985'."""
    m = _NAMED_RE.search(text)
    if not m:
        return None
    if m.group("month"):
        month_name, day, year = m.group("month"), int(m.group("day")), int(m.group("year"))
    else:
        month_name, day, year = m.group("month2"), int(m.group("day2")), int(m.group("year2"))
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return None
    year = _expand_year(year)
    if not _is_valid(year, month, day):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalize_numeric(text: str) -> str | None:
    """Handle numeric formats, disambiguating ambiguous ones.

    Rules:
      - If the first group is 4 digits, it's YYYY-MM-DD.
      - If a group is > 12, it must be the day (so the other is the month).
      - Otherwise (all <= 12), prefer DD-MM-YYYY (common outside the US).
    """
    m = _NUMERIC_RE.search(text)
    if not m:
        return None
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))

    # YYYY-MM-DD
    if a >= 1000:
        y, mo, d = a, b, c
    else:
        # Expand the year (last group).
        y = _expand_year(c)
        # If one of the first two is > 12, it's the day.
        if a > 12 and b <= 12:
            d, mo = a, b
        elif b > 12 and a <= 12:
            d, mo = b, a
        else:
            # Ambiguous: prefer DD-MM-YYYY.
            d, mo = a, b
    if not _is_valid(y, mo, d):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def normalize_dob(raw: str | None) -> str | None:
    """Normalize a DOB string to ``YYYY-MM-DD``, or None if unparseable."""
    if not raw:
        return None
    text = raw.strip()
    # Already canonical — validate it.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        y, m, d = (int(x) for x in text.split("-"))
        return text if _is_valid(y, m, d) else None
    return _normalize_named(text) or _normalize_numeric(text)
