"""Curated sample applicants for testing the underwriting workflow.

Each sample has a distinct risk profile so end users can explore different
outcomes. The frontend loads these via ``GET /api/samples`` and lets the user
pick one to fill the transcript box.
"""

from __future__ import annotations

from typing import Any

SAMPLES: list[dict[str, Any]] = [
    {
        "id": "jane-doe",
        "name": "Jane Doe",
        "description": "Clean application, low risk → accept",
        "expected_outcome": "accept",
        "transcript": (
            "My name is Jane Doe, born 1985-04-12, policy POL-1001, "
            "coverage 500000, income 120000"
        ),
    },
    {
        "id": "alice-johnson",
        "name": "Alice Johnson",
        "description": "Clean docs, moderate coverage → accept",
        "expected_outcome": "accept",
        "transcript": (
            "My name is Alice Johnson, born 1990-03-03, policy POL-2001, "
            "coverage 250000, income 65000"
        ),
    },
    {
        "id": "robert-chen",
        "name": "Robert Chen",
        "description": "High coverage + premium, high income → review",
        "expected_outcome": "review",
        "transcript": (
            "My name is Robert Chen, born 1975-11-20, policy POL-2002, "
            "coverage 1000000, income 300000"
        ),
    },
    {
        "id": "maria-garcia",
        "name": "Maria Garcia",
        "description": "Overdrafts + delinquent docs → flagged for review",
        "expected_outcome": "review (flagged docs)",
        "transcript": (
            "My name is Maria Garcia, born 1988-07-15, policy POL-2003, "
            "coverage 150000, income 45000"
        ),
    },
    {
        "id": "john-smith",
        "name": "John Smith",
        "description": "Overdraft on bank statement → flagged",
        "expected_outcome": "review (flagged docs)",
        "transcript": (
            "My name is John Smith, born 1978-09-30, policy POL-1002, "
            "coverage 250000, income 90000"
        ),
    },
    {
        "id": "unknown-policy",
        "name": "Unknown Person",
        "description": "Lapsed/unverified policy → rejected",
        "expected_outcome": "reject",
        "transcript": (
            "My name is Unknown Person, born 1980-01-01, policy POL-9999, "
            "coverage 100000, income 50000"
        ),
    },
]


def get_samples() -> list[dict[str, Any]]:
    """Return the curated sample applicants."""
    return SAMPLES
