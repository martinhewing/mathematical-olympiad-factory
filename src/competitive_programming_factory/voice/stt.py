"""
competitive_programming_factory/voice/stt.py
Cartesia STT — ink-whisper, audio bytes → transcript.
"""
from __future__ import annotations
import io
import subprocess
import tempfile
import os
from cartesia import AsyncCartesia
from competitive_programming_factory.config import get_settings
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)


def _to_wav(audio_bytes: bytes) -> bytes:
    """Convert any browser audio (WebM/OGG) to 16kHz mono WAV via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        in_path = f.name
    out_path = in_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", out_path],
            check=True, capture_output=True,
        )
        return open(out_path, "rb").read()
    finally:
        for p in (in_path, out_path):
            if os.path.exists(p): os.unlink(p)


async def transcribe(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    settings = get_settings()
    if not settings.cartesia_api_key:
        raise RuntimeError("CARTESIA_API_KEY is not set in .env")

    log.info("stt.transcribe.start", bytes=len(audio_bytes))

    wav_bytes  = _to_wav(audio_bytes)
    audio_file = ("answer.wav", io.BytesIO(wav_bytes), "audio/wav")

    async with AsyncCartesia(api_key=settings.cartesia_api_key) as client:
        response = await client.stt.transcribe(
            model = "ink-whisper",
            file  = audio_file,
            language = "en",
            timestamp_granularities = ["word"],
        )

    transcript = getattr(response, "text", None) or getattr(response, "transcript", None) or ""
    words      = getattr(response, "words", None) or []
    duration   = getattr(response, "duration", None)

    word_count = len(words) if words else len(transcript.split())

    log.info(
        "stt.transcribe.complete",
        chars=len(transcript),
        word_count=word_count,
        duration=duration,
        has_word_timestamps=bool(words),
    )

    return {
        "transcript": transcript.strip(),
        "words": words,
        "word_count": word_count,
        "duration": duration,
    }
