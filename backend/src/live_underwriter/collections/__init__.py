"""Collections workflow — servicing-side AI decision engine.

Mirrors the underwriting architecture but for debt collection:
borrower intake → compliance → hardship triage → RPC optimization →
arrangement engine → execution.

Shares the same AuditEntry model, human-in-the-loop pattern, and
compliance gate pattern from the core underwriting module.
"""

from __future__ import annotations

from live_underwriter.collections.graph import build_collections_graph, compile_collections_graph
from live_underwriter.collections.state import CollectionsState

__all__ = [
    "build_collections_graph",
    "compile_collections_graph",
    "CollectionsState",
]
