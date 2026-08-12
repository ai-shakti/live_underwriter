"""Speech-to-text using faster-whisper (CTranslate2).

faster-whisper is up to 4x faster than openai-whisper and CPU-friendly with
int8 quantization. Model choice is configurable via env var ``WHISPER_MODEL``
(default ``small`` for a good latency/quality balance).
"""

from __future__ import annotations

import os

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "small")


def transcribe(audio_path: str, model_name: str | None = None) -> str:
    """Transcribe an audio file to text using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "faster-whisper is not installed. Install with: uv sync --extra voice"
        ) from exc

    model = WhisperModel(model_name or DEFAULT_MODEL, device="cpu", compute_type="int8")
    logger.info("stt: transcribing %s with model %s", audio_path, model_name or DEFAULT_MODEL)
    segments, _info = model.transcribe(audio_path, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments)
    logger.info("stt: transcribed %d chars", len(text))
    return text
