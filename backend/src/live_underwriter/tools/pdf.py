"""PDF text extraction for document review.

Uses pypdf to extract text from real PDF documents (tax returns, bank
statements, W-2s, etc.) so the document review agent can analyze them.
"""

from __future__ import annotations

from pathlib import Path

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract all text from a PDF file."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError("pypdf is not installed. Install with: uv add pypdf") from exc

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - some pages may be scanned images
            logger.warning("pdf: could not extract text from a page: %s", exc)
            text = ""
        pages.append(text)
    full = "\n".join(pages).strip()
    logger.info("pdf: extracted %d chars from %s", len(full), pdf_path)
    return full
