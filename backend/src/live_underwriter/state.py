"""Underwriting state schema for the LangGraph workflow.

This module defines the shared state that flows through every node of the
underwriting agent team. Each agent reads from and writes to this state.
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ApplicantInfo(BaseModel):
    """Normalized applicant data collected during intake."""

    full_name: str | None = None
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    policy_number: str | None = None
    coverage_amount: float | None = None
    occupation: str | None = None
    annual_income: float | None = None


class PolicyRecord(BaseModel):
    """Verified policy/account record returned by the verification agent."""

    policy_number: str
    policy_holder: str
    status: str = "active"
    coverage_amount: float = 0.0
    premium: float = 0.0
    verified: bool = False


class RiskAssessment(BaseModel):
    """Output of the risk / decision agent."""

    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_level: str = "low"  # low | medium | high
    decision: str = "pending"  # accept | decline | review
    rationale: str = ""
    flags: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    """A single step in the underwriting audit trail (explainability)."""

    stage: str
    detail: str
    outcome: str = "ok"  # ok | warn | error


class UploadedDocument(BaseModel):
    """A document uploaded by the user for review."""

    filename: str
    doc_type: str = "uploaded"
    content: str = ""


class UnderwritingState(BaseModel):
    """The full state shared across the underwriting workflow."""

    messages: Annotated[list[Any], add_messages] = Field(default_factory=list)
    applicant: ApplicantInfo = Field(default_factory=ApplicantInfo)
    policy: PolicyRecord | None = None
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    stage: str = "intake"
    transcript: str = ""
    decision: str | None = None
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
