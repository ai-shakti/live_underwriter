"""Tests for Phase 2 core agents: normalize, validate, verify_policy, review, decision."""

from __future__ import annotations

from pathlib import Path

import pytest

from live_underwriter.agents import (
    normalize_node,
    review_node,
    risk_decision_node,
    validate_node,
    verify_policy_node,
)
from live_underwriter.agents.normalize import _parse_applicant
from live_underwriter.agents.verify_policy import set_db_for_tests
from live_underwriter.db import UnderwritingDB, seed_database
from live_underwriter.state import ApplicantInfo, PolicyRecord, UnderwritingState


@pytest.fixture()
def db(tmp_path: Path) -> UnderwritingDB:
    d = UnderwritingDB(tmp_path / "test.db")
    seed_database(d)
    set_db_for_tests(d)
    yield d
    set_db_for_tests(None)
    d.close()


def _state(**kwargs) -> UnderwritingState:
    return UnderwritingState(**kwargs)


# ---- normalize ----
def test_normalize_empty_transcript() -> None:
    state = _state(transcript="")
    out = normalize_node(state)
    assert out["stage"] == "normalize"
    assert out["applicant"].full_name is None
    assert out["audit_trail"][-1].outcome == "warn"


def test_normalize_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLLM:
        def invoke(self, messages):
            return type("R", (), {"content": '{"full_name": "Jane Doe", "policy_number": "POL-1001"}'})()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: FakeLLM())
    state = _state(transcript="My name is Jane Doe, policy POL-1001")
    out = normalize_node(state)
    assert out["applicant"].full_name == "Jane Doe"
    assert out["applicant"].policy_number == "POL-1001"


def test_normalize_tolerates_markdown_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLLM:
        def invoke(self, messages):
            return type("R", (), {"content": '```json\n{"full_name": "John Smith"}\n```'})()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: FakeLLM())
    out = normalize_node(_state(transcript="John Smith"))
    assert out["applicant"].full_name == "John Smith"


def test_normalize_normalizes_dob(monkeypatch: pytest.MonkeyPatch) -> None:
    """The normalize agent should convert any DOB format to YYYY-MM-DD."""
    class FakeLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Jane Doe", "date_of_birth": "April 12, 1985"}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: FakeLLM())
    out = normalize_node(_state(transcript="Jane Doe born April 12 1985"))
    assert out["applicant"].date_of_birth == "1985-04-12"


def test_normalize_normalizes_numeric_dob(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Jane Doe", "date_of_birth": "12/04/1985"}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: FakeLLM())
    out = normalize_node(_state(transcript="Jane Doe born 12/04/1985"))
    assert out["applicant"].date_of_birth == "1985-04-12"


# ---- JSON repair ----
def test_parse_applicant_trailing_comma() -> None:
    a = _parse_applicant('{"full_name": "Jane Doe", "policy_number": "POL-1001",}')
    assert a.full_name == "Jane Doe"
    assert a.policy_number == "POL-1001"


def test_parse_applicant_single_quotes() -> None:
    a = _parse_applicant("{'full_name': 'Jane Doe', 'policy_number': 'POL-1001'}")
    assert a.full_name == "Jane Doe"
    assert a.policy_number == "POL-1001"


def test_parse_applicant_unquoted_keys() -> None:
    a = _parse_applicant("{full_name: 'Jane Doe', policy_number: 'POL-1001'}")
    assert a.full_name == "Jane Doe"
    assert a.policy_number == "POL-1001"


def test_parse_applicant_surrounding_prose() -> None:
    a = _parse_applicant('Here is the data: {"full_name": "Jane Doe"} Hope this helps.')
    assert a.full_name == "Jane Doe"


def test_parse_applicant_garbage_returns_empty() -> None:
    a = _parse_applicant("I'm sorry, I cannot process this request.")
    assert a.full_name is None


# ---- normalize retry ----
def test_normalize_retries_on_empty_first_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the first LLM response is non-JSON, normalize should retry once."""

    class _RetryLLM:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return type("R", (), {"content": "Sorry, I can't do that."})()
            return type("R", (), {"content": '{"full_name": "Jane Doe", "policy_number": "POL-1001"}'})()

    fake = _RetryLLM()
    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: fake)
    out = normalize_node(_state(transcript="Jane Doe policy POL-1001"))
    assert fake.calls == 2
    assert out["applicant"].full_name == "Jane Doe"
    assert out["applicant"].policy_number == "POL-1001"


# ---- validate ----
def test_validate_missing_required_fields() -> None:
    state = _state(applicant=ApplicantInfo(full_name="Jane Doe"))
    out = validate_node(state)
    assert out["stage"] == "validate"
    assert out["audit_trail"][-1].outcome == "warn"


def test_validate_valid_applicant() -> None:
    applicant = ApplicantInfo(
        full_name="Jane Doe",
        date_of_birth="1985-04-12",
        policy_number="POL-1001",
        coverage_amount=500000.0,
        email="jane@example.com",
        phone="555-0100",
    )
    out = validate_node(_state(applicant=applicant))
    assert out["audit_trail"][-1].outcome == "ok"


def test_validate_bad_email() -> None:
    applicant = ApplicantInfo(
        full_name="Jane Doe",
        date_of_birth="1985-04-12",
        policy_number="POL-1001",
        coverage_amount=500000.0,
        email="not-an-email",
    )
    out = validate_node(_state(applicant=applicant))
    assert out["audit_trail"][-1].outcome == "warn"


# ---- verify_policy ----
def test_verify_policy_found(db: UnderwritingDB) -> None:
    applicant = ApplicantInfo(policy_number="POL-1001")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is not None
    assert out["policy"].verified is True


def test_verify_policy_not_found(db: UnderwritingDB) -> None:
    applicant = ApplicantInfo(policy_number="NOPE")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is None
    assert out["audit_trail"][-1].outcome == "warn"


def test_verify_policy_no_number(db: UnderwritingDB) -> None:
    out = verify_policy_node(_state(applicant=ApplicantInfo()))
    assert out["policy"] is None


def test_verify_policy_fuzzy_match_spoken(db: UnderwritingDB) -> None:
    """STT often mishears 'POL-1001' as 'Paul 1001' — fuzzy match should recover."""
    applicant = ApplicantInfo(policy_number="Paul 1001")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is not None
    assert out["policy"].policy_number == "POL-1001"
    assert out["policy"].verified is True


def test_verify_policy_fuzzy_match_no_separator(db: UnderwritingDB) -> None:
    """'POL1001' without a dash should still match."""
    applicant = ApplicantInfo(policy_number="POL1001")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is not None
    assert out["policy"].policy_number == "POL-1001"


def test_verify_policy_fuzzy_match_spoken_digits(db: UnderwritingDB) -> None:
    """'POL one zero zero one' should normalize to POL-1001."""
    applicant = ApplicantInfo(policy_number="POL one zero zero one")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is not None
    assert out["policy"].policy_number == "POL-1001"


def test_verify_policy_suffix_only(db: UnderwritingDB) -> None:
    """If the LLM drops the prefix and returns only '1001', match by suffix."""
    applicant = ApplicantInfo(policy_number="1001")
    out = verify_policy_node(_state(applicant=applicant))
    assert out["policy"] is not None
    assert out["policy"].policy_number == "POL-1001"
    assert out["policy"].verified is True


# ---- review ----
def test_review_name_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the review LLM to force a mismatch flag."""
    class _MismatchLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"match_quality": "poor", "flags": ["name mismatch"], "rationale": "Names do not match", "confidence": 0.3}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.review.get_llm", lambda: _MismatchLLM())
    state = _state(
        applicant=ApplicantInfo(full_name="Jane Doe", coverage_amount=500000.0),
        policy=PolicyRecord(
            policy_number="POL-1001", policy_holder="Someone Else",
            coverage_amount=500000.0, verified=True,
        ),
    )
    out = review_node(state)
    assert out["audit_trail"][-1].outcome == "warn"


def test_review_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the review LLM to return a clean match."""
    class _CleanLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"match_quality": "good", "flags": [], "rationale": "All details match", "confidence": 0.95}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.review.get_llm", lambda: _CleanLLM())
    state = _state(
        applicant=ApplicantInfo(full_name="Jane Doe", coverage_amount=500000.0),
        policy=PolicyRecord(
            policy_number="POL-1001", policy_holder="Jane Doe",
            coverage_amount=500000.0, verified=True,
        ),
    )
    out = review_node(state)
    assert out["audit_trail"][-1].outcome == "ok"


# ---- decision ----
def test_decision_low_risk_accept(monkeypatch: pytest.MonkeyPatch) -> None:
    class _LowRiskLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"risk_score": 15.0, "risk_level": "low", "decision": "accept", "rationale": "Low risk profile", "key_factors": ["stable income"]}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.risk_decision.get_llm", lambda: _LowRiskLLM())
    state = _state(
        applicant=ApplicantInfo(coverage_amount=100000.0, annual_income=150000.0),
        policy=PolicyRecord(policy_number="P", policy_holder="X", premium=800.0, verified=True),
    )
    out = risk_decision_node(state)
    assert out["decision"] == "accept"
    assert out["risk"].risk_level == "low"


def test_decision_high_risk_decline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _HighRiskLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"risk_score": 85.0, "risk_level": "high", "decision": "decline", "rationale": "High risk profile", "key_factors": ["high coverage"]}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.risk_decision.get_llm", lambda: _HighRiskLLM())
    state = _state(
        applicant=ApplicantInfo(coverage_amount=2_000_000.0, annual_income=20000.0),
        policy=PolicyRecord(policy_number="P", policy_holder="X", premium=10000.0, verified=True),
    )
    out = risk_decision_node(state)
    assert out["decision"] == "decline"
    assert out["risk"].risk_level == "high"


def test_decision_audit_trail(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AuditLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"risk_score": 15.0, "risk_level": "low", "decision": "accept", "rationale": "Low risk profile", "key_factors": ["stable income"]}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.risk_decision.get_llm", lambda: _AuditLLM())
    state = _state(
        applicant=ApplicantInfo(coverage_amount=100000.0, annual_income=150000.0),
        policy=PolicyRecord(policy_number="P", policy_holder="X", premium=800.0, verified=True),
    )
    out = risk_decision_node(state)
    assert out["audit_trail"][-1].stage == "decision"
    # The audit detail should contain decision-related content
    assert len(out["audit_trail"][-1].detail) > 0
