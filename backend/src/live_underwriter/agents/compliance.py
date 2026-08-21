"""Compliance agent — regulatory checks for the underwriting workflow.

This agent enforces:
- SCRA (Servicemembers Civil Relief Act): Special interest rate caps and
  protections for military borrowers.
- State-specific rules: 50-state patchwork of insurance regulations.
- UDAAP (Unfair, Deceptive, or Abusive Acts or Practices): Fairness checks.
- Regulatory limits: Coverage limits, rate caps, disclosure requirements.

Every compliance decision is logged in the audit trail for regulatory review.
"""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import ComplianceContext, UnderwritingState

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# State-level regulatory rules (simplified for POC)
# ---------------------------------------------------------------------------

_STATE_RULES: dict[str, list[str]] = {
    "CA": [
        "Prop 103: Prior approval required for rate changes",
        "CA minimum liability: 15/30/5",
        "Earthquake coverage must be offered",
    ],
    "NY": [
        "NY Reg 64: Strict claim handling timelines",
        "No-fault insurance required",
        "Pre-existing condition exclusion limited to 12 months",
    ],
    "TX": [
        "TX DOI: Rate filing required for increases > 10%",
        "Right to repair: Insurer cannot mandate specific shops",
    ],
    "FL": [
        "FL Statute 627: Sinkhole coverage must be offered",
        "Assignment of benefits (AOB) restrictions apply",
        "Citizens Insurance eligibility rules apply",
    ],
    "MA": [
        "MA Reg 211 CMR: Strict underwriting guidelines",
        "Safe driver insurance plan required",
        "Step-down provisions for non-family drivers",
    ],
}

# ---------------------------------------------------------------------------
# SCRA detection keywords
# ---------------------------------------------------------------------------

_SCRA_KEYWORDS = [
    "military", "active duty", "deployed", "servicemember",
    "army", "navy", "air force", "marines", "coast guard",
    "national guard", "reserves", "uniformed services",
]

# ---------------------------------------------------------------------------
# UDAAP fairness checks
# ---------------------------------------------------------------------------

_UDAAP_RISKY_PATTERNS = [
    "no questions", "guaranteed", "no credit check",
    "no documentation", "everyone approved",
]


def _detect_scra(transcript: str, applicant_name: str) -> bool:
    """Detect SCRA-protected status from the transcript."""
    lowered = transcript.lower()
    return any(kw in lowered for kw in _SCRA_KEYWORDS)


def _detect_jurisdiction(transcript: str, address: str | None) -> str:
    """Detect the applicant's jurisdiction from transcript or address."""
    # Try address first
    if address:
        for state_code in _STATE_RULES:
            if state_code in address.upper():
                return state_code

    # Try transcript for state mentions
    lowered = transcript.lower()
    state_map = {
        "CA": ["california", "ca "],
        "NY": ["new york", "ny "],
        "TX": ["texas", "tx "],
        "FL": ["florida", "fl "],
        "MA": ["massachusetts", "ma ", "mass "],
    }
    for code, keywords in state_map.items():
        if any(kw in lowered for kw in keywords):
            return code

    return ""


def _check_udaap(transcript: str) -> list[str]:
    """Check for UDAAP-violating patterns in the transcript."""
    lowered = transcript.lower()
    return [
        f"UDAAP concern: '{pattern}' detected"
        for pattern in _UDAAP_RISKY_PATTERNS
        if pattern in lowered
    ]


def compliance_node(state: UnderwritingState) -> dict[str, Any]:
    """Run compliance checks on the application.

    Detects SCRA status, jurisdiction, and UDAAP concerns.
    Sets compliance flags that downstream gates use for routing.
    """
    logger.info("compliance: running regulatory checks")
    flags: list[str] = []
    transcript = state.transcript or ""
    address = state.applicant.address

    # 1. SCRA detection
    scra_active = _detect_scra(transcript, state.applicant.full_name or "")
    if scra_active:
        flags.append("SCRA: Servicemember detected — special protections apply")
        logger.info("compliance: SCRA status detected")

    # 2. Jurisdiction detection
    jurisdiction = _detect_jurisdiction(transcript, address)
    state_rules: list[str] = []
    if jurisdiction:
        state_rules = _STATE_RULES.get(jurisdiction, [])
        for rule in state_rules:
            flags.append(f"Compliance ({jurisdiction}): {rule}")
        logger.info("compliance: jurisdiction detected: %s with %d rules", jurisdiction, len(state_rules))

    # 3. UDAAP fairness check
    udaap_flags = _check_udaap(transcript)
    flags.extend(udaap_flags)
    if udaap_flags:
        logger.warning("compliance: %d UDAAP concern(s)", len(udaap_flags))

    # Build compliance context
    compliance = ComplianceContext(
        jurisdiction=jurisdiction,
        scra_status=scra_active,
        state_specific_rules=state_rules,
    )

    if flags:
        logger.warning("compliance: %d flag(s): %s", len(flags), flags)
        return {
            "compliance_flags": flags,
            "compliance": compliance,
            "stage": "compliance",
            **append_audit(state, "compliance", "; ".join(flags), "warn", confidence=0.8),
        }

    logger.info("compliance: no compliance concerns")
    return {
        "compliance_flags": [],
        "compliance": compliance,
        "stage": "compliance",
        **append_audit(state, "compliance", "no compliance concerns", confidence=0.95),
    }
