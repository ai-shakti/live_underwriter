"""CLI entry point for live_underwriter."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Run the live_underwriter CLI."""
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
    args = parser.parse_args(argv)

    if args.transcript:
        return _run_single(args.transcript)
    print("Live Underwriter — interactive mode coming soon.")
    return 0


def _run_single(transcript: str) -> int:
    """Run the underwriting graph on a single transcript."""
    from live_underwriter.graph import compile_graph

    app = compile_graph()
    result = app.invoke({"transcript": transcript})
    print(f"Stage reached: {result.get('stage')}")
    print(f"Decision: {result.get('decision')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
