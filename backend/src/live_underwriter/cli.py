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
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Print the full decision trace with timestamps and input snapshots.",
    )
    parser.add_argument(
        "--generate-data",
        type=int,
        nargs="?",
        const=20,
        metavar="COUNT",
        help="Generate COUNT synthetic applicants and seed the DB, then exit.",
    )
    args = parser.parse_args(argv)

    if args.seed_db:
        return _seed_db()
    if args.generate_data is not None:
        return _generate_data(args.generate_data)
    if args.audio:
        return _run_audio(args.audio, verbose=args.audit)
    if args.transcript:
        return _run_single(args.transcript, verbose=args.audit)
    print("Live Underwriter — interactive mode coming soon.")
    return 0


def _seed_db() -> int:
    from live_underwriter.db import UnderwritingDB, seed_database

    db = UnderwritingDB()
    seed_database(db)
    db.close()
    print("Database seeded.")
    return 0


def _generate_data(count: int) -> int:
    """Generate synthetic data and seed the DB."""
    from live_underwriter.data_generator import generate_dataset, _seed_db_from_dataset

    print(f"Generating {count} synthetic applicants...")
    dataset = generate_dataset(num_applicants=count)
    _seed_db_from_dataset(dataset)
    print(f"Database seeded with {count} synthetic applicants, {len(dataset.policies)} policies, "
          f"{len(dataset.documents)} documents.")
    return 0


def _run_single(transcript: str, verbose: bool = False) -> int:
    """Run the underwriting graph on a single transcript."""
    from live_underwriter.db import UnderwritingDB, seed_database
    from live_underwriter.graph import compile_graph
    from live_underwriter.state import UnderwritingState

    db = UnderwritingDB()
    seed_database(db)
    db.close()

    app = compile_graph()
    result = app.invoke(UnderwritingState(transcript=transcript))
    _print_result(result, verbose=verbose)
    return 0


def _run_audio(audio_path: str, verbose: bool = False) -> int:
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
    _print_result(result, verbose=verbose)

    # Speak the decision back.
    decision = result.get("decision") or "no decision"
    rationale = result.get("risk", {}).get("rationale", "") if result.get("risk") else ""
    response_text = f"The underwriting decision is {decision}. {rationale}"
    out_path = "data/response.wav"
    synthesize(response_text, out_path)
    print(f"Spoken response written to {out_path}")
    return 0


def _print_result(result: dict[str, Any], verbose: bool = False) -> None:
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
            ts = entry.timestamp.split("T")[1][:8] if hasattr(entry, "timestamp") and entry.timestamp else ""
            confidence = entry.confidence if hasattr(entry, "confidence") else 0.0
            outcome_marker = {"ok": "✓", "warn": "⚠", "error": "✗"}.get(entry.outcome, "?")
            print(f"  {outcome_marker} [{entry.stage}] {entry.detail}")
            if verbose:
                print(f"     Time: {ts}  Confidence: {confidence:.0%}")
                if entry.input_snapshot:
                    snapshot = entry.input_snapshot
                    parts = [f"{k}={v}" for k, v in snapshot.items() if k != "stage"]
                    if parts:
                        print(f"     Context: {', '.join(parts)}")


if __name__ == "__main__":
    sys.exit(main())
