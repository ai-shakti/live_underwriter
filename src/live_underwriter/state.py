"""Underwriting state schema for the LangGraph workflow.

This module defines the shared state that flows through every node of the
underwriting agent team. Each agent reads from and writes to this state.
"""

from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ApplicantInfo(BaseModel):
    """Normalized applicant data collected during intake."""

    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_amount: Optional[float] = None
    occupation: Optional[str] = None
    annual_income: Optional[float] = None


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


class UnderwritingState(BaseModel):
    """The full state shared across the underwriting workflow."""

    messages: Annotated[list, add_messages] = Field(default_factory=list)
    applicant: ApplicantInfo = Field(default_factory=ApplicantInfo)
    policy: Optional[PolicyRecord] = None
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    stage: str = "intake"
    transcript: str = ""
    decision: Optional[str] = None
