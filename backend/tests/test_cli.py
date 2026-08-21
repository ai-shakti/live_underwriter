"""Tests for Phase 4: CLI and full graph end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from live_underwriter.cli import _print_result, main
from live_underwriter.graph import compile_graph


class _FakeLLM:
    """Returns a fixed JSON applicant for any transcript."""

    def invoke(self, messages):
        return type(
            "R",
            (),
            {
                "content": (
                    '{"full_name": "Jane Doe", "date_of_birth": "1985-04-12", '
                    '"policy_number": "POL-1001", "coverage_amount": 500000.0, '
                    '"annual_income": 120000.0}'
                )
            },
        )()


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _FakeLLM())

    # Also mock the risk decision LLM to avoid real API calls
    class _DefaultRiskLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"risk_score": 20.0, "risk_level": "low", "decision": "accept", "rationale": "Standard risk profile", "key_factors": ["stable income"]}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.risk_decision.get_llm", lambda: _DefaultRiskLLM())

    # Mock the review LLM to avoid real API calls
    class _DefaultReviewLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"match_quality": "good", "flags": [], "rationale": "All details match", "confidence": 0.95}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.review.get_llm", lambda: _DefaultReviewLLM())


@pytest.fixture(autouse=True)
def _seed_default_db() -> None:
    """Ensure the default DB is seeded so graph nodes find policies."""
    from live_underwriter.db import UnderwritingDB, seed_database

    db = UnderwritingDB()
    seed_database(db)
    db.close()


# ---- full graph end-to-end ----
def test_full_graph_accept_path() -> None:
    app = compile_graph()
    result = app.invoke(
        {
            "transcript": "My name is Jane Doe, policy POL-1001, coverage 500000, income 120000"
        }
    )
    assert result["decision"] == "accept"
    assert result["risk"].risk_level == "low"
    assert result["policy"].verified is True
    # Audit trail should have entries for every stage.
    stages = [e.stage for e in result["audit_trail"]]
    assert "normalize" in stages
    assert "validate" in stages
    assert "verify_policy" in stages
    assert "decision" in stages


def test_full_graph_reject_when_policy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _NoPolicyLLM(_FakeLLM):
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Jane Doe", "policy_number": "POL-9999"}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _NoPolicyLLM())
    app = compile_graph()
    result = app.invoke({"transcript": "Jane Doe, policy POL-9999"})
    # Unverified policy -> gate routes to END (reject) before decisioning.
    assert result["policy"] is None or result["policy"].verified is False
    assert result.get("decision") is None


def test_full_graph_alice_accept(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alice Johnson: clean docs, low coverage -> accept."""
    class _AliceLLM(_FakeLLM):
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Alice Johnson", "policy_number": "POL-2001", "coverage_amount": 250000.0, "annual_income": 65000.0}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _AliceLLM())
    app = compile_graph()
    result = app.invoke({"transcript": "Alice Johnson policy POL-2001 coverage 250000 income 65000"})
    assert result["decision"] == "accept"
    assert result["policy"].verified is True


def test_full_graph_robert_high_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Robert Chen: $1M coverage + high premium -> medium/high risk (review)."""
    class _RobertLLM(_FakeLLM):
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Robert Chen", "policy_number": "POL-2002", "coverage_amount": 1000000.0, "annual_income": 300000.0}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _RobertLLM())
    # Also mock the risk decision LLM to return a high-risk assessment
    class _HighRiskLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"risk_score": 65.0, "risk_level": "high", "decision": "decline", "rationale": "High coverage-to-income ratio", "key_factors": ["high coverage"]}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.risk_decision.get_llm", lambda: _HighRiskLLM())
    app = compile_graph()
    result = app.invoke({"transcript": "Robert Chen policy POL-2002 coverage 1000000 income 300000"})
    # High coverage + premium pushes risk up; high income offsets it -> medium (review).
    assert result["risk"].risk_level in ("medium", "high")
    assert result["decision"] in ("review", "decline")


def test_full_graph_maria_flagged_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Maria Garcia: overdraft + delinquent docs -> document review flags."""
    class _MariaLLM(_FakeLLM):
        def invoke(self, messages):
            return type(
                "R",
                (),
                {"content": '{"full_name": "Maria Garcia", "policy_number": "POL-2003", "coverage_amount": 150000.0, "annual_income": 45000.0}'},
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _MariaLLM())
    app = compile_graph()
    result = app.invoke({"transcript": "Maria Garcia policy POL-2003 coverage 150000 income 45000"})
    # Document review should have flagged her docs.
    assert any("overdraft" in f for f in result["risk"].flags)
    assert any("delinquent" in f for f in result["risk"].flags)


# ---- CLI ----
def test_cli_version(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "live-underwriter" in capsys.readouterr().out


def test_cli_seed_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from live_underwriter import cli

    monkeypatch.setattr(cli, "_seed_db", lambda: 0)
    assert main(["--seed-db"]) == 0


def test_cli_transcript_runs(capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
    # Point the DB at a temp file so we don't touch the real one.
    from live_underwriter.db import UnderwritingDB

    db_path = tmp_path / "cli.db"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "live_underwriter.db.UnderwritingDB",
        lambda: UnderwritingDB(db_path),
    )
    try:
        code = main(["--transcript", "Jane Doe policy POL-1001 coverage 500000"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Decision: accept" in out
        assert "Audit trail:" in out
    finally:
        monkeypatch.undo()


def test_print_result_handles_empty() -> None:
    # Should not raise on a minimal result dict.
    _print_result({"stage": "decision", "decision": "accept"})
