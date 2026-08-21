"""Tests for the underwriting workflow graph."""

from __future__ import annotations

from live_underwriter.graph import build_graph
from live_underwriter.state import ComplianceContext, PolicyRecord, UnderwritingState


def test_graph_has_expected_nodes() -> None:
    """The graph should contain all specialist agent nodes."""
    graph = build_graph()
    nodes = set(graph.nodes.keys())
    expected = {
        "normalize",
        "validate",
        "compliance",
        "verify_policy",
        "review",
        "fraud_check",
        "document_review",
        "decision",
        "human_review",
    }
    assert expected.issubset(nodes)


def test_policy_gate_routes_to_reject_when_unverified() -> None:
    """A missing/unverified policy should route to the reject (END) branch."""
    state = UnderwritingState(policy=None)
    from live_underwriter.graph import _policy_gate

    assert _policy_gate(state) == "reject"


def test_policy_gate_routes_to_continue_when_verified() -> None:
    """A verified policy should route to the review branch."""
    from live_underwriter.graph import _policy_gate

    state = UnderwritingState(
        policy=PolicyRecord(policy_number="P-1001", policy_holder="Jane Doe", verified=True)
    )
    assert _policy_gate(state) == "continue"


def test_data_quality_gate_insufficient() -> None:
    """Missing critical fields should route to insufficient."""
    from live_underwriter.graph import _data_quality_gate

    state = UnderwritingState()
    assert _data_quality_gate(state) == "insufficient"


def test_data_quality_gate_complete() -> None:
    """All required fields should route to complete."""
    from live_underwriter.graph import _data_quality_gate

    from live_underwriter.state import ApplicantInfo

    state = UnderwritingState(
        applicant=ApplicantInfo(
            full_name="Jane", policy_number="P-1", coverage_amount=100000.0,
        )
    )
    assert _data_quality_gate(state) == "complete"


def test_compliance_gate_standard() -> None:
    """No compliance flags should route to standard."""
    from live_underwriter.graph import _compliance_gate

    state = UnderwritingState(compliance=ComplianceContext())
    assert _compliance_gate(state) == "standard"


def test_compliance_gate_scra() -> None:
    """SCRA-protected applicant should route to scra path."""
    from live_underwriter.graph import _compliance_gate

    state = UnderwritingState(compliance=ComplianceContext(scra_status=True))
    assert _compliance_gate(state) == "scra"


def test_risk_gate_auto_accept() -> None:
    """Clean review with no flags should route to auto_accept."""
    from live_underwriter.graph import _risk_gate

    state = UnderwritingState(
        policy=PolicyRecord(policy_number="P-1", policy_holder="Jane", verified=True),
    )
    assert _risk_gate(state) == "auto_accept"


def test_risk_gate_escalate_with_fraud_flags() -> None:
    """Fraud flags should route to escalate."""
    from live_underwriter.graph import _risk_gate

    from live_underwriter.state import RiskAssessment

    state = UnderwritingState(
        risk=RiskAssessment(flags=["fraud keyword detected"]),
    )
    assert _risk_gate(state) == "escalate"


def test_human_review_gate_continue() -> None:
    """Approved review should route to continue."""
    from live_underwriter.graph import _human_review_gate

    state = UnderwritingState(review_decision="approved")
    assert _human_review_gate(state) == "continue"


def test_human_review_gate_reject() -> None:
    """Declined review should route to reject."""
    from live_underwriter.graph import _human_review_gate

    state = UnderwritingState(review_decision="declined")
    assert _human_review_gate(state) == "reject"
