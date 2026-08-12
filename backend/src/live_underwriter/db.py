"""SQLite persistence layer with a repository pattern.

The repository pattern isolates SQL from the rest of the app so a real
database (Postgres, etc.) can replace SQLite later without touching agents.

Tables:
    policies    — verified policy/account records (the verification source).
    applicants  — known applicant records (for fraud mismatch checks).
    fraud_rules — red-flag heuristics (velocity, keywords, patterns).
    documents   — sample supporting documents for document_review.
    audit_log   — append-only audit trail of every decision step.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "underwriting.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    policy_number   TEXT PRIMARY KEY,
    policy_holder   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    coverage_amount REAL NOT NULL DEFAULT 0,
    premium         REAL NOT NULL DEFAULT 0,
    verified        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS applicants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    date_of_birth TEXT,
    email       TEXT,
    phone       TEXT,
    address     TEXT,
    occupation  TEXT,
    annual_income REAL
);

CREATE TABLE IF NOT EXISTS fraud_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type   TEXT NOT NULL,      -- velocity | mismatch | keyword
    description TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'medium'  -- low | medium | high
);

CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id INTEGER,
    doc_type    TEXT NOT NULL,      -- bank_statement | tax_return | id
    content     TEXT NOT NULL,
    FOREIGN KEY (applicant_id) REFERENCES applicants(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       TEXT NOT NULL,
    detail      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name  TEXT NOT NULL,
    policy_number   TEXT,
    risk_score      REAL NOT NULL DEFAULT 0,
    risk_level      TEXT NOT NULL DEFAULT 'low',
    ai_decision     TEXT NOT NULL,          -- accept | decline | review
    rationale       TEXT NOT NULL DEFAULT '',
    flags           TEXT NOT NULL DEFAULT '',  -- JSON list of flags
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | declined
    reviewer_note   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at     TEXT
);
"""


class UnderwritingDB:
    """Thin repository over the SQLite database."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        logger.info("DB connected: %s", self.db_path)

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- policies ----
    def get_policy(self, policy_number: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM policies WHERE policy_number = ?", (policy_number,)
        ).fetchone()
        return dict(row) if row else None

    def get_policy_by_suffix(self, suffix: str) -> dict[str, Any] | None:
        """Look up a policy by its numeric suffix (e.g. '1001' -> POL-1001).

        Handles the case where the LLM/STT drops the alphanumeric prefix and
        only returns the digits (e.g. '1001' instead of 'POL-1001').
        """
        row = self._conn.execute(
            "SELECT * FROM policies WHERE policy_number LIKE ?",
            (f"%-{suffix}",),
        ).fetchone()
        return dict(row) if row else None

    def upsert_policy(self, policy: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO policies (policy_number, policy_holder, status, coverage_amount, premium, verified)
            VALUES (:policy_number, :policy_holder, :status, :coverage_amount, :premium, :verified)
            ON CONFLICT(policy_number) DO UPDATE SET
                policy_holder=excluded.policy_holder,
                status=excluded.status,
                coverage_amount=excluded.coverage_amount,
                premium=excluded.premium,
                verified=excluded.verified
            """,
            policy,
        )
        self._conn.commit()

    # ---- applicants ----
    def get_applicant(self, full_name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM applicants WHERE full_name = ?", (full_name,)
        ).fetchone()
        return dict(row) if row else None

    # ---- fraud rules ----
    def get_fraud_rules(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM fraud_rules").fetchall()
        return [dict(r) for r in rows]

    # ---- documents ----
    def get_documents_for_applicant(self, applicant_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE applicant_id = ?", (applicant_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- audit trail ----
    def append_audit(self, stage: str, detail: str) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (stage, detail) VALUES (?, ?)", (stage, detail)
        )
        self._conn.commit()

    def get_audit_trail(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM audit_log ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- human-in-the-loop reviews ----
    def create_review(self, review: dict[str, Any]) -> int:
        """Create a review record for a flagged case. Returns the review id."""
        cur = self._conn.execute(
            """
            INSERT INTO reviews (applicant_name, policy_number, risk_score, risk_level,
                                 ai_decision, rationale, flags)
            VALUES (:applicant_name, :policy_number, :risk_score, :risk_level,
                    :ai_decision, :rationale, :flags)
            """,
            review,
        )
        self._conn.commit()
        lastrowid = cur.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create review: no row id returned")
        return int(lastrowid)

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM reviews WHERE status = 'pending' ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_reviews(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM reviews ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_review(self, review_id: int, status: str, reviewer_note: str | None = None) -> bool:
        """Approve or decline a review. Returns True if updated."""
        cur = self._conn.execute(
            """
            UPDATE reviews
            SET status = ?, reviewer_note = ?, reviewed_at = datetime('now')
            WHERE id = ? AND status = 'pending'
            """,
            (status, reviewer_note, review_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()


def seed_database(db: UnderwritingDB) -> None:
    """Populate the DB with realistic mock data (idempotent)."""
    db.upsert_policy(
        {
            "policy_number": "POL-1001",
            "policy_holder": "Jane Doe",
            "status": "active",
            "coverage_amount": 500000.0,
            "premium": 1200.0,
            "verified": 1,
        }
    )
    db.upsert_policy(
        {
            "policy_number": "POL-1002",
            "policy_holder": "John Smith",
            "status": "active",
            "coverage_amount": 250000.0,
            "premium": 800.0,
            "verified": 1,
        }
    )
    db.upsert_policy(
        {
            "policy_number": "POL-9999",
            "policy_holder": "Unknown Person",
            "status": "lapsed",
            "coverage_amount": 0.0,
            "premium": 0.0,
            "verified": 0,
        }
    )
    # Additional policies for the 3 test applicants.
    db.upsert_policy(
        {
            "policy_number": "POL-2001",
            "policy_holder": "Alice Johnson",
            "status": "active",
            "coverage_amount": 250000.0,
            "premium": 900.0,
            "verified": 1,
        }
    )
    db.upsert_policy(
        {
            "policy_number": "POL-2002",
            "policy_holder": "Robert Chen",
            "status": "active",
            "coverage_amount": 1000000.0,
            "premium": 4500.0,
            "verified": 1,
        }
    )
    db.upsert_policy(
        {
            "policy_number": "POL-2003",
            "policy_holder": "Maria Garcia",
            "status": "active",
            "coverage_amount": 150000.0,
            "premium": 600.0,
            "verified": 1,
        }
    )

    # Known applicant (for fraud mismatch checks)
    if db.get_applicant("Jane Doe") is None:
        db._conn.execute(
            """
            INSERT INTO applicants (full_name, date_of_birth, email, phone, address, occupation, annual_income)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("Jane Doe", "1985-04-12", "jane.doe@example.com", "555-0100",
             "123 Main St, Springfield", "Software Engineer", 120000.0),
        )
        db._conn.commit()

    # Second known applicant (for document review + fraud checks)
    if db.get_applicant("John Smith") is None:
        db._conn.execute(
            """
            INSERT INTO applicants (full_name, date_of_birth, email, phone, address, occupation, annual_income)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("John Smith", "1978-09-30", "john.smith@example.com", "555-0200",
             "456 Oak Ave, Riverton", "Business Owner", 90000.0),
        )
        db._conn.commit()

    # Three more applicants with filled documents for underwriting testing.
    _seed_extra_applicants(db)

    # Mock supporting documents (realistic content).
    _seed_documents(db)

    # Fraud rules
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

    logger.info("Database seeded with mock data")


def _seed_documents(db: UnderwritingDB) -> None:
    """Seed realistic mock documents for known applicants (idempotent)."""
    # Skip if documents already exist for any applicant.
    existing = db._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if existing:
        logger.info("Documents already seeded (%d rows), skipping", existing)
        return

    jane = db.get_applicant("Jane Doe")
    john = db.get_applicant("John Smith")
    alice = db.get_applicant("Alice Johnson")
    robert = db.get_applicant("Robert Chen")
    maria = db.get_applicant("Maria Garcia")

    docs = []
    if jane:
        docs.extend(
            [
                {
                    "applicant_id": jane["id"],
                    "doc_type": "bank_statement",
                    "content": (
                        "First National Bank — Monthly Statement — Jane Doe. "
                        "Opening balance $12,400.00. Deposits $8,200.00. "
                        "Ending balance $20,600.00. Account in good standing."
                    ),
                },
                {
                    "applicant_id": jane["id"],
                    "doc_type": "tax_return",
                    "content": (
                        "2025 Federal Tax Return — Jane Doe. Adjusted gross income "
                        "$118,000.00. Filing status: single. No delinquent accounts."
                    ),
                },
                {
                    "applicant_id": jane["id"],
                    "doc_type": "id",
                    "content": (
                        "State Driver License — Jane Doe, DOB 1985-04-12, "
                        "Address 123 Main St, Springfield. Valid."
                    ),
                },
            ]
        )
    if john:
        docs.extend(
            [
                {
                    "applicant_id": john["id"],
                    "doc_type": "bank_statement",
                    "content": (
                        "Riverton Credit Union — Monthly Statement — John Smith. "
                        "Opening balance $3,100.00. One overdraft of $240.00 this "
                        "period. Insufficient funds notice issued on the 14th."
                    ),
                },
                {
                    "applicant_id": john["id"],
                    "doc_type": "tax_return",
                    "content": (
                        "2025 Federal Tax Return — John Smith. Adjusted gross income "
                        "$88,000.00. Filing status: married. Prior year had a "
                        "delinquent balance that was paid."
                    ),
                },
            ]
        )
    if alice:
        docs.extend(
            [
                {
                    "applicant_id": alice["id"],
                    "doc_type": "bank_statement",
                    "content": (
                        "Lakeview Community Bank — Monthly Statement — Alice Johnson. "
                        "Opening balance $8,900.00. Deposits $4,500.00. "
                        "Ending balance $13,400.00. Account in good standing, no overdrafts."
                    ),
                },
                {
                    "applicant_id": alice["id"],
                    "doc_type": "tax_return",
                    "content": (
                        "2025 Federal Tax Return — Alice Johnson. Adjusted gross income "
                        "$64,000.00. Filing status: single. No delinquent accounts, "
                        "no defaults."
                    ),
                },
                {
                    "applicant_id": alice["id"],
                    "doc_type": "id",
                    "content": (
                        "State Driver License — Alice Johnson, DOB 1990-03-03, "
                        "Address 789 Pine St, Lakeview. Valid."
                    ),
                },
            ]
        )
    if robert:
        docs.extend(
            [
                {
                    "applicant_id": robert["id"],
                    "doc_type": "bank_statement",
                    "content": (
                        "Hillcrest National Bank — Monthly Statement — Robert Chen. "
                        "Opening balance $45,000.00. Deposits $25,000.00. "
                        "Ending balance $70,000.00. Account in good standing."
                    ),
                },
                {
                    "applicant_id": robert["id"],
                    "doc_type": "tax_return",
                    "content": (
                        "2025 Federal Tax Return — Robert Chen. Adjusted gross income "
                        "$295,000.00. Filing status: married. No delinquent accounts."
                    ),
                },
                {
                    "applicant_id": robert["id"],
                    "doc_type": "id",
                    "content": (
                        "State Driver License — Robert Chen, DOB 1975-11-20, "
                        "Address 1010 Maple Dr, Hillcrest. Valid."
                    ),
                },
            ]
        )
    if maria:
        docs.extend(
            [
                {
                    "applicant_id": maria["id"],
                    "doc_type": "bank_statement",
                    "content": (
                        "Brookfield Savings — Monthly Statement — Maria Garcia. "
                        "Opening balance $1,200.00. Two overdrafts this period "
                        "totaling $180.00. Insufficient funds notice issued on "
                        "the 3rd and 19th."
                    ),
                },
                {
                    "applicant_id": maria["id"],
                    "doc_type": "tax_return",
                    "content": (
                        "2025 Federal Tax Return — Maria Garcia. Adjusted gross income "
                        "$42,000.00. Filing status: single. Prior year had a "
                        "delinquent balance and a default on a personal loan."
                    ),
                },
            ]
        )

    for doc in docs:
        db._conn.execute(
            "INSERT INTO documents (applicant_id, doc_type, content) VALUES (?, ?, ?)",
            (doc["applicant_id"], doc["doc_type"], doc["content"]),
        )
    db._conn.commit()
    logger.info("Seeded %d mock documents", len(docs))


def _seed_extra_applicants(db: UnderwritingDB) -> None:
    """Seed 3 more applicants with filled documents for underwriting testing.

    Each has a distinct risk profile so the document review + risk scoring
    can be exercised:
      - Alice Johnson: clean, low risk.
      - Robert Chen: high coverage, high premium -> high risk.
      - Maria Garcia: overdraft + delinquent -> flagged by document review.
    """
    extras: list[dict[str, Any]] = [
        {
            "full_name": "Alice Johnson",
            "date_of_birth": "1990-03-03",
            "email": "alice.johnson@example.com",
            "phone": "555-0300",
            "address": "789 Pine St, Lakeview",
            "occupation": "Teacher",
            "annual_income": 65000.0,
        },
        {
            "full_name": "Robert Chen",
            "date_of_birth": "1975-11-20",
            "email": "robert.chen@example.com",
            "phone": "555-0400",
            "address": "1010 Maple Dr, Hillcrest",
            "occupation": "Surgeon",
            "annual_income": 300000.0,
        },
        {
            "full_name": "Maria Garcia",
            "date_of_birth": "1988-07-15",
            "email": "maria.garcia@example.com",
            "phone": "555-0500",
            "address": "2020 Cedar Ln, Brookfield",
            "occupation": "Retail Manager",
            "annual_income": 45000.0,
        },
    ]
    for a in extras:
        if db.get_applicant(a["full_name"]) is None:
            db._conn.execute(
                """
                INSERT INTO applicants (full_name, date_of_birth, email, phone, address, occupation, annual_income)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (a["full_name"], a["date_of_birth"], a["email"], a["phone"],
                 a["address"], a["occupation"], a["annual_income"]),
            )
    db._conn.commit()
    logger.info("Seeded 3 extra applicants")
