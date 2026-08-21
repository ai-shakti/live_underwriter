"""Human-in-the-loop review node.

When the risk gate routes to "escalate", this node pauses the workflow and
waits for a human reviewer to approve, decline, or modify the AI's decision.
This is the "AI recommends, human decides" pattern — critical for regulated
financial services.
"""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.db import UnderwritingDB
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)


def human_review_node(state: UnderwritingState) -> dict[str, Any]:
    """Pause for human review when the AI flags a case.

    In CLI mode, this prompts the reviewer interactively.
    In API mode, the review is created in the DB and the workflow returns
    a ``requires_review`` status — the caller resolves it via the API.

    The node checks if a review decision has already been made (e.g. via the
    API's resolve endpoint). If so, it applies the decision. Otherwise, it
    creates a pending review record.
    """
    logger.info("human_review: case flagged for review")

    # If already resolved, apply the decision and continue.
    if state.review_decision:
        logger.info("human_review: review already resolved: %s", state.review_decision)
        return _apply_review_decision(state)

    # Create a pending review record in the DB.
    db = UnderwritingDB()
    try:
        review_id = db.create_review({
            "applicant_name": state.applicant.full_name or "Unknown",
            "policy_number": state.applicant.policy_number,
            "risk_score": state.risk.risk_score,
            "risk_level": state.risk.risk_level,
            "ai_decision": state.risk.decision,
            "rationale": state.risk.rationale,
            "flags": str(state.risk.flags),
        })
        logger.info("human_review: created review #%d", review_id)
    finally:
        db.close()

    return {
        "review_required": True,
        "stage": "human_review",
        **append_audit(
            state,
            "human_review",
            f"case escalated for human review (review #{review_id})",
            "warn",
            confidence=0.5,
        ),
    }


def _apply_review_decision(state: UnderwritingState) -> dict[str, Any]:
    """Apply the human reviewer's decision to the state."""
    decision = state.review_decision
    notes = state.reviewer_notes or ""

    if decision == "approved":
        return {
            "decision": "accept",
            "review_required": False,
            "stage": "human_review",
            **append_audit(
                state,
                "human_review",
                f"human reviewer APPROVED. Notes: {notes}",
                confidence=0.95,
            ),
        }
    elif decision == "declined":
        return {
            "decision": "decline",
            "review_required": False,
            "stage": "human_review",
            **append_audit(
                state,
                "human_review",
                f"human reviewer DECLINED. Notes: {notes}",
                "warn",
                confidence=0.95,
            ),
        }
    else:
        # modified — apply with adjusted risk
        return {
            "decision": "review",
            "review_required": False,
            "stage": "human_review",
            **append_audit(
                state,
                "human_review",
                f"human reviewer MODIFIED. Notes: {notes}",
                "warn",
                confidence=0.8,
            ),
        }
