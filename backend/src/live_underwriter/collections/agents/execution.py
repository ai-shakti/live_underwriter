"""Execution agent — execute the contact plan via dialer/SMS/email."""

from __future__ import annotations

from typing import Any

from live_underwriter.collections.state import CollectionsState, ContactLogEntry
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)


def execution_node(state: CollectionsState) -> dict[str, Any]:
    """Execute the contact plan and log the outcome."""
    logger.info("collections: executing contact plan")
    arrangement = state.arrangement

    # Log a contact attempt
    entry = ContactLogEntry(
        channel="system",
        status="completed",
        notes=f"Arrangement proposed: {arrangement.arrangement_type if arrangement else 'standard'}",
    )

    decision = "arrangement_proposed" if arrangement else "standard_outreach"
    logger.info("collections: decision=%s", decision)

    return {
        "decision": decision,
        "contact_history": [*state.contact_history, entry],
        "stage": "execution",
    }
