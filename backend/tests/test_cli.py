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
