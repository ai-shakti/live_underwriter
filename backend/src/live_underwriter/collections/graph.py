"""LangGraph state machine for the collections workflow.

Mirrors the underwriting graph architecture but for the servicing side.
Shares the same patterns: typed state, conditional gates, audit trail,
and human-in-the-loop review.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from live_underwriter.collections.agents import (
    arrangement_engine_node,
    borrower_intake_node,
    execution_node,
    hardship_triage_node,
    regf_compliance_node,
    rpc_optimization_node,
)
from live_underwriter.collections.state import CollectionsState


def build_collections_graph() -> StateGraph[CollectionsState]:
    """Build and return the collections workflow graph."""
    graph = StateGraph(CollectionsState)

    # Nodes
    graph.add_node("borrower_intake", borrower_intake_node)
    graph.add_node("regf_compliance", regf_compliance_node)
    graph.add_node("hardship_triage", hardship_triage_node)
    graph.add_node("rpc_optimization", rpc_optimization_node)
    graph.add_node("arrangement_engine", arrangement_engine_node)
    graph.add_node("execution", execution_node)

    # Edges
    graph.set_entry_point("borrower_intake")
    graph.add_edge("borrower_intake", "regf_compliance")

    # Compliance gate
    graph.add_conditional_edges(
        "regf_compliance",
        _compliance_gate,
        {
            "continue": "hardship_triage",
            "blocked": END,
        },
    )

    # Hardship gate
    graph.add_conditional_edges(
        "hardship_triage",
        _hardship_gate,
        {
            "hardship": "arrangement_engine",
            "standard": "rpc_optimization",
        },
    )

    graph.add_edge("rpc_optimization", "arrangement_engine")
    graph.add_edge("arrangement_engine", "execution")
    graph.add_edge("execution", END)

    return graph


def _compliance_gate(state: CollectionsState) -> str:
    """Route based on compliance flags."""
    if any("blocked" in f.lower() for f in state.compliance_flags):
        return "blocked"
    return "continue"


def _hardship_gate(state: CollectionsState) -> str:
    """Route based on hardship detection."""
    if state.hardship_flag:
        return "hardship"
    return "standard"


def compile_collections_graph() -> CompiledStateGraph[CollectionsState]:
    """Compile the collections graph into a runnable application."""
    return build_collections_graph().compile()
