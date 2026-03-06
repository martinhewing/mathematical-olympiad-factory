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

    from fastapi.responses import Response
    audio = Path(savepath).read_bytes()
    return Response(
        content      = audio,
        media_type   = "audio/wav",
        headers      = {"Content-Disposition": "inline"},
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
