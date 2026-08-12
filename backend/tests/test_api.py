"""Tests for the FastAPI backend server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from live_underwriter.api import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_samples_endpoint() -> None:
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    samples = resp.json()
    assert len(samples) >= 5
    # Each sample should have a transcript and expected outcome.
    for s in samples:
        assert s["name"]
        assert s["transcript"]
        assert s["expected_outcome"]
    # Jane Doe should be present.
    assert any(s["name"] == "Jane Doe" for s in samples)
    assert any(s["name"] == "Maria Garcia" for s in samples)


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


# ---- human-in-the-loop review ----
def test_underwrite_creates_review_for_flagged_case(monkeypatch) -> None:
    """A high-risk/flagged case should create a review record."""

    class _FlaggedLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {
                    "content": (
                        '{"full_name": "Maria Garcia", "policy_number": "POL-2003", '
                        '"coverage_amount": 150000.0, "annual_income": 45000.0}'
                    )
                },
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _FlaggedLLM())
    resp = client.post(
        "/api/underwrite",
        json={"transcript": "Maria Garcia policy POL-2003 coverage 150000 income 45000"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Maria's docs are flagged -> a review should exist.
    assert len(body["flags"]) > 0

    reviews = client.get("/api/reviews?pending_only=true").json()
    assert any(r["applicant_name"] == "Maria Garcia" for r in reviews)


def test_review_list_and_resolve(monkeypatch) -> None:
    """A review can be listed and resolved (approved/declined)."""

    class _FlaggedLLM:
        def invoke(self, messages):
            return type(
                "R",
                (),
                {
                    "content": (
                        '{"full_name": "Maria Garcia", "policy_number": "POL-2003", '
                        '"coverage_amount": 150000.0, "annual_income": 45000.0}'
                    )
                },
            )()

    monkeypatch.setattr("live_underwriter.agents.normalize.get_llm", lambda: _FlaggedLLM())
    client.post(
        "/api/underwrite",
        json={"transcript": "Maria Garcia policy POL-2003 coverage 150000 income 45000"},
    )

    # Find Maria's pending review.
    reviews = client.get("/api/reviews?pending_only=true").json()
    maria = next(r for r in reviews if r["applicant_name"] == "Maria Garcia")

    # Resolve it.
    resp = client.post(
        f"/api/reviews/{maria['id']}/resolve",
        json={"status": "approved", "reviewer_note": "Verified docs manually"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["reviewer_note"] == "Verified docs manually"

    # It should no longer be pending.
    pending = client.get("/api/reviews?pending_only=true").json()
    assert all(r["id"] != maria["id"] for r in pending)


def test_review_resolve_invalid_status() -> None:
    resp = client.post(
        "/api/reviews/1/resolve",
        json={"status": "maybe"},
    )
    assert resp.status_code == 400
