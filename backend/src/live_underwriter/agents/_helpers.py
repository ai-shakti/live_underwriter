"""Shared helpers for the underwriting agents."""

from __future__ import annotations

from typing import Any

from live_underwriter.state import AuditEntry, UnderwritingState


def append_audit(state: UnderwritingState, stage: str, detail: str, outcome: str = "ok") -> dict[str, Any]:
    """Return a state update that appends an audit entry.

    LangGraph merges returned dicts into state; returning a new list is the
    standard way to append to a list field.
    """
    return {
        "audit_trail": [*state.audit_trail, AuditEntry(stage=stage, detail=detail, outcome=outcome)]
    }
