"""Benchmark candidate LLMs for the underwriting extraction use case.

Tests each model on realistic underwriting transcripts and measures:
  - Correctness of structured JSON extraction (field accuracy)
  - Latency
  - Whether the output parses cleanly

Usage:
    cd backend
    uv run python -m scripts.benchmark_models
"""

from __future__ import annotations

import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from live_underwriter.llm import get_llm

SYSTEM_PROMPT = """You are an underwriting intake analyst. Extract structured applicant
data from the applicant's spoken transcript. Return ONLY a JSON object with these keys
(use null when a value is not present):
full_name, date_of_birth, email, phone, address, policy_number, coverage_amount,
occupation, annual_income.
Do not invent data that is not in the transcript."""

# Realistic underwriting transcripts with known ground truth.
CASES = [
    {
        "name": "complete_application",
        "transcript": (
            "Hi, my name is Jane Doe, I was born on April 12th 1985. My policy number "
            "is POL-1001 and I'm looking for five hundred thousand dollars in coverage. "
            "I work as a software engineer and my annual income is one hundred twenty "
            "thousand dollars."
        ),
        "expected": {
            "full_name": "Jane Doe",
            "date_of_birth": "1985-04-12",
            "policy_number": "POL-1001",
            "coverage_amount": 500000.0,
            "occupation": "software engineer",
            "annual_income": 120000.0,
        },
    },
    {
        "name": "partial_application",
        "transcript": (
            "Hello, I'm John Smith. I'd like to apply for a policy, my number is POL-1002. "
            "I don't remember my exact income right now."
        ),
        "expected": {
            "full_name": "John Smith",
            "policy_number": "POL-1002",
            "annual_income": None,
        },
    },
    {
        "name": "noisy_transcript",
        "transcript": (
            "Um, so yeah, my name is Alice Johnson, born March 3rd 1990. Policy POL-2001. "
            "I want like two hundred and fifty thousand coverage. I'm a teacher, "
            "I make about sixty five thousand a year. Yeah that's about it."
        ),
        "expected": {
            "full_name": "Alice Johnson",
            "date_of_birth": "1990-03-03",
            "policy_number": "POL-2001",
            "coverage_amount": 250000.0,
            "occupation": "teacher",
            "annual_income": 65000.0,
        },
    },
]


def _normalize(value):
    """Normalize a value for comparison (lowercase strings, strip)."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


def score_case(parsed: dict, expected: dict) -> tuple[int, list[str]]:
    """Score a parsed result against expected. Returns (correct_count, errors)."""
    correct = 0
    errors = []
    for key, exp in expected.items():
        got = parsed.get(key)
        if exp is None:
            if got in (None, ""):
                correct += 1
            else:
                errors.append(f"{key}: expected null, got {got!r}")
            continue
        if _normalize(got) == _normalize(exp):
            correct += 1
        else:
            errors.append(f"{key}: expected {exp!r}, got {got!r}")
    return correct, errors


def run_model(model: str) -> dict:
    """Run all cases against a model and return aggregate results."""
    llm = get_llm(model=model)
    total_fields = sum(len(c["expected"]) for c in CASES)
    total_correct = 0
    total_time = 0.0
    parse_failures = 0
    case_results = []

    for case in CASES:
        start = time.perf_counter()
        try:
            resp = llm.invoke(
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=case["transcript"])]
            )
            elapsed = time.perf_counter() - start
            total_time += elapsed

            content = resp.content
            # Strip markdown fences.
            cleaned = str(content).replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise ValueError("not a dict")
        except Exception as exc:  # noqa: BLE001
            parse_failures += 1
            case_results.append({"case": case["name"], "ok": False, "error": str(exc), "time": 0})
            continue

        correct, errors = score_case(parsed, case["expected"])
        total_correct += correct
        case_results.append(
            {"case": case["name"], "ok": len(errors) == 0, "correct": correct, "errors": errors, "time": round(elapsed, 2)}
        )

    return {
        "model": model,
        "field_accuracy": round(total_correct / total_fields * 100, 1),
        "total_time": round(total_time, 2),
        "avg_time": round(total_time / len(CASES), 2),
        "parse_failures": parse_failures,
        "cases": case_results,
    }


def main() -> None:
    models = ["qwen3.5:397b", "deepseek-v4-flash:0731"]
    results = []
    for model in models:
        print(f"\n=== Benchmarking {model} ===")
        try:
            r = run_model(model)
            results.append(r)
            print(f"  Field accuracy: {r['field_accuracy']}%")
            print(f"  Avg latency: {r['avg_time']}s")
            print(f"  Parse failures: {r['parse_failures']}")
            for c in r["cases"]:
                status = "PASS" if c["ok"] else "FAIL"
                print(f"    [{status}] {c['case']} ({c.get('time', 0)}s)")
                if not c["ok"] and c.get("errors"):
                    for e in c["errors"]:
                        print(f"        - {e}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")

    print("\n\n=== SUMMARY ===")
    for r in sorted(results, key=lambda x: x["field_accuracy"], reverse=True):
        print(
            f"  {r['model']}: {r['field_accuracy']}% accuracy, "
            f"{r['avg_time']}s avg, {r['parse_failures']} parse failures"
        )


if __name__ == "__main__":
    main()
