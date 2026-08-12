"""LLM wiring — Ollama via the OpenAI-compatible endpoint.

All settings come from environment variables (or a ``.env`` file in the
backend directory) so there is no provider lock-in. Defaults target a local
Ollama instance (no external API, no data leaves the machine).

Env vars (see ``backend/.env.example``):
    OLLAMA_BASE_URL  default http://localhost:11434/v1
    OLLAMA_API_KEY   default "ollama"
    OLLAMA_MODEL     default qwen2.5
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

# Load .env from the backend directory (project root of the Python package).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env")

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "ollama"
DEFAULT_MODEL = "qwen2.5"


def llm_settings() -> dict[str, str]:
    """Resolve LLM settings from the environment (with defaults)."""
    settings = {
        "base_url": os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
        "api_key": os.getenv("OLLAMA_API_KEY", DEFAULT_API_KEY),
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
    }
    logger.debug("LLM settings resolved: base_url=%s model=%s", settings["base_url"], settings["model"])
    return settings


def get_llm(**overrides: str) -> ChatOpenAI:
    """Build a ChatOpenAI instance pointed at the local Ollama endpoint."""
    settings = llm_settings()
    settings.update(overrides)
    llm = ChatOpenAI(
        base_url=settings["base_url"],
        api_key=SecretStr(settings["api_key"]),
        model=settings["model"],
        temperature=0.0,  # deterministic output for structured extraction
    )
    logger.info("LLM ready: model=%s via %s", settings["model"], settings["base_url"])
    return llm
