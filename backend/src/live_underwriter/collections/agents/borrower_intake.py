"""Borrower intake agent — normalize borrower data from transcript."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from live_underwriter.collections.state import BorrowerInfo, CollectionsState
from live_underwriter.llm import get_llm
from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a collections intake analyst. Extract structured borrower
data from the transcript. Return ONLY a JSON object with these keys
(use null when a value is not present):
full_name, date_of_birth, email, phone, address, loan_number,
outstanding_balance, monthly_payment, occupation, annual_income.
Do not invent data that is not in the transcript."""


def borrower_intake_node(state: CollectionsState) -> dict[str, Any]:
    """Extract structured borrower data from the transcript."""
    logger.info("collections: borrower intake from transcript")
    if not state.transcript:
        logger.warning("collections: empty transcript")
        return {"borrower": BorrowerInfo(), "stage": "intake"}

    llm = get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=state.transcript),
        ])
    except Exception as exc:
        logger.error("collections: LLM call failed: %s", exc)
        return {"borrower": BorrowerInfo(), "stage": "intake"}

    text = str(response.content).strip()
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    try:
        data = json.loads(text)
        borrower = BorrowerInfo(**{k: v for k, v in data.items() if k in BorrowerInfo.model_fields})
    except (json.JSONDecodeError, TypeError):
        logger.error("collections: could not parse borrower data")
        borrower = BorrowerInfo()

    logger.info("collections: extracted borrower %s", borrower.full_name)
    return {"borrower": borrower, "stage": "intake"}
