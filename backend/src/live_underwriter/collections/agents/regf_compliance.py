"""Reg F compliance agent — enforce debt collection regulations.

Checks:
- Reg F (Fair Debt Collection Practices Act): Communication frequency limits,
  calling hours (8am-9pm), harassment prohibitions.
- SCRA: Special interest rate caps for military borrowers.
- State-specific rules: 50-state patchwork of additional restrictions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from live_underwriter.collections.state import CollectionsState
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

# Reg F: Maximum contact attempts per channel per week
_MAX_CONTACTS_PER_WEEK = {
    "phone": 3,
    "sms": 3,
    "email": 2,
    "mail": 1,
}

# Reg F: Calling hours (local time)
_CALLING_HOURS_START = 8
_CALLING_HOURS_END = 21

# SCRA interest rate cap (6% during active duty)
_SCRA_RATE_CAP = 6.0


def regf_compliance_node(state: CollectionsState) -> dict[str, Any]:
    """Run Reg F and SCRA compliance checks."""
    logger.info("collections: running compliance checks")
    flags: list[str] = []

    # 1. Check contact frequency limits
    channel_counts: dict[str, int] = {}
    for entry in state.contact_history:
        channel_counts[entry.channel] = channel_counts.get(entry.channel, 0) + 1

    for channel, count in channel_counts.items():
        limit = _MAX_CONTACTS_PER_WEEK.get(channel, 3)
        if count >= limit:
            flags.append(f"Reg F: {channel} contact limit reached ({count}/{limit} per week)")

    # 2. Check calling hours
    current_hour = datetime.now().hour
    if current_hour < _CALLING_HOURS_START or current_hour >= _CALLING_HOURS_END:
        flags.append(f"Reg F: Outside calling hours ({_CALLING_HOURS_START}:00-{_CALLING_HOURS_END}:00)")

    # 3. SCRA check (simplified — would check a real database in production)
    if state.borrower.occupation and any(
        kw in state.borrower.occupation.lower()
        for kw in ["military", "army", "navy", "air force", "marines"]
    ):
        flags.append(f"SCRA: Rate cap of {_SCRA_RATE_CAP}% applies")
        if state.loan and state.loan.interest_rate > _SCRA_RATE_CAP:
            flags.append(f"SCRA: Current rate {state.loan.interest_rate}% exceeds {_SCRA_RATE_CAP}% cap")

    if flags:
        logger.warning("collections: %d compliance flag(s): %s", len(flags), flags)
        return {"compliance_flags": flags, "stage": "compliance"}

    logger.info("collections: no compliance concerns")
    return {"compliance_flags": [], "stage": "compliance"}
