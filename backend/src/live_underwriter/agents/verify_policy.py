"""Policy verification agent — the gate that checks records."""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.db import UnderwritingDB
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import PolicyRecord, UnderwritingState

logger = get_logger(__name__)

# Module-level DB so the graph can call verify_policy_node(state) while tests
# can inject a temp DB via set_db_for_tests().
_db: UnderwritingDB | None = None


def set_db_for_tests(db: UnderwritingDB) -> None:
    """Override the DB used by verify_policy_node (test hook)."""
    global _db
    _db = db


def _get_db() -> UnderwritingDB:
    return _db if _db is not None else UnderwritingDB()


# Map common spoken words to the letters they represent in policy codes.
# STT often mishears alphanumeric codes (e.g. "POL-1001" -> "Paul 1001").
# Multi-letter words map to full prefixes; single letters map to themselves.
_WORD_TO_LETTER = {
    "paul": "POL",
    "pol": "POL",
    "pall": "POL",
    "paw": "POL",
    "polo": "POL",
    "oh": "O",
    "owe": "O",
    "ell": "L",
    "el": "L",
    "zero": "0",
    "one": "1",
    "won": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
}


def _normalize_policy_number(raw: str) -> str:
    """Normalize a possibly-misheard policy number into a canonical form.

    Handles STT errors like "Paul 1001" -> "POL-1001" by mapping spoken
    words to letters/digits and standardizing separators.
    """
    text = raw.strip().upper()
    # Replace spoken words with their letter/digit equivalents (longest first).
    for word, letter in sorted(_WORD_TO_LETTER.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(word.upper(), letter)
    # Remove non-alphanumeric separators, then re-insert a dash after the prefix.
    cleaned = "".join(ch for ch in text if ch.isalnum())
    if len(cleaned) >= 4 and cleaned[:3].isalpha():
        return f"{cleaned[:3]}-{cleaned[3:]}"
    return cleaned


def _find_policy(db: UnderwritingDB, policy_number: str) -> dict[str, Any] | None:
    """Look up a policy, trying exact match, then fuzzy normalization, then suffix."""
    row = db.get_policy(policy_number)
    if row is not None:
        return row

    normalized = _normalize_policy_number(policy_number)
    if normalized != policy_number:
        row = db.get_policy(normalized)
        if row is not None:
            logger.info("verify_policy: fuzzy match %s -> %s", policy_number, normalized)
            return row

    # Fallback: match by numeric suffix (LLM/STT may drop the 'POL-' prefix).
    digits = "".join(ch for ch in policy_number if ch.isdigit())
    if digits:
        row = db.get_policy_by_suffix(digits)
        if row is not None:
            logger.info("verify_policy: suffix match %s -> %s", policy_number, row["policy_number"])
            return row
    return None


def verify_policy_node(state: UnderwritingState, db: UnderwritingDB | None = None) -> dict[str, Any]:
    """Look up the applicant's policy in records; set the verified gate."""
    logger.info("verify_policy: looking up policy %s", state.applicant.policy_number)
    db = db or _get_db()

    policy_number = state.applicant.policy_number
    if not policy_number:
        logger.warning("verify_policy: no policy number provided")
        return {
            "policy": None,
            "stage": "verify_policy",
            **append_audit(state, "verify_policy", "no policy number provided", "warn", confidence=0.0),
        }

    row = _find_policy(db, policy_number)
    if row is None:
        logger.warning("verify_policy: policy %s not found", policy_number)
        return {
            "policy": None,
            "stage": "verify_policy",
            **append_audit(state, "verify_policy", f"policy {policy_number} not found", "warn", confidence=0.0),
        }

    policy = PolicyRecord(
        policy_number=str(row["policy_number"]),
        policy_holder=str(row["policy_holder"]),
        status=str(row["status"]),
        coverage_amount=float(row["coverage_amount"]),
        premium=float(row["premium"]),
        verified=bool(row["verified"]),
    )
    confidence = 0.95 if policy.verified else 0.5
    logger.info("verify_policy: policy %s verified=%s", policy_number, policy.verified)
    return {
        "policy": policy,
        "stage": "verify_policy",
        **append_audit(state, "verify_policy", f"policy {policy_number} verified={policy.verified}", confidence=confidence),
    }
