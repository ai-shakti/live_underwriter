"""Text-to-speech using Kokoro-82M (Apache-2.0, fast, high quality).

Kokoro supports MPS GPU acceleration on Apple Silicon. Voice is configurable
via env var ``KOKORO_VOICE`` (default ``af_heart``).
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np

from live_underwriter.logging_conf import get_logger

logger = get_logger(__name__)

DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_heart")

# Kokoro outputs 24 kHz mono audio.
SAMPLE_RATE = 24000


def _write_wav(audio: np.ndarray, out: Path) -> None:
    """Write a float32 numpy array ([-1, 1]) to a 16-bit PCM WAV file."""
    # Clamp and convert to int16.
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


def synthesize(text: str, output_path: str | Path, voice: str | None = None) -> Path:
    """Synthesize speech from text and write it to output_path."""
    try:
        from kokoro import KPipeline
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "kokoro is not installed. Install with: uv sync --extra voice"
        ) from exc

    pipeline = KPipeline(lang_code="a")  # American English
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    logger.info("tts: synthesizing %d chars with voice %s", len(text), voice or DEFAULT_VOICE)
    chunks: list[np.ndarray] = []
    for result in pipeline(text, voice=voice or DEFAULT_VOICE):
        # New Kokoro API: result.output.audio is a torch Tensor.
        audio = result.output.audio
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunks.append(np.asarray(audio, dtype=np.float32))

    if not chunks:
        raise RuntimeError("Kokoro produced no audio output")

    full = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    _write_wav(full, out)
    logger.info("tts: wrote audio to %s (%d samples)", out, len(full))
    return out
