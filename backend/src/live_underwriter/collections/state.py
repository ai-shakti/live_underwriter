"""Collections workflow state schema.

Mirrors the underwriting state pattern but for the servicing side:
borrower intake, delinquency tracking, contact history, hardship assessment,
and payment arrangement management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class BorrowerInfo(BaseModel):
    """Normalized borrower data collected during intake."""

    full_name: str | None = None
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    loan_number: str | None = None
    outstanding_balance: float | None = None
    monthly_payment: float | None = None
    occupation: str | None = None
    annual_income: float | None = None


class LoanRecord(BaseModel):
    """Verified loan record returned by the verification agent."""

    loan_number: str
    borrower_name: str
    status: str = "active"  # active | delinquent | charged_off | paid
    original_amount: float = 0.0
    outstanding_balance: float = 0.0
    monthly_payment: float = 0.0
    interest_rate: float = 0.0
    delinquency_days: int = 0
    verified: bool = False


class ContactLogEntry(BaseModel):
    """A single contact attempt in the collections workflow."""

    channel: str  # phone | sms | email | mail | portal
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"  # pending | completed | failed | blocked
    notes: str = ""


class HardshipAssessment(BaseModel):
    """Assessment of borrower hardship for loss mitigation."""

    hardship_type: str = "none"  # none | medical | job_loss | natural_disaster | other
    severity: str = "low"  # low | medium | high
    recommended_action: str = "standard"  # standard | forbearance | modification | settlement
    rationale: str = ""


class PaymentArrangement(BaseModel):
    """A proposed or active payment arrangement."""

    arrangement_type: str = "standard"  # standard | forbearance | modification | settlement
    monthly_amount: float = 0.0
    duration_months: int = 0
    total_amount: float = 0.0
    status: str = "proposed"  # proposed | active | completed | defaulted


class CollectionsState(BaseModel):
    """The full state shared across the collections workflow."""

    borrower: BorrowerInfo = Field(default_factory=BorrowerInfo)
    loan: LoanRecord | None = None
    hardship: HardshipAssessment = Field(default_factory=HardshipAssessment)
    arrangement: PaymentArrangement | None = None
    stage: str = "intake"
    transcript: str = ""
    decision: str | None = None
    delinquency_stage: str = "current"  # current | 1-29 | 30-59 | 60-89 | 90+
    contact_history: list[ContactLogEntry] = Field(default_factory=list)
    hardship_flag: bool = False
    compliance_flags: list[str] = Field(default_factory=list)
    audit_trail: list[Any] = Field(default_factory=list)
    review_required: bool = False
    review_decision: str | None = None
    reviewer_notes: str | None = None
