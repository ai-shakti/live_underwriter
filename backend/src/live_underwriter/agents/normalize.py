"""Normalization agent — extract structured applicant data from the transcript."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from live_underwriter.agents._helpers import append_audit
from live_underwriter.llm import get_llm
from live_underwriter.logging_conf import get_logger
from live_underwriter.state import ApplicantInfo, UnderwritingState

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an underwriting intake analyst. Extract structured applicant
data from the applicant's spoken transcript. Return ONLY a JSON object with these keys
(use null when a value is not present):
full_name, date_of_birth, email, phone, address, policy_number, coverage_amount,
occupation, annual_income.
Do not invent data that is not in the transcript."""


def _repair_json(raw: str) -> str:
    """Repair common LLM JSON output issues so it can be parsed.

    Handles: markdown fences, trailing commas, single quotes, unquoted keys,
    and stray prose around the JSON object.
    """
    text = raw.strip()
    # 1. Strip markdown code fences.
    text = re.sub(r"```(?:json)?", "", text).strip()
    # 2. Extract the first {...} block if there's surrounding prose.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    # 3. Remove trailing commas before } or ].
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # 4. Replace single quotes with double quotes (but not inside double-quoted strings).
    text = re.sub(r"(?<!\\)'", '"', text)
    # 5. Quote unquoted keys: {key: value} -> {"key": value}.
    text = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', text)
    return text


def _parse_applicant(raw: str) -> ApplicantInfo:
    """Parse the LLM's JSON response into an ApplicantInfo, tolerating noise."""
    cleaned = _repair_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("normalize: could not parse LLM output: %s", raw[:200])
        return ApplicantInfo()
    if not isinstance(data, dict):
        logger.error("normalize: LLM output was not an object: %s", raw[:200])
        return ApplicantInfo()
    return ApplicantInfo(**{k: v for k, v in data.items() if k in ApplicantInfo.model_fields})


def normalize_node(state: UnderwritingState) -> dict[str, Any]:
    """Extract structured applicant data from the transcript via the LLM."""
    logger.info("normalize: extracting applicant data from transcript")
    if not state.transcript:
        logger.warning("normalize: empty transcript, returning empty applicant")
        return {
            "applicant": ApplicantInfo(),
            "stage": "normalize",
            **append_audit(state, "normalize", "empty transcript", "warn"),
        }

    llm = get_llm()
    try:
        response = llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=state.transcript),
            ]
        )
    except Exception as exc:  # noqa: BLE001 - surface LLM/connection errors gracefully
        logger.error("normalize: LLM call failed: %s", exc)
        return {
            "applicant": ApplicantInfo(),
            "stage": "normalize",
            **append_audit(state, "normalize", f"LLM call failed: {exc}", "error"),
        }

    applicant = _parse_applicant(str(response.content))

    # Retry once if the first parse produced nothing useful (e.g. non-JSON).
    if not applicant.full_name and not applicant.policy_number:
        logger.warning("normalize: first parse empty, retrying with stricter prompt")
        try:
            response = llm.invoke(
                [
                    SystemMessage(
                        content=_SYSTEM_PROMPT
                        + "\nRespond with ONLY valid JSON. No prose, no markdown, no comments."
                    ),
                    HumanMessage(content=state.transcript),
                ]
            )
            applicant = _parse_applicant(str(response.content))
        except Exception as exc:  # noqa: BLE001
            logger.error("normalize: retry LLM call failed: %s", exc)

    logger.info("normalize: extracted applicant %s", applicant.full_name)
    return {
        "applicant": applicant,
        "stage": "normalize",
        **append_audit(state, "normalize", f"extracted applicant {applicant.full_name}"),
    }
