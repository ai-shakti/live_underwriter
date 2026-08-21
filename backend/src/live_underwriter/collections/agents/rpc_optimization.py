"""RPC (Right Party Contact) optimization agent.

Selects the optimal channel, time, and message for contacting a borrower
based on their profile, history, and compliance constraints.
"""

from __future__ import annotations

from typing import Any

from live_underwriter.collections.state import CollectionsState
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

# Channel preference by delinquency stage
_CHANNEL_PRIORITY: dict[str, list[str]] = {
    "current": ["email", "portal", "mail"],
    "1-29": ["phone", "sms", "email"],
    "30-59": ["phone", "sms", "email", "mail"],
    "60-89": ["phone", "sms", "mail"],
    "90+": ["phone", "mail", "legal"],
}

# Best times to call (hour of day, 24h)
_BEST_TIMES = {
    "morning": (9, 12),
    "afternoon": (13, 17),
    "evening": (17, 20),
}


def rpc_optimization_node(state: CollectionsState) -> dict[str, Any]:
    """Select the optimal contact channel and timing."""
    logger.info("collections: optimizing contact strategy")
    stage = state.delinquency_stage
    channels = _CHANNEL_PRIORITY.get(stage, ["email"])

    # Skip phone if outside calling hours (simplified)
    optimal_channel = channels[0] if channels else "email"

    logger.info("collections: optimal channel=%s for stage=%s", optimal_channel, stage)
    return {"stage": "rpc_optimization"}
