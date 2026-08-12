"""Specialist agents in the underwriting team.

Each agent is a LangGraph node that operates on the shared
:class:`~live_underwriter.state.UnderwritingState`.
"""

from __future__ import annotations

from live_underwriter.state import UnderwritingState


def normalize_node(state: UnderwritingState) -> dict:
    """Normalize raw applicant input into a structured form.

    This is the first step: clean and standardize the collected data
    (trim whitespace, standardize date formats, coerce types) before
    any validation or decisioning happens.
    """
    # TODO: wire in LLM-based normalization of the transcript.
    return {"stage": "normalize"}


def validate_node(state: UnderwritingState) -> dict:
    """Validate that required applicant fields are present and well-formed.

    Runs after normalization. Missing or malformed fields are flagged here
    so the workflow can request clarification before proceeding.
    """
    # TODO: implement field-level validation rules.
    return {"stage": "validate"}


def verify_policy_node(state: UnderwritingState) -> dict:
    """Verify the applicant's policy/account against records.

    This is the gate: if no policy exists, the workflow rejects or escalates.
    """
    # TODO: wire in policy lookup against a records source.
    return {"stage": "verify_policy"}


def review_node(state: UnderwritingState) -> dict:
    """Review and verify the applicant's details before decisioning."""
    # TODO: implement review logic.
    return {"stage": "review"}


def fraud_check_node(state: UnderwritingState) -> dict:
    """Flag suspicious applications for fraud risk."""
    # TODO: implement fraud detection heuristics / LLM checks.
    return {"stage": "fraud_check"}


def document_review_node(state: UnderwritingState) -> dict:
    """Analyze supporting documents submitted with the application."""
    # TODO: implement document analysis.
    return {"stage": "document_review"}


def risk_decision_node(state: UnderwritingState) -> dict:
    """Compute the risk score and produce the underwriting decision."""
    # TODO: implement risk scoring and decision logic.
    return {"stage": "decision"}
