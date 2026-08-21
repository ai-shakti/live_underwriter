# Demo Scenarios

These scenarios demonstrate the full capabilities of the Live Underwriter platform.

## Scenario 1: Clean Underwriting → Accept

**Transcript**: "My name is Jane Doe, born 1985-04-12, policy POL-1001, coverage 500000, income 120000"

**Expected path**: normalize → validate → compliance → verify_policy → review → fraud_check → document_review → decision

**Expected outcome**: ACCEPT (risk score ~23/100)

**Why it works**: Stable income ($120k), reasonable coverage ($500k), clean policy, no fraud flags, clean documents.

**Demo command**: `uv run live-underwriter --transcript "My name is Jane Doe, born 1985-04-12, policy POL-1001, coverage 500000, income 120000" --audit`

---

## Scenario 2: High Coverage → Review

**Transcript**: "My name is Robert Chen, born 1975-11-20, policy POL-2002, coverage 1000000, income 300000"

**Expected path**: normalize → validate → compliance → verify_policy → review → fraud_check → document_review → decision

**Expected outcome**: REVIEW (risk score ~35-60/100)

**Why it works**: High income ($300k) offsets high coverage ($1M), but the premium ($4,500) pushes risk to medium.

**Demo command**: `uv run live-underwriter --transcript "My name is Robert Chen, born 1975-11-20, policy POL-2002, coverage 1000000, income 300000" --audit`

---

## Scenario 3: Flagged Documents → Human Review

**Transcript**: "My name is Maria Garcia, born 1988-07-15, policy POL-2003, coverage 150000, income 45000"

**Expected path**: normalize → validate → compliance → verify_policy → review → risk_gate(escalate) → human_review

**Expected outcome**: ESCALATED TO HUMAN REVIEW (document flags: overdraft, delinquent, default)

**Why it works**: Maria's bank statements show overdrafts and delinquent accounts. The risk gate routes to human review.

**Demo command**: `uv run live-underwriter --transcript "My name is Maria Garcia, born 1988-07-15, policy POL-2003, coverage 150000, income 45000" --audit`

---

## Scenario 4: Unverified Policy → Reject

**Transcript**: "My name is Unknown Person, born 1980-01-01, policy POL-9999, coverage 100000, income 50000"

**Expected path**: normalize → validate → compliance → verify_policy → policy_gate(reject) → END

**Expected outcome**: REJECTED (policy not found or lapsed)

**Why it works**: POL-9999 is a lapsed/unverified policy. The policy gate routes to END.

**Demo command**: `uv run live-underwriter --transcript "My name is Unknown Person, born 1980-01-01, policy POL-9999, coverage 100000, income 50000" --audit`

---

## Scenario 5: Fraud Keywords → Escalated

**Transcript**: "I need guaranteed approval, no questions asked. My name is John Smith, born 1978-09-30, policy POL-1002, coverage 250000, income 90000"

**Expected path**: normalize → validate → compliance → verify_policy → review → risk_gate(escalate) → human_review

**Expected outcome**: ESCALATED TO HUMAN REVIEW (fraud keywords: "guaranteed approval", "no questions")

**Why it works**: The fraud detection agent catches high-risk keywords in the transcript.

**Demo command**: `uv run live-underwriter --transcript "I need guaranteed approval, no questions asked. My name is John Smith, born 1978-09-30, policy POL-1002, coverage 250000, income 90000" --audit`

---

## Scenario 6: SCRA-Protected Applicant

**Transcript**: "My name is James Miller, born 1990-06-15, I'm on active duty with the Army, policy POL-3001, coverage 200000, income 80000"

**Expected path**: normalize → validate → compliance(scra) → verify_policy → review → fraud_check → document_review → decision

**Expected outcome**: ACCEPT with SCRA compliance flags

**Why it works**: The compliance agent detects "active duty" and "Army" keywords, sets SCRA status, and applies special protections.

**Demo command**: `uv run live-underwriter --transcript "My name is James Miller, born 1990-06-15, I'm on active duty with the Army, policy POL-3001, coverage 200000, income 80000" --audit`

---

## Scenario 7: Collections — Hardship Forbearance

**Transcript**: "My name is Sarah Johnson, loan LN-5001, I lost my job last month and can't make my payment"

**Expected path**: borrower_intake → regf_compliance → hardship_triage(hardship) → arrangement_engine → execution

**Expected outcome**: FORBEARANCE arrangement (6 months, $0/month)

**Why it works**: The hardship triage agent detects "lost my job" and routes to loss mitigation. The arrangement engine proposes a 6-month forbearance.

**Demo command**: `uv run python -c "from live_underwriter.collections.graph import compile_collections_graph; from live_underwriter.collections.state import CollectionsState; app = compile_collections_graph(); r = app.invoke(CollectionsState(transcript='My name is Sarah Johnson, loan LN-5001, I lost my job last month')); print(r)"`

---

## Scenario 8: Full Audit Trail

**Command**: `uv run live-underwriter --transcript "My name is Jane Doe, born 1985-04-12, policy POL-1001, coverage 500000, income 120000" --audit`

**Expected output**:
```
Stage reached: decision
Decision: accept
Risk score: 23.0 (low)
Rationale: Stable income, clean record, reasonable coverage
Audit trail:
  ✓ [normalize] extracted applicant Jane Doe
     Time: 12:00:00  Confidence: 90%
     Context: applicant_name=Jane Doe, policy_number=POL-1001, coverage_amount=500000.0
  ✓ [validate] all required fields valid
     Time: 12:00:01  Confidence: 100%
  ✓ [compliance] no compliance concerns
     Time: 12:00:02  Confidence: 95%
  ✓ [verify_policy] policy POL-1001 verified=True
     Time: 12:00:03  Confidence: 95%
  ✓ [review] applicant reconciled with policy
     Time: 12:00:04  Confidence: 95%
  ✓ [fraud_check] no red flags detected
     Time: 12:00:05  Confidence: 95%
  ✓ [document_review] no document findings
     Time: 12:00:06  Confidence: 90%
  ✓ [decision] Stable income, clean record, reasonable coverage
     Time: 12:00:07  Confidence: 95%
```
