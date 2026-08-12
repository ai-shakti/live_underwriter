"""Tests for the PDF text extraction tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from live_underwriter.tools.pdf import extract_pdf_text

# Real documents downloaded to data/sample_documents/ for testing.
SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_documents"


@pytest.mark.parametrize(
    "filename,min_chars",
    [
        ("form-1040.pdf", 1000),
        ("form-w2.pdf", 1000),
        ("form-1099-int.pdf", 1000),
        ("sample-bank-statement.pdf", 100),
    ],
)
def test_extract_pdf_text_real_documents(filename: str, min_chars: int) -> None:
    """Real PDFs should yield extractable text."""
    pdf = SAMPLE_DIR / filename
    if not pdf.exists():
        pytest.skip(f"{filename} not downloaded")
    text = extract_pdf_text(pdf)
    assert len(text) >= min_chars


def test_extract_pdf_text_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        extract_pdf_text("does-not-exist.pdf")
