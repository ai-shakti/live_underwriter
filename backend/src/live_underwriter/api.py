"""FastAPI server exposing the underwriting agent team as a REST API.

Endpoints:
    POST /api/underwrite   — run the full underwriting graph on a transcript.
    POST /api/transcribe   — transcribe an uploaded audio file (voice intake).
    GET  /api/health       — health check.
    GET  /api/policies/{n} — look up a policy record (for the frontend).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from live_underwriter.db import UnderwritingDB, seed_database
from live_underwriter.graph import compile_graph
from live_underwriter.logging_conf import get_logger, setup_logging
from live_underwriter.samples import get_samples
from live_underwriter.state import ApplicantInfo, PolicyRecord, RiskAssessment, UnderwritingState

logger = get_logger(__name__)

setup_logging()

app = FastAPI(
    title="Live Underwriter API",
    description="AI underwriting analyst agent team — risk assessment, policy verification, decisioning.",
    version="0.1.0",
)

# Allow the Vite dev server (and any origin in dev) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UnderwriteRequest(BaseModel):
    """Request body for the underwrite endpoint."""

    transcript: str


class UnderwriteResponse(BaseModel):
    """Response body for the underwrite endpoint."""

    stage: str
    decision: str | None
    risk_score: float
    risk_level: str
    rationale: str
    flags: list[str]
    applicant: dict[str, Any]
    policy: dict[str, Any] | None
    audit_trail: list[dict[str, Any]]


class TranscribeResponse(BaseModel):
    """Response body for the transcribe endpoint."""

    transcript: str


class ReviewResponse(BaseModel):
    """Response body for a review record."""

    id: int
    applicant_name: str
    policy_number: str | None
    risk_score: float
    risk_level: str
    ai_decision: str
    rationale: str
    flags: list[str]
    status: str
    reviewer_note: str | None
    created_at: str
    reviewed_at: str | None


class ResolveReviewRequest(BaseModel):
    """Request body to approve/decline a review."""

    status: str  # approved | declined
    reviewer_note: str | None = None


def _ensure_seeded() -> None:
    """Seed the DB if needed so policy lookups work."""
    db = UnderwritingDB()
    seed_database(db)
    db.close()


def _to_review_response(row: dict[str, Any]) -> ReviewResponse:
    """Convert a DB review row to a ReviewResponse."""
    import json

    flags = json.loads(row.get("flags") or "[]")
    return ReviewResponse(
        id=row["id"],
        applicant_name=row["applicant_name"],
        policy_number=row.get("policy_number"),
        risk_score=row["risk_score"],
        risk_level=row["risk_level"],
        ai_decision=row["ai_decision"],
        rationale=row["rationale"],
        flags=flags,
        status=row["status"],
        reviewer_note=row.get("reviewer_note"),
        created_at=row["created_at"],
        reviewed_at=row.get("reviewed_at"),
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/samples")
def samples() -> list[dict[str, Any]]:
    """Return curated sample applicants for testing the workflow."""
    return get_samples()


@app.post("/api/transcribe", response_model=TranscribeResponse)
def transcribe_audio(file: UploadFile = File(...)) -> TranscribeResponse:  # noqa: B008 - FastAPI injects the upload
    """Transcribe an uploaded audio file (live voice intake)."""
    logger.info("api: transcribe request received: %s", file.filename)
    try:
        from live_underwriter.tools.stt import transcribe
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Save the upload to a temp file and transcribe it.
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        text = transcribe(tmp_path)
    except RuntimeError as exc:
        # Missing optional voice dependency (faster-whisper not installed).
        logger.error("api: transcription unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # surface STT errors to the client
        logger.error("api: transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return TranscribeResponse(transcript=text)


@app.post("/api/underwrite", response_model=UnderwriteResponse)
def underwrite(req: UnderwriteRequest) -> UnderwriteResponse:
    """Run the underwriting graph on a transcript and return the result."""
    logger.info("api: underwrite request received")
    _ensure_seeded()

    app_graph = compile_graph()
    result = app_graph.invoke(UnderwritingState(transcript=req.transcript))

    risk = result.get("risk")
    applicant = result.get("applicant")
    policy = result.get("policy")

    # Human-in-the-loop: if the case is flagged or needs review, create a review.
    needs_review = (
        risk is not None
        and (risk.risk_level == "high" or risk.decision == "review" or len(risk.flags) > 0)
    )
    if needs_review:
        _create_review_for_result(applicant, policy, risk)

    return UnderwriteResponse(
        stage=result.get("stage", "intake"),
        decision=result.get("decision"),
        risk_score=risk.risk_score if risk else 0.0,
        risk_level=risk.risk_level if risk else "low",
        rationale=risk.rationale if risk else "",
        flags=risk.flags if risk else [],
        applicant=applicant.model_dump() if applicant else {},
        policy=policy.model_dump() if policy else None,
        audit_trail=[e.model_dump() for e in result.get("audit_trail", [])],
    )


def _create_review_for_result(
    applicant: ApplicantInfo | None,
    policy: PolicyRecord | None,
    risk: RiskAssessment | None,
) -> None:
    """Create a review record for a flagged/high-risk case."""
    import json

    if risk is None:
        logger.warning("api: cannot create review without a risk assessment")
        return

    db = UnderwritingDB()
    try:
        db.create_review(
            {
                "applicant_name": applicant.full_name if applicant else "Unknown",
                "policy_number": policy.policy_number if policy else None,
                "risk_score": risk.risk_score,
                "risk_level": risk.risk_level,
                "ai_decision": risk.decision,
                "rationale": risk.rationale,
                "flags": json.dumps(risk.flags),
            }
        )
        logger.info("api: created review for %s", applicant.full_name if applicant else "Unknown")
    finally:
        db.close()


@app.get("/api/reviews", response_model=list[ReviewResponse])
def list_reviews(pending_only: bool = False) -> list[ReviewResponse]:
    """List reviews, optionally only pending ones."""
    _ensure_seeded()
    db = UnderwritingDB()
    try:
        rows = db.get_pending_reviews() if pending_only else db.get_all_reviews()
        return [_to_review_response(r) for r in rows]
    finally:
        db.close()


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int) -> ReviewResponse:
    """Get a single review by id."""
    _ensure_seeded()
    db = UnderwritingDB()
    try:
        row = db.get_review(review_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
        return _to_review_response(row)
    finally:
        db.close()


@app.post("/api/reviews/{review_id}/resolve", response_model=ReviewResponse)
def resolve_review(review_id: int, req: ResolveReviewRequest) -> ReviewResponse:
    """Approve or decline a pending review (human decision)."""
    if req.status not in ("approved", "declined"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'declined'")
    _ensure_seeded()
    db = UnderwritingDB()
    try:
        updated = db.resolve_review(review_id, req.status, req.reviewer_note)
        if not updated:
            row = db.get_review(review_id)
            if row is None:
                raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
            raise HTTPException(status_code=409, detail="Review already resolved")
        row = db.get_review(review_id)
        if row is None:
            raise HTTPException(status_code=500, detail="Review disappeared after resolve")
        return _to_review_response(row)
    finally:
        db.close()


@app.get("/api/policies/{policy_number}")
def get_policy(policy_number: str) -> dict[str, Any]:
    """Look up a policy record by number."""
    _ensure_seeded()
    db = UnderwritingDB()
    row = db.get_policy(policy_number)
    db.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_number} not found")
    return row
