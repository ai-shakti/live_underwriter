# Compliance Layer

The compliance layer is built into the graph as **conditional edges (gates)**, not post-hoc filters. This means every regulatory check happens before any decision is made, and every compliance decision is logged in the audit trail.

## Regulatory Framework

### 1. SCRA (Servicemembers Civil Relief Act)
- **Trigger**: Keywords in transcript (military, active duty, deployed, etc.)
- **Effect**: Special interest rate cap of 6% during active duty
- **Gate**: Routes to `scra` path for special handling
- **Audit**: "SCRA: Servicemember detected — special protections apply"

### 2. Reg F (Fair Debt Collection Practices Act)
- **Phone calls**: Max 3 per week per channel
- **Calling hours**: 8:00 AM - 9:00 PM local time
- **Harassment**: Prohibited — monitored via keyword detection
- **Gate**: Blocks contact if limits exceeded

### 3. UDAAP (Unfair, Deceptive, or Abusive Acts or Practices)
- **Fairness checks**: Detects patterns like "no questions asked", "guaranteed approval"
- **Transparency**: Every decision includes a human-readable rationale
- **Audit trail**: Full decision trace for regulatory review

### 4. State-Specific Rules
| State | Rules |
|-------|-------|
| CA | Prop 103: Prior approval for rate changes; Earthquake coverage must be offered |
| NY | Reg 64: Strict claim timelines; No-fault insurance required |
| TX | Rate filing for increases > 10%; Right to repair |
| FL | Sinkhole coverage; AOB restrictions |
| MA | Strict underwriting guidelines; Safe driver plan |

## Implementation

Compliance checks are implemented as:
1. **`compliance_node`**: Detects SCRA status, jurisdiction, UDAAP concerns
2. **`_compliance_gate`**: Routes based on regulatory flags
3. **`regf_compliance_node`** (collections): Enforces Reg F limits

All compliance decisions are logged with:
- Timestamp
- Regulation cited
- Decision rationale
- Confidence score
