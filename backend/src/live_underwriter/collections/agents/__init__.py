"""Collections specialist agents.

Each agent is a LangGraph node that operates on the shared
:class:`~live_underwriter.collections.state.CollectionsState`.
"""

from __future__ import annotations

from live_underwriter.collections.agents.borrower_intake import borrower_intake_node
from live_underwriter.collections.agents.regf_compliance import regf_compliance_node
from live_underwriter.collections.agents.hardship_triage import hardship_triage_node
from live_underwriter.collections.agents.rpc_optimization import rpc_optimization_node
from live_underwriter.collections.agents.arrangement_engine import arrangement_engine_node
from live_underwriter.collections.agents.execution import execution_node

__all__ = [
    "borrower_intake_node",
    "regf_compliance_node",
    "hardship_triage_node",
    "rpc_optimization_node",
    "arrangement_engine_node",
    "execution_node",
]
