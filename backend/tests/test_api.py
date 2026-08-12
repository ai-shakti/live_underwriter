"""Tests for the FastAPI backend server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from live_underwriter.api import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_policy_found() -> None:
    resp = client.get("/api/policies/POL-1001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_holder"] == "Jane Doe"
    assert body["verified"] == 1


def test_get_policy_not_found() -> None:
    resp = client.get("/api/policies/NOPE")
    assert resp.status_code == 404


def test_underwrite_accept_path(monkeypatch) -> None:
    """With a mocked LLM, the full graph should return an accept decision."""

    class _FakeLLM:
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

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _FakeLLM())
    resp = client.post(
        "/api/underwrite",
        json={"transcript": "Jane Doe policy POL-1001 coverage 500000 income 120000"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "accept"
    assert body["risk_level"] == "low"
    assert body["policy"]["verified"] is True
    assert len(body["audit_trail"]) >= 4


def test_underwrite_reject_path(monkeypatch) -> None:
    """When the LLM fails (e.g. Ollama down), the API should still return a
    structured response with a null decision rather than a 500."""

    class _FailingLLM:
        def invoke(self, messages):
            raise ConnectionError("Ollama not reachable")

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _FailingLLM())
    resp = client.post(
        "/api/underwrite",
        json={"transcript": "Jane Doe policy POL-1001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] is None
    assert body["stage"] == "verify_policy"
    # The normalize failure should be recorded in the audit trail.
    assert any(e["outcome"] == "error" for e in body["audit_trail"])


def test_transcribe_returns_503_without_voice_deps(monkeypatch) -> None:
    """If faster-whisper isn't installed, the transcribe endpoint should
    return a 503 with a helpful message rather than a 500."""

    def _no_stt(*args, **kwargs):
        raise RuntimeError("faster-whisper is not installed. Install with: uv sync --extra voice")

    monkeypatch.setattr("live_underwriter.tools.stt.transcribe", _no_stt)
    resp = client.post(
        "/api/transcribe",
        files={"file": ("test.wav", b"fake-audio-bytes", "audio/wav")},
    )
    assert resp.status_code == 503
    assert "faster-whisper" in resp.json()["detail"]
