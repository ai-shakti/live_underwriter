"""Underwriting state schema for the LangGraph workflow.

This module defines the shared state that flows through every node of the
underwriting agent team. Each agent reads from and writes to this state.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    """A single step in the underwriting audit trail (explainability).

    Every agent node appends an AuditEntry so the full decision path is
    traceable — this is the foundation for regulatory compliance, debugging,
    and explainability.
    """

    stage: str
    detail: str
    outcome: str = "ok"  # ok | warn | error
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class UploadedDocument(BaseModel):
    """A document uploaded by the user for review."""

    filename: str
    doc_type: str = "uploaded"
    content: str = ""


class ComplianceContext(BaseModel):
    """Regulatory context for the applicant — checked at compliance gates."""

    jurisdiction: str = ""
    scra_status: bool = False  # Servicemembers Civil Relief Act
    regulatory_limits: dict[str, Any] = Field(default_factory=dict)
    state_specific_rules: list[str] = Field(default_factory=list)


class CrossProductContext(BaseModel):
    """Cross-context data — policy history, claims, relationship tenure."""

    has_existing_policy: bool = False
    has_claims_history: bool = False
    relationship_tenure_months: int = 0
    total_premiums_paid: float = 0.0


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

    # Phase 2: Multiple conditional gates
    compliance_flags: list[str] = Field(default_factory=list)
    data_quality: str = "pending"  # complete | partial | insufficient
    compliance: ComplianceContext = Field(default_factory=ComplianceContext)
    cross_product: CrossProductContext = Field(default_factory=CrossProductContext)

    # Phase 3: Human-in-the-loop
    review_required: bool = False
    review_decision: str | None = None  # approved | declined | modified
    reviewer_notes: str | None = None
