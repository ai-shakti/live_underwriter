"""Arrangement engine agent — pick the best payment arrangement."""

from __future__ import annotations

from typing import Any

from live_underwriter.collections.state import CollectionsState, PaymentArrangement
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)


def arrangement_engine_node(state: CollectionsState) -> dict[str, Any]:
    """Select the best payment arrangement based on hardship and loan status."""
    logger.info("collections: selecting payment arrangement")
    loan = state.loan
    hardship = state.hardship

    if not loan:
        logger.warning("collections: no loan record for arrangement")
        return {"stage": "arrangement"}

    # Determine arrangement type based on hardship
    if hardship.hardship_type != "none":
        if hardship.hardship_type in ("medical", "job_loss"):
            arr_type = "forbearance"
            duration = 6
            monthly = 0  # No payment during forbearance
        elif hardship.hardship_type == "natural_disaster":
            arr_type = "modification"
            duration = 12
            monthly = loan.monthly_payment * 0.5  # 50% reduction
        else:
            arr_type = "modification"
            duration = 6
            monthly = loan.monthly_payment * 0.75
    else:
        # Standard arrangement
        arr_type = "standard"
        duration = 3
        monthly = loan.monthly_payment

    arrangement = PaymentArrangement(
        arrangement_type=arr_type,
        monthly_amount=monthly,
        duration_months=duration,
        total_amount=monthly * duration,
        status="proposed",
    )

    logger.info("collections: arrangement=%s, $%.0f/mo for %d months",
                arr_type, monthly, duration)
    return {"arrangement": arrangement, "stage": "arrangement"}
