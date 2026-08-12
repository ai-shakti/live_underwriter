"""CLI entry point for live_underwriter."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from live_underwriter.logging_conf import get_logger, setup_logging

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run the live_underwriter CLI."""
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="live-underwriter",
        description="AI underwriting analyst agent team.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="live-underwriter 0.1.0",
    )
    parser.add_argument(
        "--transcript",
        type=str,
        help="Run a single underwriting pass on a text transcript.",
    )
    parser.add_argument(
        "--audio",
        type=str,
        help="Run a single underwriting pass on an audio file (STT -> graph -> TTS).",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Seed the SQLite database with mock data, then exit.",
    )
    args = parser.parse_args(argv)

    if args.seed_db:
        return _seed_db()
    if args.audio:
        return _run_audio(args.audio)
    if args.transcript:
        return _run_single(args.transcript)
    print("Live Underwriter — interactive mode coming soon.")
    return 0


def _seed_db() -> int:
    from live_underwriter.db import UnderwritingDB, seed_database

    db = UnderwritingDB()
    seed_database(db)
    db.close()
    print("Database seeded.")
    return 0


def _run_single(transcript: str) -> int:
    """Run the underwriting graph on a single transcript."""
    from live_underwriter.db import UnderwritingDB, seed_database
    from live_underwriter.graph import compile_graph
    from live_underwriter.state import UnderwritingState

    db = UnderwritingDB()
    seed_database(db)
    db.close()

    app = compile_graph()
    result = app.invoke(UnderwritingState(transcript=transcript))
    _print_result(result)
    return 0


def _run_audio(audio_path: str) -> int:
    """Run the underwriting graph on an audio file: STT -> graph -> TTS."""
    from live_underwriter.db import UnderwritingDB, seed_database
    from live_underwriter.graph import compile_graph
    from live_underwriter.state import UnderwritingState
    from live_underwriter.tools.stt import transcribe
    from live_underwriter.tools.tts import synthesize

    db = UnderwritingDB()
    seed_database(db)
    db.close()

    logger.info("audio: transcribing %s", audio_path)
    transcript = transcribe(audio_path)
    print(f"Transcribed: {transcript}")

    app = compile_graph()
    result = app.invoke(UnderwritingState(transcript=transcript))
    _print_result(result)

    # Speak the decision back.
    decision = result.get("decision") or "no decision"
    rationale = result.get("risk", {}).get("rationale", "") if result.get("risk") else ""
    response_text = f"The underwriting decision is {decision}. {rationale}"
    out_path = "data/response.wav"
    synthesize(response_text, out_path)
    print(f"Spoken response written to {out_path}")
    return 0


def _print_result(result: dict[str, Any]) -> None:
    """Print the final decision and audit trail."""
    print(f"Stage reached: {result.get('stage')}")
    print(f"Decision: {result.get('decision')}")
    risk = result.get("risk")
    if risk:
        print(f"Risk score: {risk.risk_score} ({risk.risk_level})")
        print(f"Rationale: {risk.rationale}")
        if risk.flags:
            print("Flags:")
            for flag in risk.flags:
                print(f"  - {flag}")
    trail = result.get("audit_trail") or []
    if trail:
        print("Audit trail:")
        for entry in trail:
            print(f"  [{entry.stage}] {entry.detail}")


if __name__ == "__main__":
    sys.exit(main())
