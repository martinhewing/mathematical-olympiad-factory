"""
connectionsphere_factory/voice/stt.py

Cartesia STT — transcribes candidate audio to text.

Accepts raw audio bytes (WAV/WebM/OGG from browser MediaRecorder).
Returns transcript string for passing to process_submission().
"""
from __future__ import annotations

from cartesia import AsyncCartesia

from connectionsphere_factory.config import get_settings
from connectionsphere_factory.logging import get_logger

log = get_logger(__name__)


async def transcribe(audio_bytes: bytes, content_type: str = "audio/wav") -> str:
    """
    Transcribe audio bytes to text using Cartesia ink-whisper.

    Args:
        audio_bytes:  Raw audio from browser (WAV, WebM, OGG)
        content_type: MIME type of the audio

    Returns:
        Transcript string
    """
    settings = get_settings()

    if not settings.cartesia_api_key:
        raise RuntimeError("CARTESIA_API_KEY is not set in .env")

    log.info("stt.transcribe.start",
             bytes=len(audio_bytes),
             model=settings.cartesia_stt_model,
             content_type=content_type)

    async with AsyncCartesia(api_key=settings.cartesia_api_key) as client:
        response = await client.stt.transcribe(
            model_id    = settings.cartesia_stt_model,
            audio       = audio_bytes,
            language    = "en",
        )

    transcript = response.transcript or ""
    log.info("stt.transcribe.complete", chars=len(transcript))
    return transcript.strip()
