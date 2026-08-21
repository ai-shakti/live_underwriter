"""Document review agent — analyze supporting documents from the DB."""

from __future__ import annotations

from typing import Any

from live_underwriter.agents._helpers import append_audit
from live_underwriter.db import UnderwritingDB
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import UnderwritingState

logger = get_logger(__name__)

_db: UnderwritingDB | None = None


def set_db_for_tests(db: UnderwritingDB) -> None:
    """Override the DB used by document_review_node (test hook)."""
    global _db
    _db = db


def _get_db() -> UnderwritingDB:
    return _db if _db is not None else UnderwritingDB()


# Keywords that indicate a document is problematic.
_RISK_KEYWORDS = ["overdraft", "insufficient funds", "returned", "delinquent", "default"]

# Negation words that cancel a following risk keyword (e.g. "no delinquent").
_NEGATIONS = ("no ", "not ", "none ", "without ", "no evidence of ")


def _analyze_document(doc: dict[str, Any]) -> list[str]:
    """Return flags for a single document based on its content.

    Negation-aware: a risk keyword preceded by "no"/"not"/"none" is not a flag
    (e.g. "no delinquent accounts" is a positive signal, not a risk).
    """
    content = str(doc.get("content", "")).lower()
    flags = []
    for kw in _RISK_KEYWORDS:
        idx = content.find(kw)
        while idx != -1:
            # Check the text immediately before the keyword for a negation.
            before = content[max(0, idx - 12) : idx]
            if not any(before.endswith(neg) for neg in _NEGATIONS):
                flags.append(f"{doc['doc_type']} risk: '{kw}'")
                break
            idx = content.find(kw, idx + 1)
    return flags


def document_review_node(state: UnderwritingState) -> dict[str, Any]:
    """Analyze supporting documents; append any findings to risk flags."""
    logger.info("document_review: analyzing supporting documents")
    db = _get_db()
    flags: list[str] = []

    # 1. Analyze uploaded documents (from the user).
    for up in state.uploaded_documents:
        flags.extend(_analyze_document({"doc_type": up.doc_type, "content": up.content}))
    if state.uploaded_documents:
        logger.info("document_review: analyzed %d uploaded document(s)", len(state.uploaded_documents))

    # 2. Analyze known applicant documents from the DB.
    applicant = state.applicant
    if applicant.full_name:
        known = db.get_applicant(applicant.full_name)
        if known:
            docs = db.get_documents_for_applicant(int(known["id"]))
            for doc in docs:
                flags.extend(_analyze_document(doc))
            logger.info("document_review: analyzed %d DB document(s)", len(docs))
        else:
            logger.info("document_review: no known applicant, no DB documents to review")
    else:
        logger.info("document_review: no applicant name, skipping DB docs")

    if flags:
        logger.warning("document_review: %d finding(s): %s", len(flags), flags)
        return {
            "risk": state.risk.model_copy(update={"flags": [*state.risk.flags, *flags]}),
            "stage": "document_review",
            **append_audit(state, "document_review", "; ".join(flags), "warn", confidence=0.4),
        }

    logger.info("document_review: no document findings")
    return {
        "stage": "document_review",
        **append_audit(state, "document_review", "no document findings", confidence=0.9),
    }
