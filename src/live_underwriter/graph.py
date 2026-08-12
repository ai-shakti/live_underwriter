"""LangGraph state machine for the live underwriting workflow.

This wires the specialist agents into a stateful, branchable graph that
mirrors the underwriting analyst's decision process.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from live_underwriter.agents import (
    document_review_node,
    fraud_check_node,
    normalize_node,
    review_node,
    risk_decision_node,
    validate_node,
    verify_policy_node,
)
from live_underwriter.state import UnderwritingState


def build_graph() -> StateGraph:
    """Build and return the underwriting workflow graph."""
    graph = StateGraph(UnderwritingState)

    # Nodes
    graph.add_node("normalize", normalize_node)
    graph.add_node("validate", validate_node)
    graph.add_node("verify_policy", verify_policy_node)
    graph.add_node("review", review_node)
    graph.add_node("fraud_check", fraud_check_node)
    graph.add_node("document_review", document_review_node)
    graph.add_node("decision", risk_decision_node)

    # Edges
    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "validate")
    graph.add_edge("validate", "verify_policy")

    # Branch: policy exists -> continue; otherwise -> end (reject/escalate)
    graph.add_conditional_edges(
        "verify_policy",
        _policy_gate,
        {"continue": "review", "reject": END},
    )

    graph.add_edge("review", "fraud_check")
    graph.add_edge("fraud_check", "document_review")
    graph.add_edge("document_review", "decision")
    graph.add_edge("decision", END)

    return graph


def _policy_gate(state: UnderwritingState) -> str:
    """Route based on whether the policy was verified."""
    if state.policy is not None and state.policy.verified:
        return "continue"
    return "reject"


def compile_graph():
    """Compile the graph into a runnable application."""
    return build_graph().compile()
