"""Tests for the Phase 1 foundation: logging, LLM config, and DB layer."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from live_underwriter.db import UnderwritingDB, seed_database
from live_underwriter.llm import llm_settings


@pytest.fixture()
def db(tmp_path: Path) -> UnderwritingDB:
    """A fresh, seeded in-memory-ish DB on a temp path."""
    d = UnderwritingDB(tmp_path / "test.db")
    seed_database(d)
    yield d
    d.close()


# ---- logging ----
def test_logging_writes_to_file(tmp_path: Path) -> None:
    from live_underwriter.logging_conf import setup_logging

    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file, force=True)
    logger = logging.getLogger("test.logging")
    logger.info("hello from test")

    assert log_file.exists()
    content = log_file.read_text()
    assert "hello from test" in content


# ---- LLM config ----
def test_llm_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("OLLAMA_BASE_URL", "OLLAMA_API_KEY", "OLLAMA_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = llm_settings()
    assert s["base_url"] == "http://localhost:11434/v1"
    assert s["api_key"] == "ollama"
    assert s["model"] == "qwen2.5"


def test_llm_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example:9999/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "secret")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")
    s = llm_settings()
    assert s["base_url"] == "http://example:9999/v1"
    assert s["api_key"] == "secret"
    assert s["model"] == "llama3.1"


# ---- DB: policies ----
def test_get_policy_found(db: UnderwritingDB) -> None:
    p = db.get_policy("POL-1001")
    assert p is not None
    assert p["policy_holder"] == "Jane Doe"
    assert p["verified"] == 1


def test_get_policy_missing(db: UnderwritingDB) -> None:
    assert db.get_policy("NOPE") is None


def test_upsert_policy_updates(db: UnderwritingDB) -> None:
    db.upsert_policy(
        {
            "policy_number": "POL-1001",
            "policy_holder": "Jane Doe",
            "status": "lapsed",
            "coverage_amount": 0.0,
            "premium": 0.0,
            "verified": 0,
        }
    )
    p = db.get_policy("POL-1001")
    assert p["status"] == "lapsed"
    assert p["verified"] == 0


# ---- DB: applicants / fraud rules / documents ----
def test_get_applicant(db: UnderwritingDB) -> None:
    a = db.get_applicant("Jane Doe")
    assert a is not None
    assert a["annual_income"] == 120000.0


def test_fraud_rules_seeded(db: UnderwritingDB) -> None:
    rules = db.get_fraud_rules()
    assert len(rules) >= 4
    types = {r["rule_type"] for r in rules}
    assert {"velocity", "mismatch", "keyword", "income"} <= types


def test_documents_seeded_for_jane(db: UnderwritingDB) -> None:
    """Mock documents should be seeded for known applicants."""
    jane = db.get_applicant("Jane Doe")
    assert jane is not None
    docs = db.get_documents_for_applicant(int(jane["id"]))
    assert len(docs) >= 3
    types = {d["doc_type"] for d in docs}
    assert {"bank_statement", "tax_return", "id"} <= types


def test_documents_seeded_for_john(db: UnderwritingDB) -> None:
    """John Smith should have a bank statement with a risk keyword (overdraft)."""
    john = db.get_applicant("John Smith")
    assert john is not None
    docs = db.get_documents_for_applicant(int(john["id"]))
    assert len(docs) >= 2
    bank = next(d for d in docs if d["doc_type"] == "bank_statement")
    assert "overdraft" in str(bank["content"]).lower()


# ---- DB: audit trail ----
def test_audit_trail_append_and_read(db: UnderwritingDB) -> None:
    db.append_audit("normalize", "extracted applicant")
    db.append_audit("decision", "accepted")
    trail = db.get_audit_trail()
    assert len(trail) == 2
    assert trail[0]["stage"] == "normalize"
    assert trail[1]["detail"] == "accepted"
