"""Fraud detection agent — heuristics + red-flag rules from the DB."""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.db import UnderwritingDB
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)

_db: UnderwritingDB | None = None


def set_db_for_tests(db: UnderwritingDB) -> None:
    """Override the DB used by fraud_check_node (test hook)."""
    global _db
    _db = db


def _get_db() -> UnderwritingDB:
    return _db if _db is not None else UnderwritingDB()


# High-risk keywords that may indicate application fraud.
_HIGH_RISK_KEYWORDS = [
    "cash only",
    "no questions",
    "guaranteed approval",
    "fake",
    "fraud",
    "under the table",
]

# Phrases suggesting repeated/urgent applications (velocity signal).
_VELOCITY_SIGNALS = [
    "applied before",
    "second application",
    "reapply",
    "multiple applications",
    "as soon as possible",
    "urgent",
]


def _keyword_flags(transcript: str) -> list[str]:
    lowered = transcript.lower()
    return [
        f"high-risk keyword present: '{kw}'"
        for kw in _HIGH_RISK_KEYWORDS
        if kw in lowered
    ]


def _velocity_flags(transcript: str) -> list[str]:
    lowered = transcript.lower()
    return [
        f"velocity signal present: '{sig}'"
        for sig in _VELOCITY_SIGNALS
        if sig in lowered
    ]


def _mismatch_flags(state: UnderwritingState, db: UnderwritingDB) -> list[str]:
    """Compare applicant details against known records for mismatches."""
    flags: list[str] = []
    applicant = state.applicant
    if not applicant.full_name:
        return flags

    known = db.get_applicant(applicant.full_name)
    if known is None:
        return flags

    if applicant.date_of_birth and known["date_of_birth"] and applicant.date_of_birth != known["date_of_birth"]:
        flags.append(
            f"DOB mismatch: known {known['date_of_birth']} vs provided {applicant.date_of_birth}"
        )
    if (
        applicant.annual_income
        and known["annual_income"]
        and abs(applicant.annual_income - float(known["annual_income"])) > 1000
    ):
        flags.append(
            f"income mismatch: known {known['annual_income']} vs provided {applicant.annual_income}"
        )
    return flags


def fraud_check_node(state: UnderwritingState) -> dict[str, Any]:
    """Run fraud heuristics; append any red flags to the risk assessment."""
    logger.info("fraud_check: running fraud heuristics")
    db = _get_db()
    flags: list[str] = []

    flags.extend(_keyword_flags(state.transcript))
    flags.extend(_velocity_flags(state.transcript))
    flags.extend(_mismatch_flags(state, db))

    if flags:
        logger.warning("fraud_check: %d red flag(s): %s", len(flags), flags)
        return {
            "risk": state.risk.model_copy(update={"flags": [*state.risk.flags, *flags]}),
            "stage": "fraud_check",
            **append_audit(state, "fraud_check", "; ".join(flags), "warn"),
        }

    logger.info("fraud_check: no red flags")
    return {
        "stage": "fraud_check",
        **append_audit(state, "fraud_check", "no red flags detected"),
    }
