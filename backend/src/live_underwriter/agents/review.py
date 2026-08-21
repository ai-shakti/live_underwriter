"""Review agent — reconcile applicant details against the verified policy.

Uses an LLM to perform intelligent reconciliation, catching subtle mismatches
that rule-based checks would miss (e.g. "Bob" vs "Robert", "Jr." suffixes,
address normalization).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from live_underwriter.agents._helpers import append_audit
from live_underwriter.llm import get_llm
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)

_REVIEW_PROMPT = """You are an underwriting review analyst. Your job is to reconcile
the applicant's stated details against the verified policy record.

Applicant details:
- Name: {applicant_name}
- DOB: {applicant_dob}
- Coverage requested: ${coverage_requested:,.0f}
- Annual income: ${income:,.0f}

Policy record:
- Policy holder: {policy_holder}
- Policy status: {policy_status}
- Coverage on policy: ${policy_coverage:,.0f}
- Premium: ${premium:,.0f}

Analyze the match quality. Consider:
1. Name match (allow for nicknames, middle names, suffixes)
2. Coverage amount consistency (is the requested amount within policy limits?)
3. Income adequacy (is the income sufficient for the premium?)

Return a JSON object with:
- "match_quality": "good" | "partial" | "poor"
- "flags": list of specific concerns (empty if none)
- "rationale": brief explanation of your assessment
- "confidence": float between 0.0 and 1.0
"""


def review_node(state: UnderwritingState) -> dict[str, Any]:
    """Cross-check applicant details against the verified policy record."""
    logger.info("review: reconciling applicant with policy")

    if state.policy is None:
        logger.warning("review: no policy to reconcile against")
        return {
            "stage": "review",
            **append_audit(state, "review", "no policy to reconcile", "warn", confidence=0.0),
        }

    # Try LLM-powered review first
    try:
        llm = get_llm()
        prompt = _REVIEW_PROMPT.format(
            applicant_name=state.applicant.full_name or "Unknown",
            applicant_dob=state.applicant.date_of_birth or "Unknown",
            coverage_requested=state.applicant.coverage_amount or 0.0,
            income=state.applicant.annual_income or 0.0,
            policy_holder=state.policy.policy_holder,
            policy_status=state.policy.status,
            policy_coverage=state.policy.coverage_amount,
            premium=state.policy.premium,
        )
        response = llm.invoke([
            SystemMessage(content="You are a precise underwriting review analyst. Return ONLY valid JSON."),
            HumanMessage(content=prompt),
        ])

        import json
        import re

        text = str(response.content)
        # Extract JSON block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            flags: list[str] = data.get("flags", [])
            match_quality = data.get("match_quality", "good")
            rationale = data.get("rationale", "")
            confidence = float(data.get("confidence", 0.8))

            if flags:
                logger.warning("review: LLM found %d flag(s): %s", len(flags), flags)
                return {
                    "stage": "review",
                    **append_audit(state, "review", f"{match_quality} match: {rationale}", "warn", confidence=confidence),
                }

            logger.info("review: LLM assessment: %s match", match_quality)
            return {
                "stage": "review",
                **append_audit(state, "review", f"{match_quality} match: {rationale}", confidence=confidence),
            }
    except Exception as exc:
        logger.warning("review: LLM review failed, falling back to rule-based: %s", exc)

    # Fallback: rule-based reconciliation
    flags: list[str] = []
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
            **append_audit(state, "review", "; ".join(flags), "warn", confidence=0.6),
        }

    logger.info("review: applicant reconciled with policy")
    return {
        "stage": "review",
        **append_audit(state, "review", "applicant reconciled with policy", confidence=0.95),
    }
