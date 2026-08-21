"""LangGraph state machine for the live underwriting workflow.

This wires the specialist agents into a stateful, branchable graph that
mirrors the underwriting analyst's decision process. Multiple conditional
gates demonstrate the branching-decision-engine pattern.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from live_underwriter.agents import (
    compliance_node,
    document_review_node,
    fraud_check_node,
    human_review_node,
    normalize_node,
    review_node,
    risk_decision_node,
    validate_node,
    verify_policy_node,
)
from live_underwriter.agents._helpers import append_audit
from live_underwriter.state import UnderwritingState


def build_graph() -> StateGraph[UnderwritingState]:
    """Build and return the underwriting workflow graph."""
    graph = StateGraph(UnderwritingState)

    # Nodes
    graph.add_node("normalize", normalize_node)
    graph.add_node("validate", validate_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("verify_policy", verify_policy_node)
    graph.add_node("review", review_node)
    graph.add_node("fraud_check", fraud_check_node)
    graph.add_node("document_review", document_review_node)
    graph.add_node("decision", risk_decision_node)
    graph.add_node("human_review", human_review_node)

    # Edges
    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "validate")

    # Gate 1: Data quality gate — route based on data completeness
    graph.add_conditional_edges(
        "validate",
        _data_quality_gate,
        {
            "complete": "compliance",
            "partial": "compliance",  # proceed but flagged
            "insufficient": END,  # can't proceed without more data
        },
    )

    # Gate 2: Compliance gate — route based on regulatory flags
    graph.add_conditional_edges(
        "compliance",
        _compliance_gate,
        {
            "standard": "verify_policy",
            "scra": "verify_policy",  # SCRA-protected → special handling
            "blocked": END,  # Regulatory block
        },
    )

    # Gate 3: Policy gate — route based on policy verification
    graph.add_conditional_edges(
        "verify_policy",
        _policy_gate,
        {"continue": "review", "reject": END},
    )

    # Gate 4: Risk gate — route based on risk score after review
    graph.add_conditional_edges(
        "review",
        _risk_gate,
        {
            "auto_accept": "fraud_check",
            "review": "fraud_check",
            "escalate": "human_review",  # flagged cases go to human review
        },
    )

    # Human review resolves back to the main flow
    graph.add_conditional_edges(
        "human_review",
        _human_review_gate,
        {
            "continue": "fraud_check",
            "reject": END,
        },
    )

    graph.add_edge("fraud_check", "document_review")
    graph.add_edge("document_review", "decision")
    graph.add_edge("decision", END)

    return graph


# ---------------------------------------------------------------------------
# Gate 1: Data quality
# ---------------------------------------------------------------------------


def _data_quality_gate(state: UnderwritingState) -> str:
    """Route based on data completeness.

    - complete: All required fields present → proceed
    - partial: Some fields missing → proceed but flagged
    - insufficient: Critical fields missing → end
    """
    applicant = state.applicant
    required = ["full_name", "policy_number", "coverage_amount"]
    critical = ["full_name", "policy_number"]

    missing_required = [f for f in required if getattr(applicant, f) is None]
    missing_critical = [f for f in critical if getattr(applicant, f) is None]

    if missing_critical:
        return "insufficient"
    if missing_required:
        return "partial"
    return "complete"


# ---------------------------------------------------------------------------
# Gate 2: Compliance
# ---------------------------------------------------------------------------


def _compliance_gate(state: UnderwritingState) -> str:
    """Route based on regulatory compliance flags.

    - standard: No compliance concerns → proceed normally
    - scra: SCRA-protected servicemember → special handling path
    - blocked: Regulatory block → end
    """
    if state.compliance.scra_status:
        return "scra"
    # Check for hard regulatory blocks
    for flag in state.compliance_flags:
        if "blocked" in flag.lower() or "prohibited" in flag.lower():
            return "blocked"
    return "standard"


# ---------------------------------------------------------------------------
# Gate 3: Policy verification
# ---------------------------------------------------------------------------


def _policy_gate(state: UnderwritingState) -> str:
    """Route based on whether the policy was verified."""
    if state.policy is not None and state.policy.verified:
        return "continue"
    return "reject"


# ---------------------------------------------------------------------------
# Gate 3: Risk-based routing
# ---------------------------------------------------------------------------


def _risk_gate(state: UnderwritingState) -> str:
    """Route based on risk assessment after review.

    - auto_accept: Low risk, clean review → fast path
    - review: Medium risk or minor flags → standard path
    - escalate: High risk or major flags → human review path
    """
    # Check for fraud flags or document issues
    has_major_flags = any(
        kw in " ".join(state.risk.flags).lower()
        for kw in ["fraud", "overdraft", "delinquent", "default", "keyword"]
    ) if state.risk.flags else False

    if has_major_flags:
        return "escalate"

    # Check review outcome
    if state.policy and state.policy.verified:
        return "auto_accept"

    return "review"


# ---------------------------------------------------------------------------
# Gate 5: Human review resolution
# ---------------------------------------------------------------------------


def _human_review_gate(state: UnderwritingState) -> str:
    """Route based on the human reviewer's decision.

    - continue: Reviewer approved or modified → proceed to fraud check
    - reject: Reviewer declined → end
    """
    if state.review_decision == "declined":
        return "reject"
    return "continue"


def compile_graph() -> CompiledStateGraph[UnderwritingState]:
    """Compile the graph into a runnable application."""
    return build_graph().compile()