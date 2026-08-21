"""Synthetic data generator for the Live Underwriter POC.

Produces realistic mock applicants, policies, documents, and fraud scenarios
so the demo feels production-grade without any real customer data.

Usage:
    uv run python -m live_underwriter.data_generator  # prints summary
    uv run python -m live_underwriter.data_generator --seed-db  # seeds the DB
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Any

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Seeded RNG for reproducible synthetic data
# ---------------------------------------------------------------------------
_SEED = 42
_rng = random.Random(_SEED)

# ---------------------------------------------------------------------------
# Data pools — realistic names, occupations, locations, etc.
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "Michael", "Jennifer", "David",
    "Linda", "William", "Elizabeth", "Joseph", "Barbara", "Thomas", "Susan",
    "Christopher", "Jessica", "Daniel", "Sarah", "Matthew", "Karen",
    "Anthony", "Lisa", "Mark", "Nancy", "Donald", "Betty", "Steven", "Margaret",
    "Andrew", "Sandra", "Edward", "Ashley", "Brian", "Kimberly", "Jason",
    "Emily", "Ryan", "Donna", "Jacob", "Michelle", "Nicholas", "Carol",
    "Eric", "Amanda", "Jonathan", "Melissa", "Stephen", "Deborah",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
]

OCCUPATIONS = [
    "Software Engineer", "Registered Nurse", "Teacher", "Accountant",
    "Construction Manager", "Marketing Director", "Physician", "Electrician",
    "Financial Analyst", "Police Officer", "Dentist", "Truck Driver",
    "Real Estate Agent", "Graphic Designer", "Chef", "Pharmacist",
    "Mechanical Engineer", "Lawyer", "Social Worker", "Plumber",
    "Data Scientist", "Architect", "Physical Therapist", "Veterinarian",
    "Insurance Agent", "Professor", "Firefighter", "Consultant",
]

STREETS = [
    "Oak", "Maple", "Cedar", "Pine", "Elm", "Birch", "Walnut", "Cherry",
    "Main", "High", "Park", "Lake", "Hill", "River", "Spring", "Sunset",
    "Harbor", "Meadow", "Forest", "Valley",
]

CITIES = [
    ("Springfield", "IL"), ("Portland", "OR"), ("Austin", "TX"),
    ("Denver", "CO"), ("Seattle", "WA"), ("Boston", "MA"),
    ("Nashville", "TN"), ("Phoenix", "AZ"), ("Minneapolis", "MN"),
    ("Raleigh", "NC"), ("Madison", "WI"), ("Richmond", "VA"),
    ("Salt Lake City", "UT"), ("Columbus", "OH"), ("Kansas City", "MO"),
    ("Atlanta", "GA"), ("Tampa", "FL"), ("Sacramento", "CA"),
]

POLICY_PREFIXES = ["POL", "HOM", "AUTO", "LIFE", "HEAL"]

# ---------------------------------------------------------------------------
# Risk profiles
# ---------------------------------------------------------------------------

RISK_PROFILES = {
    "low": {
        "weight": 0.35,
        "income_range": (80_000, 250_000),
        "coverage_range": (50_000, 300_000),
        "premium_range": (400, 1_500),
        "occupation_bias": ["Software Engineer", "Physician", "Lawyer",
                            "Data Scientist", "Architect", "Professor"],
    },
    "medium": {
        "weight": 0.40,
        "income_range": (40_000, 100_000),
        "coverage_range": (100_000, 600_000),
        "premium_range": (800, 3_000),
        "occupation_bias": ["Teacher", "Accountant", "Nurse", "Electrician",
                            "Police Officer", "Chef", "Plumber"],
    },
    "high": {
        "weight": 0.25,
        "income_range": (15_000, 60_000),
        "coverage_range": (500_000, 2_000_000),
        "premium_range": (3_000, 12_000),
        "occupation_bias": ["Truck Driver", "Construction Manager",
                            "Real Estate Agent", "Consultant"],
    },
}

# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------

BANK_STATEMENT_CLEAN = """ACCOUNT STATEMENT
Bank of America | Account: ****{account_last4}
Period: {start_date} - {end_date}
Balance: ${balance:,.2f}

Transactions:
{date}  DEPOSIT           ${deposit_1:,.2f}    Payroll - {employer}
{date2} WITHDRAWAL        ${withdrawal_1:,.2f}   Mortgage Payment
{date3} DEPOSIT           ${deposit_2:,.2f}    Payroll - {employer}
{date4} WITHDRAWAL        ${withdrawal_2:,.2f}   Utility Bill
{date5} DEPOSIT           ${deposit_3:,.2f}    Payroll - {employer}

Summary:
  Total Deposits: ${total_deposits:,.2f}
  Total Withdrawals: ${total_withdrawals:,.2f}
  Ending Balance: ${balance:,.2f}
  Average Daily Balance: ${avg_balance:,.2f}
  Overdraft Incidents: 0
  Returned Checks: 0
"""

BANK_STATEMENT_RISKY = """ACCOUNT STATEMENT
Bank of America | Account: ****{account_last4}
Period: {start_date} - {end_date}
Balance: ${balance:,.2f}

Transactions:
{date}  DEPOSIT           ${deposit_1:,.2f}    Payroll - {employer}
{date2} OVERDRAFT FEE     $35.00              Insufficient Funds
{date3} WITHDRAWAL        ${withdrawal_1:,.2f}   Mortgage Payment
{date4} RETURNED CHECK    ${returned_amt:,.2f}   Check #{check_num}
{date5} OVERDRAFT FEE     $35.00              Insufficient Funds
{date6} DEPOSIT           ${deposit_2:,.2f}    Payroll - {employer}

Summary:
  Total Deposits: ${total_deposits:,.2f}
  Total Withdrawals: ${total_withdrawals:,.2f}
  Ending Balance: ${balance:,.2f}
  Overdraft Incidents: 2
  Returned Checks: 1
  Delinquent Status: {delinquent_days} days past due on account
"""

TAX_RETURN_CLEAN = """INTERNAL REVENUE SERVICE — FORM 1040
Tax Year: {tax_year}
Filer: {full_name}
SSN: ***-**-{ssn_last4}

Adjusted Gross Income: ${agi:,.2f}
Total Tax: ${total_tax:,.2f}
Refund: ${refund:,.2f}

W-2 Income: ${w2_income:,.2f}
Interest Income: ${interest:,.2f}
Dividend Income: ${dividends:,.2f}

Deductions:
  Standard Deduction: ${standard_ded:,.2f}
  Mortgage Interest: ${mortgage_interest:,.2f}
  Charitable Contributions: ${charity:,.2f}

Filing Status: {filing_status}
Dependents: {dependents}
"""

TAX_RETURN_RISKY = """INTERNAL REVENUE SERVICE — FORM 1040
Tax Year: {tax_year}
Filer: {full_name}
SSN: ***-**-{ssn_last4}

Adjusted Gross Income: ${agi:,.2f}
Total Tax: ${total_tax:,.2f}
Amount Owed: ${amount_owed:,.2f}

W-2 Income: ${w2_income:,.2f}
Self-Employment Income: ${self_emp:,.2f}
Unreported Income Flag: YES — estimated {unreported_pct}% unreported

Deductions:
  Standard Deduction: ${standard_ded:,.2f}
  Default Notice: Payment delinquent by {delinquent_days} days

Filing Status: {filing_status}
Dependents: {dependents}
Note: Prior year tax lien of ${lien_amount:,.2f} outstanding
"""

ID_DOCUMENT = """STATE DRIVER LICENSE / IDENTIFICATION CARD
State: {state}
License #: {license_num}
Full Name: {full_name}
Date of Birth: {dob}
Address: {address}
Issue Date: {issue_date}
Expiration Date: {exp_date}
Class: {dl_class}
Restrictions: {restrictions}
Organ Donor: {organ_donor}
Veteran: {veteran}
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SyntheticApplicant:
    full_name: str
    date_of_birth: str
    email: str
    phone: str
    address: str
    occupation: str
    annual_income: float
    risk_profile: str  # low | medium | high


@dataclass
class SyntheticPolicy:
    policy_number: str
    policy_holder: str
    status: str
    coverage_amount: float
    premium: float
    verified: bool


@dataclass
class SyntheticDocument:
    applicant_name: str
    doc_type: str  # bank_statement | tax_return | id
    content: str
    is_risky: bool = False


@dataclass
class SyntheticFraudScenario:
    """A scenario that should trigger fraud flags."""
    applicant: SyntheticApplicant
    transcript: str
    expected_flags: list[str]


@dataclass
class SyntheticDataset:
    applicants: list[SyntheticApplicant] = field(default_factory=list)
    policies: list[SyntheticPolicy] = field(default_factory=list)
    documents: list[SyntheticDocument] = field(default_factory=list)
    fraud_scenarios: list[SyntheticFraudScenario] = field(default_factory=list)
    sample_transcripts: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generator functions
# ---------------------------------------------------------------------------


def _random_date(start_year: int, end_year: int) -> date:
    """Generate a random date between start_year and end_year."""
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=_rng.randint(0, delta))


def _random_phone() -> str:
    area = _rng.randint(200, 999)
    exch = _rng.randint(200, 999)
    line = _rng.randint(1000, 9999)
    return f"{area}-{exch}-{line}"


def _random_address() -> str:
    num = _rng.randint(100, 9999)
    street = _rng.choice(STREETS)
    suffix = _rng.choice(["St", "Ave", "Blvd", "Dr", "Ln", "Way", "Ct"])
    city, state = _rng.choice(CITIES)
    zip_code = _rng.randint(10000, 99999)
    return f"{num} {street} {suffix}, {city}, {state} {zip_code}"


def _random_policy_number(prefix: str | None = None) -> str:
    prefix = prefix or _rng.choice(POLICY_PREFIXES)
    num = _rng.randint(1001, 9999)
    return f"{prefix}-{num}"


def _generate_applicant(risk_profile: str | None = None) -> SyntheticApplicant:
    """Generate a single synthetic applicant with a given risk profile."""
    first = _rng.choice(FIRST_NAMES)
    last = _rng.choice(LAST_NAMES)
    full_name = f"{first} {last}"

    if risk_profile is None:
        profiles = list(RISK_PROFILES.keys())
        weights = [RISK_PROFILES[p]["weight"] for p in profiles]
        risk_profile = _rng.choices(profiles, weights=weights)[0]

    profile = RISK_PROFILES[risk_profile]

    # Age range varies by risk profile
    if risk_profile == "low":
        dob = _random_date(1975, 1995)
    elif risk_profile == "medium":
        dob = _random_date(1965, 1998)
    else:
        dob = _random_date(1955, 2000)

    income = round(_rng.uniform(*profile["income_range"]), -2)  # round to nearest 100

    # Pick occupation — bias toward the profile's list
    if _rng.random() < 0.7:
        occupation = _rng.choice(profile["occupation_bias"])
    else:
        occupation = _rng.choice(OCCUPATIONS)

    email = f"{first.lower()}.{last.lower()}@email.com"
    phone = _random_phone()
    address = _random_address()

    return SyntheticApplicant(
        full_name=full_name,
        date_of_birth=dob.isoformat(),
        email=email,
        phone=phone,
        address=address,
        occupation=occupation,
        annual_income=income,
        risk_profile=risk_profile,
    )


def _generate_policy(applicant: SyntheticApplicant) -> SyntheticPolicy:
    """Generate a policy matching the applicant's risk profile."""
    profile = RISK_PROFILES[applicant.risk_profile]
    coverage = round(_rng.uniform(*profile["coverage_range"]), -3)
    premium = round(_rng.uniform(*profile["premium_range"]), -2)

    # High-risk applicants sometimes have lapsed policies
    if applicant.risk_profile == "high" and _rng.random() < 0.3:
        status = "lapsed"
        verified = False
    else:
        status = "active"
        verified = True

    return SyntheticPolicy(
        policy_number=_random_policy_number(),
        policy_holder=applicant.full_name,
        status=status,
        coverage_amount=coverage,
        premium=premium,
        verified=verified,
    )


def _generate_documents(applicant: SyntheticApplicant, is_risky: bool = False) -> list[SyntheticDocument]:
    """Generate supporting documents for an applicant."""
    docs: list[SyntheticDocument] = []
    today = date.today()
    ssn_last4 = _rng.randint(1000, 9999)
    account_last4 = _rng.randint(1000, 9999)

    # --- Bank statement ---
    start_date = today - timedelta(days=_rng.randint(60, 90))
    end_date = start_date + timedelta(days=30)
    employer = applicant.occupation if applicant.occupation else "Employer"

    if is_risky:
        content = BANK_STATEMENT_RISKY.format(
            account_last4=account_last4,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            balance=_rng.randint(100, 2000),
            date=(start_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            date2=(start_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            date3=(start_date + timedelta(days=10)).strftime("%Y-%m-%d"),
            date4=(start_date + timedelta(days=15)).strftime("%Y-%m-%d"),
            date5=(start_date + timedelta(days=20)).strftime("%Y-%m-%d"),
            date6=(start_date + timedelta(days=25)).strftime("%Y-%m-%d"),
            deposit_1=applicant.annual_income / 26,
            deposit_2=applicant.annual_income / 26,
            withdrawal_1=_rng.randint(1000, 3000),
            returned_amt=_rng.randint(200, 800),
            check_num=_rng.randint(1000, 9999),
            total_deposits=applicant.annual_income / 12,
            total_withdrawals=applicant.annual_income / 12 * 1.1,
            avg_balance=_rng.randint(500, 3000),
            employer=employer,
            delinquent_days=_rng.randint(30, 90),
        )
    else:
        balance = _rng.randint(5000, 50000)
        content = BANK_STATEMENT_CLEAN.format(
            account_last4=account_last4,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            balance=balance,
            date=(start_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            date2=(start_date + timedelta(days=3)).strftime("%Y-%m-%d"),
            date3=(start_date + timedelta(days=10)).strftime("%Y-%m-%d"),
            date4=(start_date + timedelta(days=15)).strftime("%Y-%m-%d"),
            date5=(start_date + timedelta(days=22)).strftime("%Y-%m-%d"),
            deposit_1=applicant.annual_income / 26,
            deposit_2=applicant.annual_income / 26,
            deposit_3=applicant.annual_income / 26,
            withdrawal_1=_rng.randint(1500, 4000),
            withdrawal_2=_rng.randint(200, 600),
            total_deposits=applicant.annual_income / 12 * 3,
            total_withdrawals=applicant.annual_income / 12 * 2.5,
            avg_balance=balance * 0.8,
            employer=employer,
        )

    docs.append(SyntheticDocument(
        applicant_name=applicant.full_name,
        doc_type="bank_statement",
        content=content,
        is_risky=is_risky,
    ))

    # --- Tax return ---
    tax_year = today.year - 1
    agi = applicant.annual_income

    if is_risky:
        content = TAX_RETURN_RISKY.format(
            tax_year=tax_year,
            full_name=applicant.full_name,
            ssn_last4=ssn_last4,
            agi=agi,
            total_tax=agi * _rng.uniform(0.1, 0.2),
            amount_owed=_rng.randint(2000, 10000),
            w2_income=agi * 0.7,
            self_emp=agi * 0.3,
            unreported_pct=_rng.randint(10, 30),
            standard_ded=_rng.choice([13850, 27700, 20800]),
            delinquent_days=_rng.randint(30, 180),
            filing_status=_rng.choice(["Single", "Married Filing Jointly", "Head of Household"]),
            dependents=_rng.randint(0, 3),
            lien_amount=_rng.randint(5000, 50000),
        )
    else:
        content = TAX_RETURN_CLEAN.format(
            tax_year=tax_year,
            full_name=applicant.full_name,
            ssn_last4=ssn_last4,
            agi=agi,
            total_tax=agi * _rng.uniform(0.12, 0.22),
            refund=_rng.randint(500, 5000),
            w2_income=agi,
            interest=_rng.randint(100, 2000),
            dividends=_rng.randint(100, 3000),
            standard_ded=_rng.choice([13850, 27700, 20800]),
            mortgage_interest=_rng.randint(5000, 15000),
            charity=_rng.randint(500, 5000),
            filing_status=_rng.choice(["Single", "Married Filing Jointly", "Head of Household"]),
            dependents=_rng.randint(0, 3),
        )

    docs.append(SyntheticDocument(
        applicant_name=applicant.full_name,
        doc_type="tax_return",
        content=content,
        is_risky=is_risky,
    ))

    # --- ID document ---
    state = _rng.choice([c[0] for c in CITIES])
    dob = date.fromisoformat(applicant.date_of_birth)
    exp_date = date(dob.year + 40 + _rng.randint(0, 5), dob.month, dob.day)
    content = ID_DOCUMENT.format(
        state=state,
        license_num=f"{state[:2].upper()}{_rng.randint(1000000, 9999999)}",
        full_name=applicant.full_name,
        dob=applicant.date_of_birth,
        address=applicant.address,
        issue_date=(today - timedelta(days=_rng.randint(30, 365))).strftime("%Y-%m-%d"),
        exp_date=exp_date.strftime("%Y-%m-%d"),
        dl_class=_rng.choice(["D", "C", "A", "B"]),
        restrictions=_rng.choice(["None", "Corrective Lenses", "Daylight Only"]),
        organ_donor=_rng.choice(["Yes", "No"]),
        veteran=_rng.choice(["Yes", "No"]),
    )

    docs.append(SyntheticDocument(
        applicant_name=applicant.full_name,
        doc_type="id",
        content=content,
        is_risky=False,
    ))

    return docs


def _generate_transcript(applicant: SyntheticApplicant, policy: SyntheticPolicy) -> str:
    """Generate a realistic spoken transcript for an applicant."""
    parts = [
        f"My name is {applicant.full_name},",
        f"born {applicant.date_of_birth},",
        f"policy {policy.policy_number},",
        f"coverage {int(policy.coverage_amount)},",
        f"income {int(applicant.annual_income)}",
    ]
    return " ".join(parts)


def _generate_fraud_transcript(applicant: SyntheticApplicant) -> str:
    """Generate a transcript that should trigger fraud flags."""
    templates = [
        f"I need guaranteed approval, no questions asked. My name is {applicant.full_name}, "
        f"born {applicant.date_of_birth}, I applied before and was denied. "
        f"I really need this as soon as possible.",
        f"This is my second application. My name is {applicant.full_name}, "
        f"I need cash only, no questions. I'm willing to pay under the table.",
        f"I'm reapplying. My name is {applicant.full_name}, "
        f"born {applicant.date_of_birth}. I need urgent approval, "
        f"multiple applications have been submitted.",
    ]
    return _rng.choice(templates)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_dataset(
    num_applicants: int = 20,
    num_fraud_scenarios: int = 3,
    seed: int = _SEED,
) -> SyntheticDataset:
    """Generate a complete synthetic dataset.

    Args:
        num_applicants: How many applicants to generate.
        num_fraud_scenarios: How many fraud scenarios to include.
        seed: RNG seed for reproducibility.

    Returns:
        A SyntheticDataset with applicants, policies, documents, and transcripts.
    """
    global _rng
    _rng = random.Random(seed)

    dataset = SyntheticDataset()

    for _ in range(num_applicants):
        applicant = _generate_applicant()
        policy = _generate_policy(applicant)
        is_risky = applicant.risk_profile == "high" and _rng.random() < 0.5
        docs = _generate_documents(applicant, is_risky=is_risky)

        dataset.applicants.append(applicant)
        dataset.policies.append(policy)
        dataset.documents.extend(docs)

        transcript = _generate_transcript(applicant, policy)
        dataset.sample_transcripts.append({
            "id": f"sample-{len(dataset.sample_transcripts) + 1}",
            "name": applicant.full_name,
            "description": f"{applicant.risk_profile.capitalize()} risk — {applicant.occupation}",
            "expected_outcome": "accept" if applicant.risk_profile == "low" else "review",
            "transcript": transcript,
        })

    # Generate fraud scenarios
    for _ in range(num_fraud_scenarios):
        applicant = _generate_applicant(risk_profile="high")
        transcript = _generate_fraud_transcript(applicant)
        dataset.fraud_scenarios.append(SyntheticFraudScenario(
            applicant=applicant,
            transcript=transcript,
            expected_flags=["high-risk keyword", "velocity signal"],
        ))

    return dataset


def dataset_to_db_seed(dataset: SyntheticDataset) -> dict[str, Any]:
    """Convert a synthetic dataset to DB seed data format.

    Returns a dict with keys: policies, applicants, documents, fraud_rules.
    """
    policies = []
    for p in dataset.policies:
        policies.append({
            "policy_number": p.policy_number,
            "policy_holder": p.policy_holder,
            "status": p.status,
            "coverage_amount": p.coverage_amount,
            "premium": p.premium,
            "verified": 1 if p.verified else 0,
        })

    applicants = []
    for a in dataset.applicants:
        applicants.append({
            "full_name": a.full_name,
            "date_of_birth": a.date_of_birth,
            "email": a.email,
            "phone": a.phone,
            "address": a.address,
            "occupation": a.occupation,
            "annual_income": a.annual_income,
        })

    documents = []
    for d in dataset.documents:
        documents.append({
            "applicant_name": d.applicant_name,
            "doc_type": d.doc_type,
            "content": d.content,
            "is_risky": d.is_risky,
        })

    return {
        "policies": policies,
        "applicants": applicants,
        "documents": documents,
        "fraud_rules": [
            {"rule_type": "velocity", "description": "Multiple applications within a short window", "severity": "high"},
            {"rule_type": "mismatch", "description": "Applicant details differ from known records", "severity": "high"},
            {"rule_type": "keyword", "description": "High-risk keywords in transcript or documents", "severity": "medium"},
            {"rule_type": "income", "description": "Reported income inconsistent with occupation", "severity": "medium"},
        ],
    }


def print_summary(dataset: SyntheticDataset) -> None:
    """Print a human-readable summary of the generated dataset."""
    print("=" * 60)
    print("SYNTHETIC DATASET SUMMARY")
    print("=" * 60)
    print(f"  Applicants:       {len(dataset.applicants)}")
    print(f"  Policies:         {len(dataset.policies)}")
    print(f"  Documents:        {len(dataset.documents)}")
    print(f"  Fraud scenarios:  {len(dataset.fraud_scenarios)}")
    print(f"  Sample transcripts: {len(dataset.sample_transcripts)}")
    print()

    # Risk profile breakdown
    profiles: dict[str, int] = {}
    for a in dataset.applicants:
        profiles[a.risk_profile] = profiles.get(a.risk_profile, 0) + 1
    print("Risk Profile Breakdown:")
    for profile, count in sorted(profiles.items()):
        print(f"  {profile}: {count}")
    print()

    # Sample applicants
    print("Sample Applicants:")
    for a in dataset.applicants[:5]:
        print(f"  {a.full_name:25s} | {a.occupation:25s} | ${a.annual_income:>8,.0f} | {a.risk_profile}")
    if len(dataset.applicants) > 5:
        print(f"  ... and {len(dataset.applicants) - 5} more")
    print()

    # Fraud scenarios
    print("Fraud Scenarios:")
    for i, fs in enumerate(dataset.fraud_scenarios, 1):
        print(f"  {i}. {fs.applicant.full_name}")
        print(f"     Transcript: {fs.transcript[:80]}...")
        print(f"     Expected flags: {', '.join(fs.expected_flags)}")
    print()

    # Sample transcripts
    print("Sample Transcripts (for frontend):")
    for st in dataset.sample_transcripts[:3]:
        print(f"  [{st['id']}] {st['name']:25s} | {st['description']}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate and display the synthetic dataset."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic data for Live Underwriter")
    parser.add_argument("--count", type=int, default=20, help="Number of applicants to generate")
    parser.add_argument("--fraud", type=int, default=3, help="Number of fraud scenarios")
    parser.add_argument("--seed", type=int, default=_SEED, help="RNG seed")
    parser.add_argument("--seed-db", action="store_true", help="Seed the SQLite database with generated data")
    parser.add_argument("--json", type=str, help="Export dataset to a JSON file")
    args = parser.parse_args()

    dataset = generate_dataset(
        num_applicants=args.count,
        num_fraud_scenarios=args.fraud,
        seed=args.seed,
    )

    print_summary(dataset)

    if args.json:
        data = dataset_to_db_seed(dataset)
        with open(args.json, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Dataset exported to {args.json}")

    if args.seed_db:
        _seed_db_from_dataset(dataset)
        print("Database seeded with synthetic data.")


def _seed_db_from_dataset(dataset: SyntheticDataset) -> None:
    """Seed the live_underwriter DB from a synthetic dataset."""
    from live_underwriter.db import UnderwritingDB

    db = UnderwritingDB()

    for policy in dataset.policies:
        db.upsert_policy({
            "policy_number": policy.policy_number,
            "policy_holder": policy.policy_holder,
            "status": policy.status,
            "coverage_amount": policy.coverage_amount,
            "premium": policy.premium,
            "verified": 1 if policy.verified else 0,
        })

    for applicant in dataset.applicants:
        existing = db.get_applicant(applicant.full_name)
        if existing is None:
            db._conn.execute(
                """
                INSERT INTO applicants (full_name, date_of_birth, email, phone, address, occupation, annual_income)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (applicant.full_name, applicant.date_of_birth, applicant.email,
                 applicant.phone, applicant.address, applicant.occupation, applicant.annual_income),
            )

    # Seed documents
    existing_docs = db._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if existing_docs == 0:
        for doc in dataset.documents:
            applicant_row = db.get_applicant(doc.applicant_name)
            if applicant_row:
                db._conn.execute(
                    "INSERT INTO documents (applicant_id, doc_type, content) VALUES (?, ?, ?)",
                    (applicant_row["id"], doc.doc_type, doc.content),
                )

    # Seed fraud rules
    if not db.get_fraud_rules():
        rules = [
            ("velocity", "Multiple applications within a short window", "high"),
            ("mismatch", "Applicant details differ from known records", "high"),
            ("keyword", "High-risk keywords in transcript or documents", "medium"),
            ("income", "Reported income inconsistent with occupation", "medium"),
        ]
        db._conn.executemany(
            "INSERT INTO fraud_rules (rule_type, description, severity) VALUES (?, ?, ?)",
            rules,
        )

    db._conn.commit()
    db.close()


if __name__ == "__main__":
    main()
