"""Validation agent — check required fields and formats."""

from __future__ import annotations

import re
from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)

# Fields required for a decisionable application.
REQUIRED_FIELDS = ["full_name", "date_of_birth", "policy_number", "coverage_amount"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,}$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_field(field: str, value: object) -> str | None:
    """Return an error message for a field, or None if valid."""
    if value is None or value == "":
        return f"missing required field: {field}"
    if field == "email" and not _EMAIL_RE.match(str(value)):
        return f"invalid email format: {value}"
    if field == "phone" and not _PHONE_RE.match(str(value)):
        return f"invalid phone format: {value}"
    if field == "date_of_birth" and not _DOB_RE.match(str(value)):
        return f"invalid date_of_birth (expected YYYY-MM-DD): {value}"
    if field == "coverage_amount" and isinstance(value, (int, float)) and value <= 0:
        return f"coverage_amount must be positive: {value}"
    return None


def validate_node(state: UnderwritingState) -> dict[str, Any]:
    """Validate required applicant fields; collect errors into flags."""
    logger.info("validate: checking applicant fields")
    errors: list[str] = []
    applicant = state.applicant

    for field in REQUIRED_FIELDS:
        err = _validate_field(field, getattr(applicant, field))
        if err:
            errors.append(err)

    # Optional format checks.
    for field in ("email", "phone", "date_of_birth"):
        value = getattr(applicant, field)
        if value:
            err = _validate_field(field, value)
            if err:
                errors.append(err)

    if errors:
        logger.warning("validate: %d issue(s): %s", len(errors), errors)
        return {
            "stage": "validate",
            **append_audit(state, "validate", "; ".join(errors), "warn", confidence=0.5),
        }

    logger.info("validate: all required fields present")
    return {
        "stage": "validate",
        **append_audit(state, "validate", "all required fields valid", confidence=1.0),
    }
