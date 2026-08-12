"""Review agent — reconcile applicant details against the verified policy."""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)


def review_node(state: UnderwritingState) -> dict[str, Any]:
    """Cross-check applicant details against the verified policy record."""
    logger.info("review: reconciling applicant with policy")
    flags: list[str] = []

    if state.policy is None:
        logger.warning("review: no policy to reconcile against")
        return {
            "stage": "review",
            **append_audit(state, "review", "no policy to reconcile", "warn"),
        }

    if (
        state.policy.policy_holder
        and state.applicant.full_name
        and state.policy.policy_holder.lower() != state.applicant.full_name.lower()
    ):
        flags.append(
            f"name mismatch: policy holder '{state.policy.policy_holder}' "
            f"vs applicant '{state.applicant.full_name}'"
        )

    if (
        state.policy.coverage_amount
        and state.applicant.coverage_amount
        and abs(state.policy.coverage_amount - state.applicant.coverage_amount) > 1.0
    ):
        flags.append(
            f"coverage mismatch: policy {state.policy.coverage_amount} "
            f"vs requested {state.applicant.coverage_amount}"
        )

    if flags:
        logger.warning("review: %d flag(s): %s", len(flags), flags)
        return {
            "stage": "review",
            **append_audit(state, "review", "; ".join(flags), "warn"),
        }

    logger.info("review: applicant reconciled with policy")
    return {
        "stage": "review",
        **append_audit(state, "review", "applicant reconciled with policy"),
    }
