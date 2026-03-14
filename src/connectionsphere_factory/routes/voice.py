"""
connectionsphere_factory/routes/voice.py
Voice endpoints — Cartesia TTS + STT.
"""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response, HTMLResponse

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.logging import get_logger
from connectionsphere_factory.voice.tts import generate_tts, audio_path
from connectionsphere_factory.voice.stt import transcribe
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["voice"])
log    = get_logger(__name__)


def _stage_text(session_id: str, stage_n: int) -> tuple[str, str]:
    from connectionsphere_factory.domain.agents import get_agent_for_state
    from connectionsphere_factory.config import get_settings as _settings
    spec       = engine.get_or_generate_stage(session_id, stage_n)
    state_data = engine.get_state(session_id) or {}
    fsm_state  = state_data.get("fsm_state", "")
    agent      = get_agent_for_state(fsm_state)
    voice_id   = agent.voice_id(_settings())
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    # Teach phase: use lesson greeting + lesson content
    if fsm_state in {"Teach", "Teach Comprehension Check"}:
        greeting = agent.greeting(first_name)
        lesson = spec.get("greeting", "")
        check = spec.get("comprehension_check", "")
        parts = [p for p in [greeting, lesson, check] if p]
    else:
        scene_data = store.load_field(session_id, "scene") or {}
        scene      = scene_data.get("scene", "")
        question   = spec.get("opening_question", "")
        parts      = [p for p in [scene, question] if p]
    return ("  ".join(parts), voice_id)


@router.get("/session/{session_id}/stage/{stage_n}/audio/file")
async def get_stage_audio_file(session_id: str, stage_n: int):
    """Return raw WAV bytes for this stage (inline playback)."""
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    import connectionsphere_factory.session_store as _store
    _fsm_result = engine.load_session(session_id)
    _phase = "teach" if (_fsm_result and _fsm_result[0].state.value in {"Teach", "Teach Comprehension Check"}) else "interview"
    savepath = audio_path(session_id, stage_n, _phase)
    if not Path(savepath).exists():
        text, voice_id = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath, voice_id=voice_id)
    return Response(
        content    = Path(savepath).read_bytes(),
        media_type = "audio/mpeg",
        headers    = {"Content-Disposition": "inline"},
    )


@router.get("/session/{session_id}/stage/{stage_n}/play",
            response_class=HTMLResponse)
async def play_stage_audio(session_id: str, stage_n: int):
    """
    Auto-playing audio tab.

    Opens in a new tab, plays the interviewer audio immediately,
    and closes itself when playback finishes. No interaction required.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Pre-generate audio so playback starts immediately
    savepath = audio_path(session_id, stage_n)
    if not Path(savepath).exists():
        text, voice_id = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath, voice_id=voice_id)

    audio_url = f"/session/{session_id}/stage/{stage_n}/audio/file"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Interviewer — Stage {stage_n}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: #0a0a0a;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      font-family: monospace;
      color: #94a3b8;
      font-size: 0.8rem;
      letter-spacing: 0.05em;
    }}
    .pulse {{
      width: 8px; height: 8px;
      background: #6366f1;
      border-radius: 50%;
      margin-right: 10px;
      animation: pulse 1s ease-in-out infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50%       {{ opacity: 0.4; transform: scale(0.8); }}
    }}
  </style>
</head>
<body>
  <div class="pulse" id="dot"></div>
  <span id="status">INTERVIEWER SPEAKING</span>
  <audio id="audio" autoplay>
    <source src="{audio_url}" type="audio/mpeg">
  </audio>
  <script>
    const audio  = document.getElementById('audio');
    const status = document.getElementById('status');
    const dot    = document.getElementById('dot');

    audio.addEventListener('ended', () => {{
      status.textContent = 'DONE';
      dot.style.animation = 'none';
      dot.style.background = '#334155';
      setTimeout(() => window.close(), 600);
    }});

    audio.addEventListener('error', () => {{
      status.textContent = 'AUDIO ERROR';
      setTimeout(() => window.close(), 2000);
    }});
  </script>
</body>
</html>"""




@router.post("/session/{session_id}/speak")
async def speak_text(session_id: str, payload: dict):
    """
    Convert arbitrary text to speech and return WAV audio.
    Used by the interview UI to speak probe questions and feedback.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    speak_text = payload.get("text", "").strip()
    if not speak_text:
        raise HTTPException(status_code=422, detail="No text provided")

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        req_voice = payload.get("voice_id", "")
        from connectionsphere_factory.config import get_settings as _settings
        cfg = _settings()
        use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALEX_VOICE" else cfg.cartesia_voice_id
        await generate_tts(speak_text, save_path=tmp, voice_id=use_voice)
        audio = Path(tmp).read_bytes()
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

    return Response(
        content    = audio,
        media_type = "audio/mpeg",
        headers    = {"Content-Disposition": "inline"},
    )

@router.post("/session/{session_id}/stage/{stage_n}/voice")
async def submit_voice_answer(
    session_id: str,
    stage_n:    int,
    audio:      UploadFile = File(...),
    images:     list[UploadFile] = File(default=[]),
):
    """
    Submit spoken answer + optional diagrams. Transcribes via STT → Claude assessment.
    Returns same JSON as text submit + transcript field.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/mpeg"

    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Audio too short")

    transcript = await transcribe(audio_bytes, content_type=content_type)

    if len(transcript.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="We couldn't hear that clearly. Check your microphone is connected and try again — speak for at least 3 seconds.",
        )

    # Attach images to transcript for Claude assessment
    image_data = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            import base64
            image_data.append({
                "media_type": img.content_type or "image/png",
                "data": base64.b64encode(img_bytes).decode(),
            })

    assessment = engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = transcript,
        images     = image_data,
    )
    # Convert Pydantic model or dict to plain dict
    if hasattr(assessment, "model_dump"):
        assessment = assessment.model_dump()
    return {**assessment, "transcript": transcript, "input_mode": "voice"}


@router.get("/session/{session_id}/interview", response_class=HTMLResponse)
async def interview_page(session_id: str):
    """
    Candidate-facing interview UI.

    Full-session single-page interface:
    - Auto-plays stage audio on load
    - Records candidate voice answer
    - Submits, shows assessment, auto-advances on CONFIRMED
    - Holds on PARTIAL for probe response
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    state   = engine.get_state(session_id)
    scene   = store.load_field(session_id, "scene") or {}
    problem = store.load_field(session_id, "problem_statement") or ""
    name    = store.load_field(session_id, "candidate_name") or "Candidate"

    agent_name = state.get("agent_name", "Interviewer")
    agent_role = state.get("agent_role", "INTERVIEWER")

    return HTMLResponse(content=_interview_html(
        session_id = session_id,
        problem    = problem,
        name       = name,
        scene      = scene.get("scene", ""),
        fsm_state  = state["fsm_state"],
        phase      = state["phase"],
        agent_name = agent_name,
        agent_role = agent_role,
    ))


def _interview_html(session_id, problem, name, scene, fsm_state, phase,
                    agent_name="Interviewer", agent_role="INTERVIEWER") -> str:
    import json
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{problem} — ConnectionSphere</title>
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="apple-touch-icon" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:        #0a0a0a;
  --bg2:       #111111;
  --bg3:       #1a1a1a;
  --border:    #222222;
  --text:      #f0f0f0;
  --muted:     #666666;
  --subtle:    #333333;
  --accent:    #c8ff00;
  --danger:    #ff4444;
  --confirm:   #00ff88;
  --partial:   #ffaa00;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html, body {{
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  overflow: hidden;
}}

/* ── Top bar ─────────────────────────────────────────────────── */
.topbar {{
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 48px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 100;
}}

.topbar-left {{
  display: flex;
  align-items: center;
  gap: 16px;
}}

.logo {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}}

.separator {{ color: var(--subtle); }}

.problem-title {{
  font-size: 13px;
  font-weight: 400;
  color: var(--muted);
  max-width: 400px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.topbar-right {{
  display: flex;
  align-items: center;
  gap: 20px;
}}

.timer {{
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.08em;
}}

.fsm-badge {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--muted);
}}

.fsm-badge.active {{ border-color: var(--accent); color: var(--accent); }}

/* ── Layout ──────────────────────────────────────────────────── */
.layout {{
  display: grid;
  grid-template-columns: 38% 62%;
  height: 100vh;
  padding-top: 48px;
}}

/* ── Left panel — interviewer ─────────────────────────────────── */
.left-panel {{
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

.panel-header {{
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}}

.panel-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
}}

.panel-role {{
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  opacity: 0.7;
  margin-left: 6px;
}}

.speaking-dot {{
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  opacity: 0;
  transition: opacity 0.3s;
}}

.speaking-dot.active {{
  opacity: 1;
  animation: breathe 1.2s ease-in-out infinite;
}}

@keyframes breathe {{
  0%, 100% {{ transform: scale(1); opacity: 1; }}
  50%       {{ transform: scale(0.6); opacity: 0.4; }}
}}

.scene-text {{
  padding: 20px 24px;
  font-size: 13px;
  color: #999;
  line-height: 1.75;
  font-weight: 300;
  border-bottom: 1px solid var(--border);
  overflow-y: auto;
  max-height: 200px;
  flex-shrink: 0;
}}

.question-area {{
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}}

.question-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}}

.question-text {{
  font-family: 'DM Mono', monospace;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.8;
  color: var(--text);
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.5s ease, transform 0.5s ease;
}}

.question-text.visible {{
  opacity: 1;
  transform: translateY(0);
}}

.audio-bar {{
  padding: 12px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}}

.audio-progress {{
  flex: 1;
  height: 2px;
  background: var(--border);
  border-radius: 1px;
  overflow: hidden;
}}

.audio-fill {{
  height: 100%;
  background: var(--accent);
  width: 0%;
  transition: width 0.3s linear;
}}

.audio-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  min-width: 48px;
  text-align: right;
}}

/* ── Whiteboard panel ────────────────────────────────────────── */
.whiteboard {{
  border-top: 1px solid var(--border);
  display: none;           /* hidden by default — activated by JS */
  flex-direction: column;
  gap: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
}}
.whiteboard.active {{
  display: flex;
}}

/* Banner — appears above the drop zone when whiteboard is activated */
.whiteboard-banner {{
  padding: 8px 16px;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.whiteboard-banner.mode-alex {{
  background: rgba(88, 166, 255, 0.07);
  border-bottom: 1px solid rgba(88, 166, 255, 0.18);
  color: var(--accent);
}}
.whiteboard-banner.mode-jordan {{
  background: rgba(255, 170, 0, 0.07);
  border-bottom: 1px solid rgba(255, 170, 0, 0.18);
  color: var(--partial);
}}
.whiteboard-banner.mode-required {{
  background: rgba(255, 68, 68, 0.07);
  border-bottom: 1px solid rgba(255, 68, 68, 0.2);
  color: var(--danger);
}}
.whiteboard-banner-dot {{
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
  animation: wb-pulse 2s ease-in-out infinite;
}}
@keyframes wb-pulse {{
  0%, 100% {{ opacity: 1; }}
  50%       {{ opacity: 0.35; }}
}}

/* Reference diagram — shown as a small inline preview */
.whiteboard-reference {{
  display: none;
  padding: 10px 16px 4px;
  border-bottom: 1px solid var(--border);
}}
.whiteboard-reference.visible {{
  display: block;
}}
.whiteboard-reference-label {{
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}}
.whiteboard-reference svg,
.whiteboard-reference img {{
  width: 100%;
  max-height: 160px;
  object-fit: contain;
  border-radius: 4px;
  border: 1px solid var(--border);
  display: block;
}}
.whiteboard-reference-loading {{
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
}}

/* Drop zone + thumbs row */
.whiteboard-controls {{
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 44px;
}}
.whiteboard-drop {{
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
  flex-shrink: 0;
}}
.whiteboard-drop:hover {{ border-color: var(--accent); }}
.whiteboard.mode-required .whiteboard-drop {{
  border-color: rgba(255,68,68,0.45);
}}
.whiteboard-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.1em;
  pointer-events: none;
}}
.whiteboard-thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.whiteboard-thumb {{
  position: relative; width: 48px; height: 48px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;
}}
.whiteboard-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}

/* Record button dimming when diagram is required but not yet provided */
.record-btn.diagram-pending {{
  opacity: 0.35;
  pointer-events: none;
  cursor: not-allowed;
}}
.diagram-gate-hint {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--danger);
  letter-spacing: 0.06em;
  text-align: center;
  opacity: 0;
  transition: opacity 0.3s;
  margin-top: -20px;
}}
.diagram-gate-hint.visible {{ opacity: 1; }}

/* ── Rubric checklist in assessment panel ────────────────────── */
.rubric-list {{
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 4px;
}}
.rubric-item {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.5;
}}
.rubric-icon {{
  flex-shrink: 0;
  margin-top: 1px;
  font-size: 11px;
}}
.rubric-icon.present  {{ color: var(--confirm); }}
.rubric-icon.partial  {{ color: var(--partial); }}
.rubric-icon.missing  {{ color: var(--danger); }}
.rubric-icon.unknown  {{ color: var(--muted); }}
.rubric-text {{ color: var(--muted); }}
.rubric-text.required-item {{ color: var(--text); }}
.whiteboard-thumb .thumb-del {{
  position: absolute; top: 2px; right: 2px;
  background: rgba(0,0,0,0.7); color: var(--muted);
  font-size: 9px; border: none; border-radius: 2px;
  cursor: pointer; padding: 1px 3px; line-height: 1; display: none;
}}
.whiteboard-thumb:hover .thumb-del {{ display: block; }}
.whiteboard-lightbox {{
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.85); z-index: 1000;
  align-items: center; justify-content: center; cursor: pointer;
}}
.whiteboard-lightbox.open {{ display: flex; }}
.whiteboard-lightbox img {{ max-width: 90vw; max-height: 90vh; border-radius: 4px; object-fit: contain; }}
/* ── Right panel — candidate ──────────────────────────────────── */
.right-panel {{
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

.candidate-header {{
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.candidate-name {{
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}}

.stage-indicator {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.06em;
}}

.answer-area {{
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 32px;
  position: relative;
}}

/* ── Record button ───────────────────────────────────────────── */
.record-btn {{
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 2px solid var(--border);
  background: var(--bg2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
  position: relative;
  outline: none;
}}

.record-btn:hover {{
  border-color: var(--accent);
  background: var(--bg3);
}}

.record-btn.recording {{
  border-color: var(--danger);
  background: rgba(255, 68, 68, 0.08);
  animation: record-pulse 1.5s ease-in-out infinite;
}}

@keyframes record-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(255,68,68,0.3); }}
  50%       {{ box-shadow: 0 0 0 16px rgba(255,68,68,0); }}
}}

.record-icon {{
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--muted);
  transition: all 0.25s ease;
}}

.record-btn:hover .record-icon {{
  background: var(--accent);
}}

.record-btn.recording .record-icon {{
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: var(--danger);
}}

.record-hint {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-align: center;
}}

/* ── Waveform visualiser ─────────────────────────────────────── */
.waveform {{
  display: flex;
  align-items: center;
  gap: 3px;
  height: 32px;
  opacity: 0;
  transition: opacity 0.3s;
}}

.waveform.active {{ opacity: 1; }}

.wave-bar {{
  width: 3px;
  background: var(--accent);
  border-radius: 2px;
  height: 4px;
  transition: height 0.1s ease;
}}

/* ── Assessment panel ────────────────────────────────────────── */
.assessment {{
  border-top: 1px solid var(--border);
  padding: 20px 24px;
  display: none;
  gap: 12px;
  flex-direction: column;
  max-height: 280px;
  overflow-y: auto;
}}

.assessment.visible {{ display: flex; }}

.verdict-row {{
  display: flex;
  align-items: center;
  gap: 10px;
}}

.verdict-tag {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
}}

.verdict-CONFIRMED {{ background: rgba(0,255,136,0.1); color: var(--confirm); border: 1px solid rgba(0,255,136,0.3); }}
.verdict-PARTIAL   {{ background: rgba(255,170,0,0.1);  color: var(--partial); border: 1px solid rgba(255,170,0,0.3); }}
.verdict-NOT_MET   {{ background: rgba(255,68,68,0.1);  color: var(--danger);  border: 1px solid rgba(255,68,68,0.3); }}

.feedback-text {{
  font-size: 13px;
  color: #bbb;
  line-height: 1.7;
}}

.probe-text {{
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  color: var(--text);
  line-height: 1.7;
  padding: 12px 16px;
  background: var(--bg3);
  border-left: 2px solid var(--partial);
  border-radius: 0 4px 4px 0;
}}

.concepts-row {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}}

.concept-chip {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 3px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--muted);
}}

.concept-chip.confirmed {{
  border-color: rgba(0,255,136,0.3);
  color: var(--confirm);
}}

.next-btn {{
  align-self: flex-start;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 8px 20px;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: opacity 0.2s;
}}

.next-btn:hover {{ opacity: 0.85; }}

/* ── Status overlay ──────────────────────────────────────────── */
.status-overlay {{
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-transform: uppercase;
  opacity: 0;
  transition: opacity 0.3s;
  white-space: nowrap;
}}

.status-overlay.visible {{ opacity: 1; }}

/* ── Transcript preview ──────────────────────────────────────── */
.transcript-preview {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  line-height: 1.6;
  max-width: 400px;
  text-align: center;
  opacity: 0;
  transition: opacity 0.4s;
  font-style: italic;
}}

.transcript-preview.visible {{ opacity: 1; }}

/* ── Loading shimmer ─────────────────────────────────────────── */
.shimmer {{
  background: linear-gradient(90deg, var(--bg3) 25%, var(--border) 50%, var(--bg3) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 3px;
  height: 14px;
  width: 100%;
}}

@keyframes shimmer {{
  0%   {{ background-position: 200% 0; }}
  100% {{ background-position: -200% 0; }}
}}

/* ── Progress dots ───────────────────────────────────────────── */
.progress-dots {{
  display: flex;
  gap: 6px;
  align-items: center;
}}

.dot {{
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--subtle);
  transition: background 0.3s;
}}

.dot.done    {{ background: var(--confirm); }}
.dot.current {{ background: var(--accent); }}
.dot.partial {{ background: var(--partial); }}
</style>
</head>
<body>

<!-- Top bar -->
<div class="topbar">
  <div class="topbar-left">
    <span class="logo">ConnectionSphere</span>
    <span class="separator">/</span>
    <span class="problem-title">{problem}</span>
  </div>
  <div class="topbar-right">
    <span class="timer" id="timer">00:00</span>
    <div class="progress-dots" id="progress-dots"></div>
    <span class="fsm-badge active" id="fsm-badge">{fsm_state}</span>
  </div>
</div>

<!-- Layout -->
<div class="layout">

  <!-- Left: Interviewer -->
  <div class="left-panel">
    <div class="panel-header">
      <span class="panel-label" id="agent-name-label">{agent_name}</span>
      <span class="panel-role" id="agent-role-label">{agent_role}</span>
      <div class="speaking-dot" id="speaking-dot"></div>
    </div>
    <div class="scene-text" id="scene-text">{scene}</div>
    <div class="question-area">
      <div class="question-label">Current question</div>
      <div class="question-text" id="question-text">
        <div class="shimmer" style="margin-bottom:8px"></div>
        <div class="shimmer" style="width:80%;margin-bottom:8px"></div>
        <div class="shimmer" style="width:60%"></div>
      </div>
    </div>
    <div class="teach-actions" id="teach-actions" style="display:none;padding:12px 24px;border-top:1px solid var(--border);">
      <button class="next-btn" id="ready-btn" onclick="handoverToJordan()" style="width:100%;text-align:center;">
        Ready for interview →
      </button>
    </div>
    <div class="audio-bar">
      <button id="audio-play-btn" onclick="toggleAudioPlayback()" style="background:none;border:1px solid var(--border);color:var(--muted);font-family:'DM Mono',monospace;font-size:11px;letter-spacing:0.08em;padding:4px 10px;border-radius:3px;cursor:pointer;min-width:36px;display:none;">▶</button>
      <div class="audio-progress" style="cursor:default;">
        <div class="audio-fill" id="audio-fill"></div>
      </div>
      <span class="audio-label" id="audio-label">—</span>
    </div>
  </div>

  <!-- Right: Candidate -->
  <div class="right-panel">
    <div class="candidate-header">
      <span class="candidate-name">{name}</span>
      <div style="display:flex;align-items:center;gap:12px;">
        <span class="stage-indicator" id="stage-indicator">Stage —</span>
        <button id="back-to-alex-btn" onclick="backToAlex()" style="display:none;background:none;border:1px solid var(--border);color:var(--muted);font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.1em;padding:3px 10px;border-radius:3px;cursor:pointer;">← Alex</button>
      </div>
    </div>

    <div class="answer-area">
      <div class="waveform" id="waveform">
        {''.join('<div class="wave-bar" id="wb' + str(i) + '"></div>' for i in range(24))}
      </div>

      <button class="record-btn" id="record-btn" onclick="toggleRecording()" disabled>
        <div class="record-icon"></div>
      </button>

      <div class="record-hint" id="record-hint">Loading stage…</div>
      <div class="transcript-preview" id="transcript-preview"></div>
      <div class="status-overlay" id="status-overlay"></div>
    </div>

    <div class="assessment" id="assessment"></div>
    <div class="whiteboard" id="whiteboard">
      <!-- Banner: coloured prompt strip, toggled by activateWhiteboard() -->
      <div class="whiteboard-banner mode-alex" id="whiteboard-banner" style="display:none">
        <span class="whiteboard-banner-dot"></span>
        <span id="whiteboard-banner-text">Sketch this out</span>
      </div>

      <!-- Reference diagram: fetched from /concept/{id}/diagram on activation -->
      <div class="whiteboard-reference" id="whiteboard-reference">
        <div class="whiteboard-reference-label">reference diagram</div>
        <div id="whiteboard-reference-inner">
          <div class="whiteboard-reference-loading">loading…</div>
        </div>
      </div>

      <!-- Drop zone + thumbnails -->
      <div class="whiteboard-controls">
        <input type="file" id="whiteboard-input" accept="image/*" multiple style="display:none" onchange="handleWhiteboardUpload(event)">
        <div class="whiteboard-drop" id="whiteboard-drop" onclick="document.getElementById('whiteboard-input').click()">
          <span class="whiteboard-label">+ diagram</span>
        </div>
        <div class="whiteboard-thumbs" id="whiteboard-thumbs"></div>
      </div>
    </div>

    <!-- Gate hint: shown below record button when diagram required but missing -->
    <div class="diagram-gate-hint" id="diagram-gate-hint">upload a diagram to continue</div>
  </div>

</div>

<audio id="stage-audio" style="display:none"></audio>
<div class="whiteboard-lightbox" id="whiteboard-lightbox" onclick="this.classList.remove('open')">
  <img src="" alt="diagram">
</div>

<script>
const SESSION_ID = {json.dumps(session_id)};
  const playedAudio = new Set();
let currentStage   = 1;
let isRecording    = false;
let mediaRecorder  = null;
let audioChunks    = [];
let timerInterval  = null;
let elapsedSeconds = 0;
let stageData      = null;
let analyser       = null;
let animFrame      = null;
let audioCtx       = null;

// ── Timer ────────────────────────────────────────────────────────
function startTimer() {{
  timerInterval = setInterval(() => {{
    elapsedSeconds++;
    const m = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
    const s = String(elapsedSeconds % 60).padStart(2, '0');
    document.getElementById('timer').textContent = m + ':' + s;
  }}, 1000);
}}

// ── Load stage ───────────────────────────────────────────────────
async function loadStage(n) {{
  currentStage = n;
  document.getElementById('stage-indicator').textContent = 'Stage ' + n;
  document.getElementById('record-btn').disabled = true;
  document.getElementById('record-hint').textContent = 'Loading stage…';
  document.getElementById('assessment').className = 'assessment';

  const qt = document.getElementById('question-text');
  qt.className = 'question-text';
  qt.innerHTML = '<div class="shimmer" style="margin-bottom:8px"></div><div class="shimmer" style="width:80%;margin-bottom:8px"></div><div class="shimmer" style="width:60%"></div>';

  try {{
    const res  = await fetch(`/session/${{SESSION_ID}}/stage/${{n}}`);
    stageData  = await res.json();

    // Show question + scene based on phase
    const isTeach = (stageData.phase === 'teach');
    qt.innerHTML  = isTeach ? (stageData.comprehension_check || '') : (stageData.opening_question || '');

    // ── Whiteboard: activate for Alex drawing comprehension check ─────────
    deactivateWhiteboard();  // always reset first on stage load
    if (isTeach && stageData.comprehension_check_mode === 'drawing') {{
      activateWhiteboard({{
        by:        'alex',
        required:  true,
        prompt:    'Sketch this before we move on',
        conceptId: stageData.concept_id || null,
        rubric:    stageData.drawing_rubric || [],
      }});
    }}
    // Swap scene text: Alex's lesson during teach, Jordan's scenario during interview
    const sceneEl = document.getElementById('scene-text');
    if (isTeach && stageData.greeting) {{
      const concepts = stageData.concepts || [];
      const conceptHtml = concepts.length
        ? '<ul style="margin-top:12px;padding-left:16px;">' + concepts.map(c => '<li style="margin-bottom:8px;">' + (c.name || c) + ': ' + (c.explanation || '') + '</li>').join('') + '</ul>'
        : '';
      sceneEl.innerHTML = '<strong>' + stageData.greeting + '</strong>' + conceptHtml;
    }} else {{
      sceneEl.textContent = stageData.scene || '';
    }}
    if (stageData.agent_name) {{ document.getElementById('agent-name-label').textContent = stageData.agent_name; document.getElementById('agent-role-label').textContent = stageData.agent_role || ''; }}
    qt.className  = 'question-text visible';

    // Update FSM badge
    document.getElementById('fsm-badge').textContent = stageData.fsm_state;
    // Show/hide teach vs interview UI
    const teachActions = document.getElementById('teach-actions');
    const backBtn = document.getElementById('back-to-alex-btn');
    if (stageData.phase === 'teach') {{
      teachActions.style.display = 'block';
      backBtn.style.display = 'none';
    }} else {{
      teachActions.style.display = 'none';
      backBtn.style.display = 'inline-block';
    }}
    // Enable record button immediately, audio plays in background
    enableRecording();
    // Autoplay once per stage+phase; show play button on revisit
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    const playBtn  = document.getElementById('audio-play-btn');
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }} else {{
      // Revisit — preload audio and show play button
      const audio = document.getElementById('stage-audio');
      audio.src   = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;
      if (playBtn) {{ playBtn.textContent = '▶'; playBtn.style.display = 'inline-block'; }}
    }}

  }} catch(e) {{
    qt.innerHTML = 'Failed to load stage. ' + e.message;
    qt.className = 'question-text visible';
  }}
}}

// ── Audio playback ───────────────────────────────────────────────
async function playStageAudio(n) {{
  const dot      = document.getElementById('speaking-dot');
  const fill     = document.getElementById('audio-fill');
  const label    = document.getElementById('audio-label');
  const audio    = document.getElementById('stage-audio');
  const playBtn  = document.getElementById('audio-play-btn');

  dot.className    = 'speaking-dot active';
  fill.style.width = '0%';
  label.textContent = '';
  if (playBtn) playBtn.style.display = 'none';

  audio.src = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;

  audio.ontimeupdate = () => {{
    if (audio.duration) {{
      fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
      const rem = Math.ceil(audio.duration - audio.currentTime);
      label.textContent = rem + 's';
    }}
  }};

  audio.onended = () => {{
    dot.className    = 'speaking-dot';
    fill.style.width = '100%';
    label.textContent = '';
    if (playBtn) {{ playBtn.textContent = '▶'; playBtn.style.display = 'inline-block'; }}
    enableRecording();
  }};

  audio.onerror = () => {{
    dot.className = 'speaking-dot';
    label.textContent = 'no audio';
    enableRecording();
  }};

  setTimeout(() => {{ if (!audio.ended) enableRecording(); }}, 60000);
  audio.play().catch(() => {{ label.textContent = 'no audio'; enableRecording(); }});
}}

function handleWhiteboardUpload(event) {{
  const files = Array.from(event.target.files);
  const thumbs = document.getElementById('whiteboard-thumbs');
  files.forEach(file => {{
    const reader = new FileReader();
    reader.onload = e => {{
      const thumb = document.createElement('div');
      thumb.className = 'whiteboard-thumb';
      const img = document.createElement('img');
      img.src = e.target.result;
      img.title = file.name;
      img.onclick = () => openLightbox(e.target.result);
      const del = document.createElement('button');
      del.className = 'thumb-del';
      del.textContent = '✕';
      del.onclick = ev => {{
        ev.stopPropagation();
        thumb.remove();
        updateSubmitGate();   // re-evaluate gate after removal
      }};
      thumb.appendChild(img);
      thumb.appendChild(del);
      thumbs.appendChild(thumb);
      updateSubmitGate();   // ungate if diagram requirement now satisfied
    }};
    reader.readAsDataURL(file);
  }});
  event.target.value = '';
}}
function openLightbox(src) {{
  const lb = document.getElementById('whiteboard-lightbox');
  lb.querySelector('img').src = src;
  lb.classList.add('open');
}}
function toggleAudioPlayback() {{
  const audio   = document.getElementById('stage-audio');
  const playBtn = document.getElementById('audio-play-btn');
  const dot     = document.getElementById('speaking-dot');
  if (audio.paused) {{
    audio.play();
    playBtn.textContent = '❙❙';
    dot.className = 'speaking-dot active';
  }} else {{
    audio.pause();
    playBtn.textContent = '▶';
    dot.className = 'speaking-dot';
  }}
}}

function enableRecording() {{
  const btn  = document.getElementById('record-btn');
  const hint = document.getElementById('record-hint');
  btn.disabled = false;
  hint.textContent = 'Click to answer';
}}

// ── Recording ────────────────────────────────────────────────────
async function toggleRecording() {{
  if (isRecording) {{
    stopRecording();
  }} else {{
    await startRecording();
  }}
}}

async function startRecording() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    audioChunks  = [];
    mediaRecorder = new MediaRecorder(stream);

    // Waveform analyser
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);
    drawWaveform();

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop          = submitAudio;
    mediaRecorder.start();

    isRecording = true;
    document.getElementById('record-btn').className  = 'record-btn recording';
    document.getElementById('record-hint').textContent = 'Recording… click to stop';
    document.getElementById('waveform').className    = 'waveform active';
    document.getElementById('transcript-preview').className = 'transcript-preview';

  }} catch(e) {{
    showStatus('Microphone access denied');
  }}
}}

function stopRecording() {{
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {{
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
  }}
  if (animFrame) cancelAnimationFrame(animFrame);
  if (audioCtx)  audioCtx.close();
  isRecording = false;
  document.getElementById('record-btn').className  = 'record-btn';
  document.getElementById('record-hint').textContent = 'Processing…';
  document.getElementById('waveform').className    = 'waveform';
}}

function drawWaveform() {{
  const bars = document.querySelectorAll('.wave-bar');
  const data = new Uint8Array(analyser.frequencyBinCount);

  function draw() {{
    animFrame = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(data);
    bars.forEach((bar, i) => {{
      const v = (data[i] || 0) / 255;
      bar.style.height = Math.max(4, v * 32) + 'px';
    }});
  }}
  draw();
}}

// ── Submit audio ─────────────────────────────────────────────────
async function submitAudio() {{
  // ── Diagram gate: block submission if drawing is required but not uploaded ─
  if (diagramRequired) {{
    const thumbCount = document.querySelectorAll('.whiteboard-thumb').length;
    if (thumbCount === 0) {{
      updateSubmitGate();   // re-flash the gate hint
      return;               // don't submit
    }}
  }}

  const blob = new Blob(audioChunks, {{ type: 'audio/webm' }});
  // Attach any whiteboard images
  const thumbImgs = document.querySelectorAll('.whiteboard-thumb img');
  const imageFiles = [];
  for (const img of thumbImgs) {{
    const res  = await fetch(img.src);
    const blob = await res.blob();
    imageFiles.push(new File([blob], 'diagram.png', {{type: blob.type}}));
  }}
  const form = new FormData();
  imageFiles.forEach(f => form.append('images', f));
  form.append('audio', blob, 'answer.webm');

  showStatus('Transcribing…');

  try {{
    const isTeachPhase = stageData && stageData.phase === 'teach';
    const submitUrl = isTeachPhase
      ? `/session/${{SESSION_ID}}/teach/ask`
      : `/session/${{SESSION_ID}}/stage/${{currentStage}}/voice`;
    const res        = await fetch(submitUrl, {{
      method: 'POST',
      body:   form,
    }});
    const assessment = await res.json();

    if (!res.ok) {{
      showStatus(assessment.detail || 'Error submitting');
      enableRecording();
      return;
    }}

    showTranscript(assessment.transcript || '');
    renderAssessment(assessment);

  }} catch(e) {{
    showStatus('Submission failed: ' + e.message);
    enableRecording();
  }}
}}

// ── Render assessment ────────────────────────────────────────────

async function speakResponse(spokenText) {{
  if (!spokenText) return;
  const dot   = document.getElementById('speaking-dot');
  const fill  = document.getElementById('audio-fill');
  const label = document.getElementById('audio-label');
  const audio = document.getElementById('stage-audio');

  dot.className = 'speaking-dot active';
  label.textContent = '▶ response';

  try {{
    const voiceId = stageData && stageData.phase === 'teach' ? 'ALEX_VOICE' : '';
    const res  = await fetch(`/session/${{SESSION_ID}}/speak`, {{
      method:  'POST',
      headers: {{'Content-Type': 'application/json'}},
      body:    JSON.stringify({{ text: spokenText, voice_id: voiceId }}),
    }});
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    audio.src  = url;
    audio.addEventListener('timeupdate', () => {{
      if (audio.duration) {{
        fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
        label.textContent = Math.ceil(audio.duration - audio.currentTime) + 's';
      }}
    }});
    audio.addEventListener('ended', () => {{
      dot.className = 'speaking-dot';
      label.textContent = '✓ done';
      URL.revokeObjectURL(url);
    }}, {{ once: true }});
    await audio.play();
  }} catch(e) {{
    dot.className = 'speaking-dot';
    label.textContent = '—';
  }}
}}

function renderAssessment(a) {{
  const panel   = document.getElementById('assessment');
  const verdict = a.verdict || 'NOT_MET';
  const shown   = a.concepts_demonstrated || [];
  const missing = a.concepts_missing || [];

  let html = `
    <div class="verdict-row">
      <span class="verdict-tag verdict-${{verdict}}">${{verdict}}</span>
    </div>
    <p class="feedback-text">${{a.feedback || ''}}</p>
  `;

  if (verdict === 'PARTIAL' && a.probe) {{
    html += `<div class="probe-text">${{a.probe}}</div>`;
  }}

  // ── Diagram request: Jordan is asking the candidate to draw ───────────
  if (a.diagram_request && a.diagram_request.required) {{
    const dr = a.diagram_request;
    activateWhiteboard({{
      by:        'jordan',
      required:  true,
      prompt:    dr.prompt || 'Draw the architecture — upload your diagram',
      conceptId: dr.concept_id || null,
      rubric:    dr.rubric   || [],
    }});
  }} else if (a.diagram_request && !a.diagram_request.required) {{
    // Suggested but not mandatory
    activateWhiteboard({{
      by:        'jordan',
      required:  false,
      prompt:    a.diagram_request.prompt || 'Diagrams welcome — upload if you have one',
      conceptId: a.diagram_request.concept_id || null,
      rubric:    a.diagram_request.rubric    || [],
    }});
  }}

  // ── Diagram evaluation rubric (when Jordan scored a submitted drawing) ─
  if (a.diagram_scores && currentRubric.length > 0) {{
    html += renderRubric(currentRubric, a.diagram_scores);
  }} else if (a.diagram_scores && a.diagram_scores.length > 0) {{
    // Rubric not in client state — render scores without labels
    const icons = {{ PRESENT: '✓', PARTIAL: '◐', MISSING: '✗' }};
    const scoreHtml = a.diagram_scores.map(s =>
      `<div class="rubric-item">
         <span class="rubric-icon ${{s.status.toLowerCase()}}">${{icons[s.status] || '○'}}</span>
         <span class="rubric-text">${{s.label}}</span>
       </div>`
    ).join('');
    html += `<div class="rubric-list">${{scoreHtml}}</div>`;
  }}

  if (shown.length || missing.length) {{
    html += '<div class="concepts-row">';
    shown.forEach(c   => html += `<span class="concept-chip confirmed">+ ${{c}}</span>`);
    missing.forEach(c => html += `<span class="concept-chip">- ${{c}}</span>`);
    html += '</div>';
  }}

  if (verdict === 'CONFIRMED') {{
    const nextStage = currentStage + 1;
    if (a.next_url && a.next_url.includes('evaluate')) {{
      html += `<button class="next-btn" onclick="goEvaluate()">View results →</button>`;
    }} else {{
      html += `<button class="next-btn" onclick="advanceStage(${{nextStage}})">Next stage →</button>`;
      // Auto-advance after 3s
      setTimeout(() => advanceStage(nextStage), 3000);
    }}
  }} else if (verdict === 'PARTIAL') {{
    html += `<button class="next-btn" onclick="resetForProbe()">Answer follow-up →</button>`;
  }} else {{
    html += `<button class="next-btn" onclick="resetForProbe()">Try again →</button>`;
  }}

  // During TEACH phase, show as Alex chat reply not Jordan verdict
  if (stageData && stageData.phase === 'teach') {{
    const alexReply = a.probe || a.feedback || '';
    panel.innerHTML = `<div style="font-size:13px;color:#bbb;line-height:1.7;border-left:2px solid var(--accent);padding-left:12px;">${{alexReply}}</div>
      <button class="next-btn" onclick="resetForProbe()" style="margin-top:8px;">Ask another question</button>`;
    panel.className = 'assessment visible';
    speakResponse(alexReply.split('.').slice(0,2).join('.') + '.');
    return;
  }}

  panel.innerHTML   = html;
  panel.className   = 'assessment visible';
  const toSpeak = (verdict === 'PARTIAL' && a.probe) ? a.probe : (a.feedback || '').split('.').slice(0,2).join('.') + '.';
  speakResponse(toSpeak);


  document.getElementById('record-hint').textContent = '';
  showStatus('');
}}

async function handoverToJordan() {{
  const btn = document.getElementById('ready-btn');
  btn.disabled = true;
  btn.textContent = 'Handing over…';
  try {{
    const audio = document.getElementById('stage-audio');
    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}
    await fetch(`/session/${{SESSION_ID}}/teach/complete`, {{method:'POST'}});
  }} catch(e) {{}}
  advanceStage(currentStage);
}}

async function backToAlex() {{
  const btn = document.getElementById('back-to-alex-btn');
  btn.disabled = true;
  btn.textContent = '…';
  try {{
    const audio = document.getElementById('stage-audio');
    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}
    await fetch(`/session/${{SESSION_ID}}/teach/restart`, {{method:'POST'}});
  }} catch(e) {{}}
  btn.disabled = false;
  btn.textContent = '← Alex';
  // Re-enable the handover button
  const readyBtn = document.getElementById('ready-btn');
  if (readyBtn) {{ readyBtn.disabled = false; readyBtn.textContent = 'Ready for interview →'; }}
  loadStage(1);
}}

function advanceStage(n) {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  deactivateWhiteboard();
  loadStage(n);
}}

function resetForProbe() {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  // Keep whiteboard open on probe — candidate may still be drawing
  // But reset the gate so they can re-answer verbally if the diagram is uploaded
  updateSubmitGate();
  enableRecording();
  document.getElementById('record-hint').textContent = 'Answer the follow-up';
}}

function goEvaluate() {{
  window.location.href = `/session/${{SESSION_ID}}/evaluate`;
}}

// ── Helpers ──────────────────────────────────────────────────────
function showStatus(msg) {{
  const el = document.getElementById('status-overlay');
  el.textContent = msg;
  el.className   = msg ? 'status-overlay visible' : 'status-overlay';
}}

function showTranscript(text) {{
  const el = document.getElementById('transcript-preview');
  if (text) {{
    el.textContent = '"' + text.slice(0, 120) + (text.length > 120 ? '…' : '') + '"';
    el.className   = 'transcript-preview visible';
  }}
}}

// ── Whiteboard state ─────────────────────────────────────────────
let diagramRequired    = false;   // true → submit gated until ≥1 thumb
let diagramRequiredBy  = null;    // 'alex' | 'jordan' | null
let currentRubric      = [];      // DrawingRubricItem list from last diagram_request
let referenceConceptId = null;    // concept_id currently shown as reference

// ── Whiteboard: activate ─────────────────────────────────────────
function activateWhiteboard(opts = {{}}) {{
  /*
    opts:
      by        — 'alex' | 'jordan'          (default 'alex')
      required  — bool                        (default false)
      prompt    — string shown in banner      (default by-mode)
      conceptId — string, loads reference SVG (default null)
      rubric    — array of rubric items       (default [])
  */
  const by       = opts.by       || 'alex';
  const required = opts.required || false;
  const conceptId = opts.conceptId || null;
  currentRubric   = opts.rubric  || [];

  const panel  = document.getElementById('whiteboard');
  const banner = document.getElementById('whiteboard-banner');
  const btext  = document.getElementById('whiteboard-banner-text');

  panel.classList.add('active');
  banner.style.display = 'flex';

  // Banner mode class
  banner.className = 'whiteboard-banner mode-' + (required ? 'required' : by);
  panel.classList.toggle('mode-required', required);

  // Banner text
  const defaultPrompts = {{
    alex:   'Sketch this out for me',
    jordan: 'Draw it out — show me the architecture',
  }};
  btext.textContent = opts.prompt || defaultPrompts[by] || 'Upload your diagram';

  // Gate state
  diagramRequired   = required;
  diagramRequiredBy = by;

  // Reference diagram
  if (conceptId && conceptId !== referenceConceptId) {{
    referenceConceptId = conceptId;
    loadReferenceDiagram(conceptId);
  }} else if (!conceptId) {{
    document.getElementById('whiteboard-reference').classList.remove('visible');
  }}

  updateSubmitGate();
}}

// ── Whiteboard: deactivate ────────────────────────────────────────
function deactivateWhiteboard() {{
  const panel  = document.getElementById('whiteboard');
  const banner = document.getElementById('whiteboard-banner');

  panel.classList.remove('active', 'mode-required');
  banner.style.display = 'none';
  document.getElementById('whiteboard-reference').classList.remove('visible');
  document.getElementById('whiteboard-thumbs').innerHTML = '';

  diagramRequired    = false;
  diagramRequiredBy  = null;
  currentRubric      = [];
  referenceConceptId = null;

  updateSubmitGate();
}}

// ── Submit gate: disable record button when diagram required but absent ───────
function updateSubmitGate() {{
  const btn      = document.getElementById('record-btn');
  const hint     = document.getElementById('diagram-gate-hint');
  const thumbs   = document.querySelectorAll('.whiteboard-thumb');
  const hasDrawing = thumbs.length > 0;

  const blocked = diagramRequired && !hasDrawing;

  btn.classList.toggle('diagram-pending', blocked);
  if (hint) hint.classList.toggle('visible', blocked);

  // Also update the banner colour to reflect pending state
  const banner = document.getElementById('whiteboard-banner');
  if (diagramRequired && banner) {{
    banner.className = 'whiteboard-banner mode-' + (blocked ? 'required' : diagramRequiredBy);
  }}
}}

// ── Load reference diagram from /concept/{id}/diagram ────────────
async function loadReferenceDiagram(conceptId) {{
  const refPanel = document.getElementById('whiteboard-reference');
  const inner    = document.getElementById('whiteboard-reference-inner');

  refPanel.classList.add('visible');
  inner.innerHTML = '<div class="whiteboard-reference-loading">loading reference…</div>';

  try {{
    const res = await fetch(`/concept/${{conceptId}}/diagram`);
    if (!res.ok) throw new Error('not found');
    const svg = await res.text();
    inner.innerHTML = svg;
    // Constrain the inline SVG to the panel width
    const svgEl = inner.querySelector('svg');
    if (svgEl) {{
      svgEl.style.width    = '100%';
      svgEl.style.height   = 'auto';
      svgEl.style.maxHeight = '160px';
      svgEl.style.display  = 'block';
    }}
  }} catch (e) {{
    // Non-fatal — hide the reference slot silently
    refPanel.classList.remove('visible');
    inner.innerHTML = '';
  }}
}}

// ── Rubric checklist renderer (called from renderAssessment) ─────
function renderRubric(rubric, scores) {{
  /*
    rubric: array of {{ label, description, required }}
    scores: array of {{ label, status }}  — status: PRESENT | PARTIAL | MISSING
    Returns HTML string for the rubric checklist.
  */
  if (!rubric || rubric.length === 0) return '';

  const scoreMap = {{}};
  (scores || []).forEach(s => {{ scoreMap[s.label] = s.status; }});

  const iconMap = {{
    PRESENT: {{ icon: '✓', cls: 'present' }},
    PARTIAL: {{ icon: '◐', cls: 'partial' }},
    MISSING: {{ icon: '✗', cls: 'missing'  }},
  }};

  const items = rubric.map(item => {{
    const status = scoreMap[item.label] || 'unknown';
    const ic     = iconMap[status] || {{ icon: '○', cls: 'unknown' }};
    const req    = item.required ? ' required-item' : '';
    return `
      <div class="rubric-item">
        <span class="rubric-icon ${{ic.cls}}">${{ic.icon}}</span>
        <span class="rubric-text${{req}}">${{item.label}}${{item.required ? ' *' : ''}}</span>
      </div>`;
  }}).join('');

  return `
    <div class="rubric-list">
      ${{items}}
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin-top:4px">
        * required element
      </div>
    </div>`;
}}

// ── Boot ─────────────────────────────────────────────────────────
startTimer();
loadStage(1);
</script>
</body>
</html>"""
