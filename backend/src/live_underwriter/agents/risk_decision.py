"""Risk decision agent — compute risk score and produce the decision."""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import RiskAssessment, UnderwritingState

logger = get_logger(__name__)

# Weight of each risk factor (0-100 scale).
_COVERAGE_WEIGHT = 0.4
_INCOME_WEIGHT = 0.3
_PREMIUM_WEIGHT = 0.3


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

    score = (
        _coverage_risk(coverage) * _COVERAGE_WEIGHT
        + _income_risk(income) * _INCOME_WEIGHT
        + _premium_risk(premium) * _PREMIUM_WEIGHT
    )
    score = round(min(100.0, max(0.0, score)), 1)
    level = _level_from_score(score)
    decision = _decision_from_level(level)

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
    logger.info("decision: %s (%s, score=%s)", decision, level, score)
    return {
        "risk": risk,
        "decision": decision,
        "stage": "decision",
        **append_audit(state, "decision", rationale),
    }
