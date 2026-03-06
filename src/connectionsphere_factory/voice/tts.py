"""
connectionsphere_factory/voice/tts.py
Cartesia TTS — sonic-3 via AsyncCartesia v3 SDK.
"""
from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from cartesia import AsyncCartesia

from connectionsphere_factory.config import get_settings
from connectionsphere_factory.logging import get_logger

log = get_logger(__name__)

_OUTPUT_FORMAT = {
    "container":   "wav",
    "encoding":    "pcm_f32le",
    "sample_rate": 44100,
}


def _settings():
    return get_settings()


async def generate_tts(text: str, save_path: str) -> bytes:
    """Generate TTS audio and save to disk. Returns raw bytes."""
    settings = _settings()
    log.info("tts.generate.start", chars=len(text), model=settings.cartesia_model)

    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncCartesia(api_key=settings.cartesia_api_key) as client:
        response = await client.tts.generate(
            model_id      = settings.cartesia_model,
            transcript    = text,
            voice         = {"mode": "id", "id": settings.cartesia_voice_id},
            output_format = _OUTPUT_FORMAT,
        )
        await response.write_to_file(str(path))

    audio = path.read_bytes()
    log.info("tts.generate.complete", bytes=len(audio), path=save_path)
    return audio


async def stream_tts(text: str) -> AsyncGenerator[bytes, None]:
    """Generate TTS and yield the full WAV in one chunk."""
    settings = _settings()
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        audio = await generate_tts(text, save_path=tmp)
        yield audio
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def audio_path(session_id: str, stage_n: int) -> str:
    settings = _settings()
    return f"{settings.audio_storage_dir}/{session_id}_stage_{stage_n}.wav"
