/** Shared types matching the FastAPI backend response. */

export interface AuditEntry {
  stage: string;
  detail: string;
  outcome: "ok" | "warn" | "error";
}

export interface ApplicantInfo {
  full_name: string | null;
  date_of_birth: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  policy_number: string | null;
  coverage_amount: number | null;
  occupation: string | null;
  annual_income: number | null;
}

export interface PolicyRecord {
  policy_number: string;
  policy_holder: string;
  status: string;
  coverage_amount: number;
  premium: number;
  verified: boolean;
}

export interface UnderwriteResponse {
  stage: string;
  decision: string | null;
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  rationale: string;
  flags: string[];
  applicant: ApplicantInfo;
  policy: PolicyRecord | null;
  audit_trail: AuditEntry[];
}

export interface Review {
  id: number;
  applicant_name: string;
  policy_number: string | null;
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  ai_decision: string;
  rationale: string;
  flags: string[];
  status: "pending" | "approved" | "declined";
  reviewer_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface SampleApplicant {
  id: string;
  name: string;
  description: string;
  expected_outcome: string;
  transcript: string;
}
