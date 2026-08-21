"""Risk decision agent — compute risk score and produce the decision.

Uses an LLM to generate a nuanced risk assessment with human-readable
rationale, then combines it with rule-based scoring for consistency.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from live_underwriter.agents._helpers import append_audit
from live_underwriter.llm import get_llm
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import RiskAssessment, UnderwritingState

logger = get_logger(__name__)

# Weight of each risk factor (0-100 scale).
_COVERAGE_WEIGHT = 0.4
_INCOME_WEIGHT = 0.3
_PREMIUM_WEIGHT = 0.3

_RISK_PROMPT = """You are an expert underwriting risk analyst. Evaluate this application
and provide a structured risk assessment.

Applicant: {applicant_name}
Occupation: {occupation}
Annual Income: ${income:,.0f}
Requested Coverage: ${coverage:,.0f}
Policy Premium: ${premium:,.0f}
Policy Status: {policy_status}
Fraud/Document Flags: {flags}

Consider:
1. Coverage-to-income ratio (high coverage on low income = risk)
2. Premium affordability (premium > 10% of income = risk)
3. Policy status and history
4. Any fraud or document flags

Return ONLY a JSON object with:
- "risk_score": float between 0 and 100
- "risk_level": "low" | "medium" | "high"
- "decision": "accept" | "review" | "decline"
- "rationale": 2-3 sentence explanation of the decision
- "key_factors": list of the most important factors driving the decision
"""


def _coverage_risk(coverage: float) -> float:
    """Higher coverage -> higher risk (larger exposure)."""
    if coverage >= 1_000_000:
        return 80.0
    if coverage >= 500_000:
        return 50.0
    if coverage >= 100_000:
        return 25.0
    return 10.0


def _income_risk(income: float | None) -> float:
    """Lower income relative to coverage -> higher risk."""
    if income is None or income <= 0:
        return 60.0
    if income < 50_000:
        return 55.0
    if income < 100_000:
        return 30.0
    return 10.0


def _premium_risk(premium: float) -> float:
    """Higher premium -> higher risk."""
    if premium >= 5_000:
        return 70.0
    if premium >= 2_000:
        return 40.0
    return 15.0


def _level_from_score(score: float) -> str:
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _decision_from_level(level: str) -> str:
    if level == "high":
        return "decline"
    if level == "medium":
        return "review"
    return "accept"


def risk_decision_node(state: UnderwritingState) -> dict[str, Any]:
    """Compute the risk score and produce the underwriting decision."""
    logger.info("decision: computing risk score")
    applicant = state.applicant
    policy = state.policy

    coverage = applicant.coverage_amount or (policy.coverage_amount if policy else 0.0)
    premium = policy.premium if policy else 0.0
    income = applicant.annual_income

    # Rule-based score (consistent baseline)
    rule_score = (
        _coverage_risk(coverage) * _COVERAGE_WEIGHT
        + _income_risk(income) * _INCOME_WEIGHT
        + _premium_risk(premium) * _PREMIUM_WEIGHT
    )
    rule_score = round(min(100.0, max(0.0, rule_score)), 1)

    # Try LLM-powered assessment for richer rationale
    llm_rationale = ""
    llm_key_factors: list[str] = []
    try:
        llm = get_llm()
        prompt = _RISK_PROMPT.format(
            applicant_name=applicant.full_name or "Unknown",
            occupation=applicant.occupation or "Unknown",
            income=income or 0.0,
            coverage=coverage,
            premium=premium,
            policy_status=policy.status if policy else "N/A",
            flags="; ".join(state.risk.flags) if state.risk.flags else "None",
        )
        response = llm.invoke([
            SystemMessage(content="You are an expert underwriting risk analyst. Return ONLY valid JSON."),
            HumanMessage(content=prompt),
        ])

        text = str(response.content)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            llm_score = float(data.get("risk_score", rule_score))
            llm_rationale = data.get("rationale", "")
            llm_key_factors = data.get("key_factors", [])

            # Blend LLM score with rule score (weighted average)
            score = round(rule_score * 0.6 + llm_score * 0.4, 1)
        else:
            score = rule_score
    except Exception as exc:
        logger.warning("decision: LLM assessment failed, using rule-based: %s", exc)
        score = rule_score

    score = round(min(100.0, max(0.0, score)), 1)
    level = _level_from_score(score)
    decision = _decision_from_level(level)

    # Build rationale
    if llm_rationale:
        rationale = llm_rationale
    else:
        rationale = (
            f"coverage=${coverage:,.0f}, income=${income or 0:,.0f}, "
            f"premium=${premium:,.0f} -> risk {level} ({score}/100)"
        )

    risk = RiskAssessment(
        risk_score=score,
        risk_level=level,
        decision=decision,
        rationale=rationale,
        flags=list(state.risk.flags),
    )
    # Confidence is inversely related to risk level (low risk = high confidence)
    confidence_map = {"low": 0.95, "medium": 0.7, "high": 0.5}
    confidence = confidence_map.get(level, 0.7)
    logger.info("decision: %s (%s, score=%s)", decision, level, score)
    return {
        "risk": risk,
        "decision": decision,
        "stage": "decision",
        **append_audit(state, "decision", rationale, confidence=confidence),
    }
