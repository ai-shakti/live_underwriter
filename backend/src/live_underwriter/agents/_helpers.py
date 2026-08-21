"""Shared helpers for the underwriting agents."""

from __future__ import annotations

from typing import Any

from live_underwriter.state import AuditEntry, UnderwritingState


def append_audit(
    state: UnderwritingState,
    stage: str,
    detail: str,
    outcome: str = "ok",
    confidence: float = 0.0,
    input_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a state update that appends an audit entry.

    LangGraph merges returned dicts into state; returning a new list is the
    standard way to append to a list field.

    Args:
        state: Current workflow state.
        stage: Name of the agent/node that produced this entry.
        detail: Human-readable description of what happened.
        outcome: One of "ok", "warn", "error".
        confidence: How confident the agent is in its decision (0.0-1.0).
        input_snapshot: Key state fields at decision time for traceability.
    """
    snapshot = input_snapshot or _build_snapshot(state, stage)
    return {
        "audit_trail": [
            *state.audit_trail,
            AuditEntry(
                stage=stage,
                detail=detail,
                outcome=outcome,
                confidence=confidence,
                input_snapshot=snapshot,
            ),
        ]
    }


def _build_snapshot(state: UnderwritingState, stage: str) -> dict[str, Any]:
    """Build a relevant input snapshot based on the current stage."""
    snapshot: dict[str, Any] = {"stage": stage}

    if state.applicant.full_name:
        snapshot["applicant_name"] = state.applicant.full_name
    if state.applicant.policy_number:
        snapshot["policy_number"] = state.applicant.policy_number
    if state.applicant.coverage_amount:
        snapshot["coverage_amount"] = state.applicant.coverage_amount
    if state.applicant.annual_income:
        snapshot["annual_income"] = state.applicant.annual_income
    if state.policy:
        snapshot["policy_verified"] = state.policy.verified
        snapshot["policy_status"] = state.policy.status
    if state.risk.risk_score:
        snapshot["risk_score"] = state.risk.risk_score
    if state.risk.flags:
        snapshot["flags"] = list(state.risk.flags)

    return snapshot
