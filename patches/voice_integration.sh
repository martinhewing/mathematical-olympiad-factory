#!/usr/bin/env bash
# voice_integration.sh
# Run from inside connectionsphere_factory/
# Adds Cartesia TTS + STT to the interview flow.

set -euo pipefail

# ── 1. Add cartesia to pyproject.toml ────────────────────────────────────────
python3 - << 'EOF'
text = open("pyproject.toml").read()
if "cartesia" not in text:
    text = text.replace(
        '    "structlog>=24.0.0",',
        '    "structlog>=24.0.0",\n    "cartesia[websockets]>=1.0.0",\n    "python-multipart>=0.0.9",',
    )
    # avoid duplicate python-multipart if already present
    lines = text.split("\n")
    seen = set()
    deduped = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('"python-multipart') and stripped in seen:
            continue
        seen.add(stripped)
        deduped.append(line)
    open("pyproject.toml", "w").write("\n".join(deduped))
    print("cartesia added to pyproject.toml")
else:
    print("cartesia already present")
EOF

# ── 2. Add config fields ──────────────────────────────────────────────────────
python3 - << 'EOF'
text = open("src/connectionsphere_factory/config.py").read()
if "cartesia_api_key" not in text:
    text = text.replace(
        "    # ── Anthropic",
        "    # ── Cartesia\n"
        "    cartesia_api_key: str = \"\"\n"
        "    cartesia_voice_id: str = \"a0e99841-438c-4a64-b679-ae501e7d6091\"\n"
        "    cartesia_model: str = \"sonic-3\"\n"
        "    cartesia_stt_model: str = \"ink-whisper\"\n"
        "    audio_storage_dir: str = \"/tmp/connectionsphere_audio\"\n\n"
        "    # ── Anthropic",
    )
    open("src/connectionsphere_factory/config.py", "w").write(text)
    print("config.py updated")
else:
    print("config already has cartesia fields")
EOF

# ── 3. Create voice/__init__.py ───────────────────────────────────────────────
mkdir -p src/connectionsphere_factory/voice

cat > src/connectionsphere_factory/voice/__init__.py << 'EOF'
"""connectionsphere_factory/voice — Cartesia TTS + STT integration."""
EOF

# ── 4. Create voice/tts.py ────────────────────────────────────────────────────
cat > src/connectionsphere_factory/voice/tts.py << 'EOF'
"""
connectionsphere_factory/voice/tts.py

Cartesia TTS — converts interviewer text to speech.

Two modes:
  stream()      → AsyncGenerator[bytes, None]  — for StreamingResponse
  generate()    → bytes                         — full WAV, saved to disk
"""
from __future__ import annotations

import asyncio
import os
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


def _client() -> AsyncCartesia:
    settings = get_settings()
    if not settings.cartesia_api_key:
        raise RuntimeError("CARTESIA_API_KEY is not set in .env")
    return AsyncCartesia(api_key=settings.cartesia_api_key)


def _voice() -> dict:
    return {
        "mode": "id",
        "id":   get_settings().cartesia_voice_id,
    }


async def stream_tts(text: str) -> AsyncGenerator[bytes, None]:
    """
    Stream TTS audio chunks from Cartesia WebSocket.
    Yields raw WAV bytes as they arrive — ~40ms first-chunk latency.
    """
    settings = get_settings()
    log.info("tts.stream.start", chars=len(text), model=settings.cartesia_model)

    async with _client() as client:
        async with client.tts.websocket() as ws:
            async for chunk in await ws.send(
                model_id      = settings.cartesia_model,
                transcript    = text,
                voice         = _voice(),
                output_format = _OUTPUT_FORMAT,
                stream        = True,
            ):
                if chunk.audio:
                    yield chunk.audio

    log.info("tts.stream.complete", chars=len(text))


async def generate_tts(text: str, save_path: str | None = None) -> bytes:
    """
    Generate full TTS audio, optionally save to disk.
    Returns raw WAV bytes.
    """
    settings = get_settings()
    log.info("tts.generate.start", chars=len(text), model=settings.cartesia_model)

    chunks: list[bytes] = []
    async for chunk in stream_tts(text):
        chunks.append(chunk)

    audio = b"".join(chunks)

    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        log.info("tts.generate.saved", path=save_path, bytes=len(audio))

    log.info("tts.generate.complete", bytes=len(audio))
    return audio


def audio_path(session_id: str, stage_n: int) -> str:
    """Canonical path for a stage audio file."""
    settings = get_settings()
    return f"{settings.audio_storage_dir}/{session_id}_stage_{stage_n}.wav"
EOF

# ── 5. Create voice/stt.py ────────────────────────────────────────────────────
cat > src/connectionsphere_factory/voice/stt.py << 'EOF'
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
EOF

# ── 6. Create routes/voice.py ─────────────────────────────────────────────────
cat > src/connectionsphere_factory/routes/voice.py << 'EOF'
"""
connectionsphere_factory/routes/voice.py

Voice endpoints — Cartesia TTS + STT.

GET  /session/{id}/stage/{n}/audio
     Streams WAV audio of the interviewer scene + question.
     Also saves file to disk. Returns X-Audio-Url header pointing to file.

POST /session/{id}/stage/{n}/voice
     Accepts audio upload from browser MediaRecorder.
     Transcribes via Cartesia STT → submits to process_submission().
     Returns same assessment JSON as the text submit endpoint.

GET  /session/{id}/stage/{n}/audio/file
     Returns the saved WAV file for download / playback.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.logging import get_logger
from connectionsphere_factory.voice.tts import stream_tts, generate_tts, audio_path
from connectionsphere_factory.voice.stt import transcribe
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["voice"])
log    = get_logger(__name__)


def _stage_text(session_id: str, stage_n: int) -> str:
    """Build the text Cartesia will speak for a given stage."""
    spec       = engine.get_or_generate_stage(session_id, stage_n)
    scene_data = store.load_field(session_id, "scene") or {}

    scene    = scene_data.get("scene", "")
    question = spec.get("opening_question", "")

    parts = []
    if scene:
        parts.append(scene)
    if question:
        parts.append(question)
    return "  ".join(parts)


@router.get("/session/{session_id}/stage/{stage_n}/audio")
async def stream_stage_audio(session_id: str, stage_n: int):
    """
    Stream TTS audio for this stage.

    The interviewer scene and opening question are spoken aloud using
    Cartesia sonic-3 via WebSocket streaming (~40ms first-chunk latency).

    The audio is also saved to disk — retrieve it later via
    `GET /session/{session_id}/stage/{stage_n}/audio/file`.

    **Headers returned:**
    - `X-Audio-Url` — URL of the saved WAV file
    - `X-Session-Id` — session identifier
    - `X-Stage-N` — stage number
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    text     = _stage_text(session_id, stage_n)
    savepath = audio_path(session_id, stage_n)

    log.info("voice.stream.start",
             session_id=session_id, stage_n=stage_n, chars=len(text))

    async def _audio_and_save():
        """Stream chunks to client AND accumulate for disk save."""
        chunks: list[bytes] = []
        async for chunk in stream_tts(text):
            chunks.append(chunk)
            yield chunk
        # Save after streaming completes
        path = Path(savepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(chunks))
        log.info("voice.stream.saved", path=savepath)

    file_url = f"/session/{session_id}/stage/{stage_n}/audio/file"

    return StreamingResponse(
        _audio_and_save(),
        media_type = "audio/wav",
        headers    = {
            "X-Audio-Url":  file_url,
            "X-Session-Id": session_id,
            "X-Stage-N":    str(stage_n),
        },
    )


@router.get("/session/{session_id}/stage/{stage_n}/audio/file")
async def get_stage_audio_file(session_id: str, stage_n: int):
    """
    Download the saved WAV file for this stage.

    File is generated on first call to
    `GET /session/{session_id}/stage/{stage_n}/audio`.
    If not yet generated, triggers generation synchronously.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    savepath = audio_path(session_id, stage_n)

    if not Path(savepath).exists():
        log.info("voice.file.generating", session_id=session_id, stage_n=stage_n)
        text = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath)

    return FileResponse(
        path         = savepath,
        media_type   = "audio/wav",
        filename     = f"stage_{stage_n}_{session_id}.wav",
    )


@router.post("/session/{session_id}/stage/{stage_n}/voice")
async def submit_voice_answer(
    session_id: str,
    stage_n:    int,
    audio:      UploadFile = File(..., description="WAV/WebM/OGG from browser MediaRecorder"),
):
    """
    Submit a spoken answer for this stage.

    Upload audio recorded from the browser's MediaRecorder API.
    Cartesia ink-whisper transcribes the audio, then the transcript
    is assessed by Claude — same pipeline as the text submit endpoint.

    **Accepted formats:** WAV, WebM, OGG, MP4

    **Returns:** Same assessment JSON as `POST /session/{id}/stage/{n}/submit`
    - `verdict`: CONFIRMED | PARTIAL | NOT_MET
    - `feedback`: Claude's assessment
    - `probe`: follow-up question if PARTIAL
    - `next_url`: where to go next
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/wav"

    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Audio too short — minimum ~1 second")

    log.info("voice.submit.received",
             session_id=session_id, stage_n=stage_n,
             bytes=len(audio_bytes), content_type=content_type)

    transcript = await transcribe(audio_bytes, content_type=content_type)

    if len(transcript.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail=f"Transcript too short: '{transcript}'. Please speak clearly and try again.",
        )

    log.info("voice.submit.transcribed",
             session_id=session_id, stage_n=stage_n, transcript=transcript[:100])

    assessment = engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = transcript,
    )

    return {
        **assessment,
        "transcript": transcript,
        "input_mode": "voice",
    }
EOF

# ── 7. Register voice router in app.py ────────────────────────────────────────
python3 - << 'EOF'
text = open("src/connectionsphere_factory/app.py").read()
if "voice" not in text:
    text = text.replace(
        "from connectionsphere_factory.routes import sessions, stages, state, visualize",
        "from connectionsphere_factory.routes import sessions, stages, state, visualize, voice",
    )
    text = text.replace(
        "    app.include_router(visualize.router)",
        "    app.include_router(visualize.router)\n    app.include_router(voice.router)",
    )
    open("src/connectionsphere_factory/app.py", "w").write(text)
    print("voice router registered in app.py")
else:
    print("voice already registered")
EOF

# ── 8. Add audio storage dir to auth public paths ─────────────────────────────
# /tmp files are served via the file endpoint which IS auth-protected — no change needed

echo ""
echo "Done. Now run:"
echo "  uv sync"
echo "  uv run uvicorn connectionsphere_factory.app:app --host 127.0.0.1 --port 8391 --reload"
echo ""
echo "New endpoints:"
echo "  GET  /session/{id}/stage/{n}/audio        — streams TTS"
echo "  GET  /session/{id}/stage/{n}/audio/file   — download WAV"
echo "  POST /session/{id}/stage/{n}/voice        — STT submit"
