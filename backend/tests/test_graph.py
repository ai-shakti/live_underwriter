"""Tests for the underwriting workflow graph."""

from __future__ import annotations

from live_underwriter.graph import build_graph
from live_underwriter.state import PolicyRecord, UnderwritingState


def test_graph_has_expected_nodes() -> None:
    """The graph should contain all specialist agent nodes."""
    graph = build_graph()
    nodes = set(graph.nodes.keys())
    expected = {
        "normalize",
        "validate",
        "verify_policy",
        "review",
        "fraud_check",
        "document_review",
        "decision",
    }
    assert expected.issubset(nodes)


def test_policy_gate_routes_to_reject_when_unverified() -> None:
    """A missing/unverified policy should route to the reject (END) branch."""
    state = UnderwritingState(policy=None)
    # The gate is a module-level function; verify via the compiled graph instead.
    from live_underwriter.graph import _policy_gate

    assert _policy_gate(state) == "reject"


def test_policy_gate_routes_to_continue_when_verified() -> None:
    """A verified policy should route to the review branch."""
    from live_underwriter.graph import _policy_gate

    state = UnderwritingState(
        policy=PolicyRecord(policy_number="P-1001", policy_holder="Jane Doe", verified=True)
    )
    assert _policy_gate(state) == "continue"
