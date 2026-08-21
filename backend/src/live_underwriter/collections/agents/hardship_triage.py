"""Hardship triage agent — classify borrower for loss mitigation vs. standard."""

from __future__ import annotations

from typing import Any

from live_underwriter.collections.state import CollectionsState, HardshipAssessment
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

# Keywords that indicate hardship scenarios
_HARDSHIP_KEYWORDS: dict[str, list[str]] = {
    "medical": ["hospital", "surgery", "medical", "illness", "cancer", "emergency room", "doctor"],
    "job_loss": ["laid off", "fired", "unemployed", "lost my job", "terminated", "reduction in force"],
    "natural_disaster": ["flood", "hurricane", "earthquake", "fire", "wildfire", "tornado"],
    "other": ["divorce", "death", "family emergency", "caregiver"],
}


def hardship_triage_node(state: CollectionsState) -> dict[str, Any]:
    """Classify the borrower's hardship status from the transcript."""
    logger.info("collections: triaging hardship")
    transcript = (state.transcript or "").lower()

    for hardship_type, keywords in _HARDSHIP_KEYWORDS.items():
        for kw in keywords:
            if kw in transcript:
                logger.info("collections: detected hardship: %s (keyword: '%s')", hardship_type, kw)
                assessment = HardshipAssessment(
                    hardship_type=hardship_type,
                    severity="medium",
                    recommended_action="forbearance" if hardship_type in ("medical", "job_loss") else "modification",
                    rationale=f"Detected '{kw}' in transcript — classifying as {hardship_type} hardship",
                )
                return {
                    "hardship": assessment,
                    "hardship_flag": True,
                    "stage": "hardship_triage",
                }

    logger.info("collections: no hardship detected")
    return {
        "hardship": HardshipAssessment(),
        "hardship_flag": False,
        "stage": "hardship_triage",
    }
