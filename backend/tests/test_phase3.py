"""Tests for Phase 3: fraud check, document review, and voice tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from live_underwriter.agents import document_review_node, fraud_check_node
from live_underwriter.agents.document_review import set_db_for_tests as set_doc_db
from live_underwriter.agents.fraud_check import set_db_for_tests as set_fraud_db
from live_underwriter.db import UnderwritingDB, seed_database
from live_underwriter.state import ApplicantInfo, UnderwritingState


@pytest.fixture()
def db(tmp_path: Path) -> UnderwritingDB:
    d = UnderwritingDB(tmp_path / "test.db")
    seed_database(d)
    set_fraud_db(d)
    set_doc_db(d)
    yield d
    set_fraud_db(None)
    set_doc_db(None)
    d.close()


def _state(**kwargs) -> UnderwritingState:
    return UnderwritingState(**kwargs)


# ---- fraud_check ----
def test_fraud_keyword_flag() -> None:
    state = _state(transcript="I want guaranteed approval, no questions asked")
    out = fraud_check_node(state)
    assert out["stage"] == "fraud_check"
    assert out["audit_trail"][-1].outcome == "warn"
    assert any("keyword" in f for f in out["risk"].flags)


def test_fraud_no_flags(db: UnderwritingDB) -> None:
    state = _state(transcript="My name is Jane Doe, policy POL-1001")
    out = fraud_check_node(state)
    assert out["audit_trail"][-1].outcome == "ok"


def test_fraud_dob_mismatch(db: UnderwritingDB) -> None:
    # Known applicant Jane Doe has DOB 1985-04-12; provide a different one.
    state = _state(
        transcript="Jane Doe",
        applicant=ApplicantInfo(full_name="Jane Doe", date_of_birth="1990-01-01"),
    )
    out = fraud_check_node(state)
    assert any("DOB mismatch" in f for f in out["risk"].flags)


# ---- document_review ----
def test_document_review_no_docs(db: UnderwritingDB) -> None:
    # An applicant with no known records should have no document findings.
    state = _state(applicant=ApplicantInfo(full_name="Nobody Known"))
    out = document_review_node(state)
    assert out["stage"] == "document_review"
    assert out["audit_trail"][-1].outcome == "ok"


def test_document_review_clean_docs(db: UnderwritingDB) -> None:
    # Jane Doe has clean seeded documents (no risk keywords).
    state = _state(applicant=ApplicantInfo(full_name="Jane Doe"))
    out = document_review_node(state)
    assert out["stage"] == "document_review"
    assert out["audit_trail"][-1].outcome == "ok"


def test_document_review_risk_keyword(db: UnderwritingDB) -> None:
    # John Smith's seeded bank statement contains an overdraft (risk keyword).
    state = _state(applicant=ApplicantInfo(full_name="John Smith"))
    out = document_review_node(state)
    assert out["audit_trail"][-1].outcome == "warn"
    assert any("overdraft" in f for f in out["risk"].flags)


def test_document_review_alice_clean(db: UnderwritingDB) -> None:
    """Alice Johnson has clean documents -> no flags."""
    state = _state(applicant=ApplicantInfo(full_name="Alice Johnson"))
    out = document_review_node(state)
    assert out["audit_trail"][-1].outcome == "ok"


def test_document_review_robert_clean(db: UnderwritingDB) -> None:
    """Robert Chen has clean documents -> no flags (high risk comes from coverage)."""
    state = _state(applicant=ApplicantInfo(full_name="Robert Chen"))
    out = document_review_node(state)
    assert out["audit_trail"][-1].outcome == "ok"


def test_document_review_maria_flagged(db: UnderwritingDB) -> None:
    """Maria Garcia has overdrafts + delinquent + default -> flagged."""
    state = _state(applicant=ApplicantInfo(full_name="Maria Garcia"))
    out = document_review_node(state)
    assert out["audit_trail"][-1].outcome == "warn"
    flags = " ".join(out["risk"].flags)
    assert "overdraft" in flags
    assert "delinquent" in flags
    assert "default" in flags


# ---- voice tools ----
def test_stt_raises_without_dependency() -> None:
    # Simulate faster-whisper not installed by forcing ImportError.
    import builtins

    from live_underwriter.tools import stt

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("no faster_whisper")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(RuntimeError, match="faster-whisper"):
            stt.transcribe("fake.wav")
    finally:
        builtins.__import__ = real_import


def test_tts_raises_without_dependency() -> None:
    import builtins

    from live_underwriter.tools import tts

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "kokoro":
            raise ImportError("no kokoro")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(RuntimeError, match="kokoro"):
            tts.synthesize("hello", "out.wav")
    finally:
        builtins.__import__ = real_import
