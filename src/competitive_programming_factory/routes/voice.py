# ruff: noqa: E501
"""
competitive_programming_factory/routes/voice.py
Voice endpoints — Cartesia TTS + STT.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

import competitive_programming_factory.session_store as store
from competitive_programming_factory.engine import session_engine as engine
from competitive_programming_factory.logging import get_logger
from competitive_programming_factory.voice.stt import transcribe
from competitive_programming_factory.voice.tts import audio_path, generate_tts

router = APIRouter(tags=["voice"])
log = get_logger(__name__)


def _strip_latex(text: str) -> str:
    import re

    text = re.sub(r"\$\$(.+?)\$\$", lambda m: _latex_to_speech(m.group(1)), text, flags=re.DOTALL)
    text = re.sub(r"\$(.+?)\$", lambda m: _latex_to_speech(m.group(1)), text)
    return text


def _latex_to_speech(expr: str) -> str:
    import re

    e = expr.strip()
    e = e.replace("\\geq", "greater than or equal to")
    e = e.replace("\\leq", "less than or equal to")
    e = e.replace("\\neq", "not equal to")
    e = e.replace("\\gcd", "gcd")
    e = e.replace("\\times", "times")
    e = e.replace("\\cdot", "times")
    e = e.replace("\\in", "in")
    e = e.replace("\\mathbb{Z}", "the integers")
    e = e.replace("\\mathbb{N}", "the natural numbers")
    e = e.replace("\\forall", "for all")
    e = e.replace("\\exists", "there exists")
    e = e.replace("\\infty", "infinity")
    e = e.replace("\\to", "to")
    e = e.replace("\\rightarrow", "implies")
    e = e.replace("\\Rightarrow", "implies")
    e = e.replace("\\ldots", "...")
    e = e.replace("\\", "")
    e = re.sub(r"\^{?(\w+)}?", r" to the power \1", e)
    e = re.sub(r"_{?(\w+)}?", r" subscript \1", e)
    return e.strip()


def _stage_text(session_id: str, stage_n: int) -> tuple[str, str]:
    from competitive_programming_factory.config import get_settings as _settings
    from competitive_programming_factory.domain.agents import get_agent_for_state

    spec = engine.get_or_generate_stage(session_id, stage_n)
    state_data = engine.get_state(session_id) or {}
    fsm_state = state_data.get("fsm_state", "")
    agent = get_agent_for_state(fsm_state)
    voice_id = agent.voice_id(_settings())
    store.load_field(session_id, "candidate_first_name") or "there"
    _TEACH_STATES = {
        "Teach",
        "Teach Comprehension Check",
        "Concept Teach",
        "Concept Teach Check",
    }
    _JORDAN_STATES = {"Concept Stage"}
    if fsm_state in _TEACH_STATES:
        greeting = spec.get("greeting", "")
        check = spec.get("comprehension_check", "")
        if fsm_state in {"Concept Teach", "Concept Teach Check"}:
            parts = [p for p in [greeting] if p]
        else:
            parts = [p for p in [greeting, check] if p]
    elif fsm_state in _JORDAN_STATES:
        scene_hook = spec.get("scene_hook", "")
        question = spec.get("opening_question", "")
        parts = [p for p in [scene_hook, question] if p]
    else:
        scene_data = store.load_field(session_id, "scene") or {}
        scene = scene_data.get("scene", "")
        question = spec.get("opening_question", "")
        parts = [p for p in [scene, question] if p]
    return (_strip_latex("  ".join(parts)), voice_id)


@router.get("/session/{session_id}/stage/{stage_n}/audio/file")
async def get_stage_audio_file(session_id: str, stage_n: int):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    _fsm_result = engine.load_session(session_id)
    _TEACH_VALS = {"Teach", "Teach Comprehension Check", "Concept Teach", "Concept Teach Check"}
    _phase = "teach" if (_fsm_result and _fsm_result[0].state.value in _TEACH_VALS) else "interview"
    savepath = audio_path(session_id, stage_n, _phase)
    if not Path(savepath).exists():
        text, voice_id = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath, voice_id=voice_id)
    return Response(
        content=Path(savepath).read_bytes(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )


@router.get("/session/{session_id}/stage/{stage_n}/play", response_class=HTMLResponse)
async def play_stage_audio(session_id: str, stage_n: int):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
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
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    speak_text = _strip_latex(payload.get("text", "").strip())
    if not speak_text:
        raise HTTPException(status_code=422, detail="No text provided")
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        req_voice = payload.get("voice_id", "")
        from competitive_programming_factory.config import get_settings as _settings

        cfg = _settings()
        use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALISTAIR_VOICE" else cfg.cartesia_voice_id
        await generate_tts(speak_text, save_path=tmp, voice_id=use_voice)
        audio = Path(tmp).read_bytes()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )


@router.post("/session/{session_id}/stage/{stage_n}/voice")
async def submit_voice_answer(
    session_id: str,
    stage_n: int,
    audio: UploadFile = File(...),
    images: list[UploadFile] = File(default=[]),
):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/mpeg"
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Audio too short")
    stt_result = await transcribe(audio_bytes, content_type=content_type)

    # Structured result from upgraded STT — use word-level data for quality gating
    if isinstance(stt_result, dict):
        transcript = stt_result["transcript"]
        word_count = stt_result["word_count"]
        duration = stt_result.get("duration")
    else:
        # Fallback for plain string (shouldn't happen after patch)
        transcript = stt_result if isinstance(stt_result, str) else str(stt_result)
        word_count = len(transcript.split())
        duration = None
    if word_count < 8:
        nudge = (
            "Sorry, I didn't catch that — it sounded like the mic cut off. Take your time and answer when you're ready."
        )
        return {
            "verdict": "PARTIAL",
            "feedback": nudge,
            "probe": nudge,
            "transcript": transcript,
            "concepts_demonstrated": [],
            "concepts_missing": [],
            "next_url": f"/session/{session_id}/stage/{stage_n}",
            "session_complete": False,
            "input_mode": "voice",
        }
    if duration and duration < 1.0:
        nudge = "That was very short — make sure your microphone is working and try again."
        return {
            "verdict": "PARTIAL",
            "feedback": nudge,
            "probe": nudge,
            "transcript": transcript,
            "concepts_demonstrated": [],
            "concepts_missing": [],
            "next_url": f"/session/{session_id}/stage/{stage_n}",
            "session_complete": False,
            "input_mode": "voice",
        }

    if len(transcript.strip()) > 4000:
        raise HTTPException(
            status_code=422,
            detail=(
                "That recording was too long to process. Please keep your answer to around 4-5 minutes and try again."
            ),
        )
    image_data = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            import base64

            image_data.append(
                {
                    "media_type": img.content_type or "image/png",
                    "data": base64.b64encode(img_bytes).decode(),
                }
            )
    assessment = engine.process_submission(
        session_id=session_id,
        stage_n=stage_n,
        answer=transcript,
        images=image_data,
    )
    if hasattr(assessment, "model_dump"):
        assessment = assessment.model_dump()
    return {**assessment, "transcript": transcript, "input_mode": "voice"}


@router.get("/session/{session_id}/interview", response_class=HTMLResponse)
async def interview_page(session_id: str):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    state = engine.get_state(session_id)
    scene = store.load_field(session_id, "scene") or {}
    problem = store.load_field(session_id, "problem_statement") or ""
    name = store.load_field(session_id, "candidate_name") or "Candidate"
    agent_name = state.get("agent_name", "Interviewer")
    agent_role = state.get("agent_role", "INTERVIEWER")
    return HTMLResponse(
        content=_interview_html(
            session_id=session_id,
            problem=_latexify(problem),
            name=name,
            scene=scene.get("scene", ""),
            fsm_state=state["fsm_state"],
            phase=state["phase"],
            agent_name=agent_name,
            agent_role=agent_role,
        )
    )


def _latexify(text: str) -> str:
    import re

    if "$" in text:
        return text
    result = text
    result = re.sub(r"([a-zA-Z0-9_]+)\s*>=\s*([a-zA-Z0-9_]+)", r"$\1 \\geq \2$", result)
    result = re.sub(r"([a-zA-Z0-9_]+)\s*<=\s*([a-zA-Z0-9_]+)", r"$\1 \\leq \2$", result)
    result = re.sub(r"([a-zA-Z0-9_]+)\s*!=\s*([a-zA-Z0-9_]+)", r"$\1 \\neq \2$", result)
    result = re.sub(r"(\d+)([a-zA-Z])\s*\+\s*(\d+)([a-zA-Z])", r"$\1\2 + \3\4$", result)
    result = re.sub(r"(\d+)([a-zA-Z])\s*-\s*(\d+)([a-zA-Z])", r"$\1\2 - \3\4$", result)
    return result


def _interview_html(
    session_id,
    problem,
    name,
    scene,
    fsm_state,
    phase,
    agent_name="Interviewer",
    agent_role="INTERVIEWER",
) -> str:
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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},
      {{left: '$', right: '$', display: false}}
    ]
  }});"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {{ renderMath(); }});
function renderMath() {{
  if (typeof renderMathInElement !== 'undefined') {{
    renderMathInElement(document.body, {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '$', right: '$', display: false}}
      ],
      throwOnError: false
    }});
  }}
}}
</script>
<style>
:root {{
  --bg:        #0a0a0a;
  --bg2:       #111111;
  --bg3:       #1a1a1a;
  --border:    #222222;
  --text:      #f0f0f0;
  --muted:     #666666;
  --subtle:    #333333;
  --accent:    #00cfff;
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

/* ── Concept progress pills ──────────────────────────────────── */
.progress-bar {{
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px;
  overflow-x: auto;
  scrollbar-width: none;
  flex: 1;
  min-width: 0;
}}
.progress-bar::-webkit-scrollbar {{ display: none; }}
.concept-pill {{
  flex-shrink: 0;
  height: 6px;
  width: 24px;
  border-radius: 3px;
  background: var(--subtle);
  transition: background 0.3s, width 0.3s;
  cursor: default;
  position: relative;
}}
.concept-pill[title]:hover::after {{
  content: attr(title);
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg3);
  color: var(--text);
  font-size: 10px;
  white-space: nowrap;
  padding: 3px 6px;
  border-radius: 3px;
  border: 1px solid var(--border);
  pointer-events: none;
  z-index: 100;
}}
.concept-pill.confirmed      {{ background: var(--confirm); }}
.concept-pill.current-alex   {{ background: var(--accent);  width: 32px; }}
.concept-pill.current-jordan {{ background: var(--partial); width: 32px; }}
.concept-pill.flagged        {{ background: var(--danger); }}

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
.topbar-left  {{ display: flex; align-items: center; gap: 16px; }}
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
.topbar-right {{ display: flex; align-items: center; gap: 20px; }}
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
  flex-shrink: 0;
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
.question-text.visible {{ opacity: 1; transform: translateY(0); }}
.audio-bar {{
  padding: 12px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
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

/* ── Right panel — candidate ─────────────────────────────────────
   Grid layout: header | answer-area (grows) | assessment | whiteboard | gate-hint
   answer-area always gets its space; bottom panels are capped + scrollable.
   ─────────────────────────────────────────────────────────────── */
.right-panel {{
  display: grid;
  grid-template-rows: auto 1fr auto auto auto;
  overflow: hidden;
}}
.candidate-header {{
  padding: 16px 24px;
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

/* answer-area: centred, never crushed */
.answer-area {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 40px;
  gap: 24px;
  position: relative;
  min-height: 0;   /* allows grid to shrink it gracefully */
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
  flex-shrink: 0;
}}
.record-btn:hover  {{ border-color: var(--accent); background: var(--bg3); }}
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
.record-btn:hover .record-icon {{ background: var(--accent); }}
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
  padding: 16px 20px;
  display: none;
  gap: 10px;
  flex-direction: column;
  max-height: 220px;
  overflow-y: auto;
}}
.assessment.visible {{ display: flex; }}
.verdict-row {{ display: flex; align-items: center; gap: 10px; }}
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
.feedback-text {{ font-size: 13px; color: #bbb; line-height: 1.7; }}
.probe-text {{
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  color: var(--text);
  line-height: 1.7;
  padding: 10px 14px;
  background: var(--bg3);
  border-left: 2px solid var(--partial);
  border-radius: 0 4px 4px 0;
}}
.concepts-row {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.concept-chip {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 3px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--muted);
}}
.concept-chip.confirmed {{ border-color: rgba(0,255,136,0.3); color: var(--confirm); }}
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

/* ── Whiteboard panel ────────────────────────────────────────── */
.whiteboard {{
  border-top: 1px solid var(--border);
  display: none;
  flex-direction: column;
  max-height: 90px;        /* banner + one row of thumbs — compact */
  overflow-y: auto;
}}
.whiteboard.active {{ display: flex; }}

.whiteboard-banner {{
  padding: 7px 16px;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}}
.whiteboard-banner.mode-alex {{
  background: rgba(88, 166, 255, 0.07);
  border-bottom: 1px solid rgba(88, 166, 255, 0.18);
  color: var(--accent);
}}
.whiteboard-banner.mode-alistair {{
  background: rgba(88, 166, 255, 0.07);
  border-bottom: 1px solid rgba(88, 166, 255, 0.18);
  color: var(--accent);
}}
.whiteboard-banner.mode-imogen {{
  background: rgba(255, 170, 0, 0.07);
  border-bottom: 1px solid rgba(255, 170, 0, 0.18);
  color: var(--partial);
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

/* Reference diagram hidden by default — only shown when conceptId provided */
.whiteboard-reference {{ display: none; }}
.whiteboard-reference.visible {{
  display: block;
  padding: 8px 16px 4px;
  border-bottom: 1px solid var(--border);
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
  max-height: 120px;
  object-fit: contain;
  border-radius: 4px;
  border: 1px solid var(--border);
  display: block;
}}
.whiteboard-reference-loading {{
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
}}

/* Drop zone + thumbs row — single compact row */
.whiteboard-controls {{
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
  flex-shrink: 0;
}}
.whiteboard-controls::-webkit-scrollbar {{ display: none; }}
.whiteboard-drop {{
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 5px 12px;
  cursor: pointer;
  transition: border-color 0.2s;
  flex-shrink: 0;
}}
.whiteboard-drop:hover {{ border-color: var(--accent); }}
.whiteboard.mode-required .whiteboard-drop {{ border-color: rgba(255,68,68,0.45); }}
.whiteboard-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.1em;
  pointer-events: none;
}}
.whiteboard-thumbs {{ display: flex; gap: 8px; align-items: center; flex-shrink: 0; }}
.whiteboard-thumb {{
  position: relative; width: 40px; height: 40px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;
}}
.whiteboard-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.whiteboard-thumb .thumb-del {{
  position: absolute; top: 2px; right: 2px;
  background: rgba(0,0,0,0.7); color: var(--muted);
  font-size: 9px; border: none; border-radius: 2px;
  cursor: pointer; padding: 1px 3px; line-height: 1; display: none;
}}
.whiteboard-thumb:hover .thumb-del {{ display: block; }}

/* ── Record button gate ──────────────────────────────────────── */
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
  padding: 4px 0 6px;
  opacity: 0;
  transition: opacity 0.3s;
}}
.diagram-gate-hint.visible {{ opacity: 1; }}

/* ── Rubric checklist ────────────────────────────────────────── */
.rubric-list {{ display: flex; flex-direction: column; gap: 5px; margin-top: 4px; }}
.rubric-item {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.5;
}}
.rubric-icon {{ flex-shrink: 0; margin-top: 1px; font-size: 11px; }}
.rubric-icon.present {{ color: var(--confirm); }}
.rubric-icon.partial {{ color: var(--partial); }}
.rubric-icon.missing {{ color: var(--danger);  }}
.rubric-icon.unknown {{ color: var(--muted);   }}
.rubric-text {{ color: var(--muted); }}
.rubric-text.required-item {{ color: var(--text); }}

/* ── Lightbox ────────────────────────────────────────────────── */
.whiteboard-lightbox {{
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.85); z-index: 1000;
  align-items: center; justify-content: center; cursor: pointer;
}}
.whiteboard-lightbox.open {{ display: flex; }}
.whiteboard-lightbox img {{ max-width: 90vw; max-height: 90vh; border-radius: 4px; object-fit: contain; }}

/* ── Status + transcript overlays ───────────────────────────── */
.status-overlay {{
  position: absolute;
  bottom: 12px;
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
.progress-dots {{ display: flex; gap: 6px; align-items: center; }}
.dot {{
  width: 6px; height: 6px;
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
        Test me →
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
        <span style="color:var(--muted);font-size:11px;">·</span>
        <span class="stage-indicator" id="stage-indicator">Stage —</span>
        <div class="progress-bar" id="progress-bar"></div>
        <button id="back-to-alex-btn" onclick="backToAlex()" style="display:none;background:none;border:1px solid var(--border);color:var(--muted);font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.1em;padding:3px 10px;border-radius:3px;cursor:pointer;">← Alistair</button>
      </div>
    </div>

    <!-- Answer area — always vertically centred, grows to fill available space -->
    <div class="answer-area">
      <div class="waveform" id="waveform">
        {"".join('<div class="wave-bar" id="wb' + str(i) + '"></div>' for i in range(24))}
      </div>
      <button class="record-btn" id="record-btn" onclick="toggleRecording()" disabled>
        <div class="record-icon"></div>
      </button>
      <div class="record-hint" id="record-hint">Loading stage…</div>
      <div class="transcript-preview" id="transcript-preview"></div>
      <div class="status-overlay" id="status-overlay"></div>
    </div>

    <!-- Assessment — capped at 220px, scrolls internally -->
    <div class="assessment" id="assessment"></div>

    <!-- Whiteboard — compact 90px strip: banner + drop zone row -->
    <div class="whiteboard" id="whiteboard">
      <div class="whiteboard-banner mode-alex" id="whiteboard-banner" style="display:none">
        <span class="whiteboard-banner-dot"></span>
        <span id="whiteboard-banner-text">Sketch this out</span>
      </div>
      <div class="whiteboard-reference" id="whiteboard-reference">
        <div class="whiteboard-reference-label">reference diagram</div>
        <div id="whiteboard-reference-inner">
          <div class="whiteboard-reference-loading">loading…</div>
        </div>
      </div>
      <div class="whiteboard-controls">
        <input type="file" id="whiteboard-input" accept="image/*" multiple style="display:none" onchange="handleWhiteboardUpload(event)">
        <div class="whiteboard-drop" id="whiteboard-drop" onclick="document.getElementById('whiteboard-input').click()">
          <span class="whiteboard-label">+ diagram</span>
        </div>
        <div class="whiteboard-thumbs" id="whiteboard-thumbs"></div>
      </div>
    </div>

    <!-- Gate hint -->
    <div class="diagram-gate-hint" id="diagram-gate-hint">upload a diagram to continue</div>

  </div><!-- end .right-panel -->

</div><!-- end .layout -->

<audio id="stage-audio" style="display:none"></audio>
<div class="whiteboard-lightbox" id="whiteboard-lightbox" onclick="this.classList.remove('open')">
  <img src="" alt="diagram">
</div>

<script>
const SESSION_ID   = {json.dumps(session_id)};
const playedAudio  = new Set();
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

// ── Progress bar ─────────────────────────────────────────────────
async function loadProgress() {{
  try {{
    const res  = await fetch(`/session/${{SESSION_ID}}/progress`);
    if (!res.ok) return;
    const data = await res.json();
    const bar  = document.getElementById('progress-bar');
    if (!bar || !data.concepts || !data.concepts.length) return;
    bar.innerHTML = data.concepts.map(c => {{
      let cls  = 'concept-pill';
      const st = c.status;
      if      (st === 'confirmed')                              cls += ' confirmed';
      else if (st === 'flagged')                                cls += ' flagged';
      else if (st === 'current' && data.agent === 'alex')      cls += ' current-alex';
      else if (st === 'current' && data.agent === 'jordan')    cls += ' current-jordan';
      const label = c.concept_id.replace(/_/g,' ').replace(/\w/g,l=>l.toUpperCase());
      return `<div class="${{cls}}" title="${{label}}"></div>`;
    }}).join('');
  }} catch(e) {{ /* non-fatal */ }}
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
    const res = await fetch(`/session/${{SESSION_ID}}/stage/${{n}}`);
    stageData  = await res.json();
    loadProgress();
    if (stageData.stage_title) document.getElementById('stage-indicator').textContent = stageData.stage_title;

    const isTeach = (stageData.phase === 'teach');
    qt.innerHTML  = isTeach ? (stageData.comprehension_check || '') : (stageData.opening_question || '');
    renderMath();

    deactivateWhiteboard();
    if (isTeach && stageData.comprehension_check_mode === 'drawing') {{
      activateWhiteboard({{
        by:        'alex',
        required:  true,
        prompt:    'Outline your proof or sketch before we move on',
        conceptId: stageData.concept_id || null,
        rubric:    stageData.drawing_rubric || [],
      }});
    }} else {{
      activateWhiteboard({{
        by:        'alistair',
        required:  false,
        prompt:    'Upload written work, a proof sketch, or a diagram — optional',
        conceptId: stageData.concept_id || null,
        rubric:    stageData.drawing_rubric || [],
      }});
    }}

    const sceneEl = document.getElementById('scene-text');
    if (isTeach && stageData.greeting) {{
      const concepts = stageData.concepts || [];
      const conceptHtml = concepts.length
        ? '<ul style="margin-top:12px;padding-left:16px;">' + concepts.map(c =>
            '<li style="margin-bottom:8px;">' + (c.name || c) + ': ' + (c.explanation || '') + '</li>'
          ).join('') + '</ul>'
        : '';
      sceneEl.innerHTML = '<strong>' + stageData.greeting + '</strong>' + conceptHtml;
      renderMath();
    }} else {{
      sceneEl.innerHTML = stageData.scene || '';
      renderMath();
    }}

    if (stageData.agent_name) {{
      document.getElementById('agent-name-label').textContent = stageData.agent_name;
      document.getElementById('agent-role-label').textContent = stageData.agent_role || '';
    }}
    qt.className = 'question-text visible';
    document.getElementById('fsm-badge').textContent = stageData.fsm_state;

    const teachActions = document.getElementById('teach-actions');
    const backBtn      = document.getElementById('back-to-alex-btn');
    if (stageData.phase === 'teach') {{
      teachActions.style.display = 'block';
      backBtn.style.display      = 'none';
    }} else {{
      teachActions.style.display = 'none';
      backBtn.style.display      = 'inline-block';
    }}

    enableRecording();
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    const playBtn  = document.getElementById('audio-play-btn');
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }} else {{
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
  const dot     = document.getElementById('speaking-dot');
  const fill    = document.getElementById('audio-fill');
  const label   = document.getElementById('audio-label');
  const audio   = document.getElementById('stage-audio');
  const playBtn = document.getElementById('audio-play-btn');

  dot.className     = 'speaking-dot active';
  fill.style.width  = '0%';
  label.textContent = '';
  if (playBtn) playBtn.style.display = 'none';

  audio.src = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;
  audio.ontimeupdate = () => {{
    if (audio.duration) {{
      fill.style.width  = (audio.currentTime / audio.duration * 100) + '%';
      label.textContent = Math.ceil(audio.duration - audio.currentTime) + 's';
    }}
  }};
  audio.onended = () => {{
    dot.className     = 'speaking-dot';
    fill.style.width  = '100%';
    label.textContent = '';
    if (playBtn) {{ playBtn.textContent = '▶'; playBtn.style.display = 'inline-block'; }}
    enableRecording();
  }};
  audio.onerror = () => {{
    dot.className     = 'speaking-dot';
    label.textContent = 'no audio';
    enableRecording();
  }};
  setTimeout(() => {{ if (!audio.ended) enableRecording(); }}, 60000);
  audio.play().catch(() => {{
    if (playBtn) {{ playBtn.textContent = '▶ Play audio'; playBtn.style.display = 'inline-block'; }}
    label.textContent = 'tap ▶ to hear';
    enableRecording();
  }});
}}

function handleWhiteboardUpload(event) {{
  const files  = Array.from(event.target.files);
  const thumbs = document.getElementById('whiteboard-thumbs');
  files.forEach(file => {{
    const reader = new FileReader();
    reader.onload = e => {{
      const thumb = document.createElement('div');
      thumb.className = 'whiteboard-thumb';
      const img = document.createElement('img');
      img.src   = e.target.result;
      img.title = file.name;
      img.onclick = () => openLightbox(e.target.result);
      const del = document.createElement('button');
      del.className   = 'thumb-del';
      del.textContent = '✕';
      del.onclick = ev => {{ ev.stopPropagation(); thumb.remove(); updateSubmitGate(); }};
      thumb.appendChild(img);
      thumb.appendChild(del);
      thumbs.appendChild(thumb);
      updateSubmitGate();
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
  btn.disabled     = false;
  hint.textContent = 'Click to answer';
}}

// ── Recording ────────────────────────────────────────────────────
async function toggleRecording() {{
  if (isRecording) {{ stopRecording(); }} else {{ await startRecording(); }}
}}

async function startRecording() {{
  try {{
    const stream  = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    audioChunks   = [];
    mediaRecorder = new MediaRecorder(stream);
    audioCtx      = new AudioContext();
    const source  = audioCtx.createMediaStreamSource(stream);
    analyser      = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);
    drawWaveform();
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop          = submitAudio;
    mediaRecorder.start();
    isRecording = true;
    document.getElementById('record-btn').className   = 'record-btn recording';
    document.getElementById('record-hint').textContent = 'Recording… click to stop';
    document.getElementById('waveform').className     = 'waveform active';
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
  document.getElementById('record-btn').className   = 'record-btn';
  document.getElementById('record-hint').textContent = 'Processing…';
  document.getElementById('waveform').className     = 'waveform';
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
  if (diagramRequired) {{
    const thumbCount = document.querySelectorAll('.whiteboard-thumb').length;
    if (thumbCount === 0) {{ updateSubmitGate(); return; }}
  }}
  const blob      = new Blob(audioChunks, {{ type: 'audio/webm' }});
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
    const submitUrl    = isTeachPhase
      ? `/session/${{SESSION_ID}}/teach/ask`
      : `/session/${{SESSION_ID}}/stage/${{currentStage}}/voice`;
    const res        = await fetch(submitUrl, {{ method: 'POST', body: form }});
    const assessment = await res.json();
    if (!res.ok) {{ showStatus(assessment.detail || 'Error submitting'); enableRecording(); return; }}
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
  dot.className     = 'speaking-dot active';
  label.textContent = '▶ response';
  try {{
    const voiceId = stageData && stageData.phase === 'teach' ? 'ALISTAIR_VOICE' : '';
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
        fill.style.width  = (audio.currentTime / audio.duration * 100) + '%';
        label.textContent = Math.ceil(audio.duration - audio.currentTime) + 's';
      }}
    }});
    audio.addEventListener('ended', () => {{
      dot.className     = 'speaking-dot';
      label.textContent = '✓ done';
      URL.revokeObjectURL(url);
    }}, {{ once: true }});
    await audio.play();
  }} catch(e) {{
    dot.className     = 'speaking-dot';
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

  // Activate whiteboard after assessment so it's always visible
  if (a.diagram_request && a.diagram_request.required) {{
    const dr = a.diagram_request;
    activateWhiteboard({{
      by:        'imogen',
      required:  true,
      prompt:    dr.prompt || 'Write out your proof — upload before submitting',
      conceptId: dr.concept_id || null,
      rubric:    dr.rubric   || [],
    }});
  }} else {{
    activateWhiteboard({{
      by:        'imogen',
      required:  false,
      prompt:    a.diagram_request
        ? (a.diagram_request.prompt || 'Written work welcome — upload if you have it')
        : 'Upload written work or a proof sketch — optional',
      conceptId: a.diagram_request ? (a.diagram_request.concept_id || null) : null,
      rubric:    a.diagram_request ? (a.diagram_request.rubric    || []) : [],
    }});
  }}

  if (a.diagram_scores && currentRubric.length > 0) {{
    html += renderRubric(currentRubric, a.diagram_scores);
  }} else if (a.diagram_scores && a.diagram_scores.length > 0) {{
    const icons = {{ PRESENT: '✓', PARTIAL: '◐', MISSING: '✗' }};
    html += '<div class="rubric-list">' + a.diagram_scores.map(s =>
      `<div class="rubric-item">
         <span class="rubric-icon ${{s.status.toLowerCase()}}">${{icons[s.status] || '○'}}</span>
         <span class="rubric-text">${{s.label}}</span>
       </div>`
    ).join('') + '</div>';
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
      setTimeout(() => advanceStage(nextStage), 3000);
    }}
  }} else if (verdict === 'PARTIAL') {{
    html += `<button class="next-btn" onclick="resetForProbe()">Answer follow-up →</button>`;
  }} else {{
    html += `<button class="next-btn" onclick="resetForProbe()">Try again →</button>`;
  }}

  // Teach phase: Alistair chat-style reply
  if (stageData && stageData.phase === 'teach') {{
    const alexReply = a.probe || a.feedback || '';
    panel.innerHTML = `
      <div style="font-size:13px;color:#bbb;line-height:1.7;border-left:2px solid var(--accent);padding-left:12px;">${{alexReply}}</div>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <button class="next-btn" onclick="resetForProbe()">Ask another question</button>
        <button class="next-btn" onclick="document.getElementById('whiteboard-input').click()"
          style="background:var(--bg3);border:1px solid var(--border);color:var(--muted);">+ written work</button>
      </div>`;
    panel.className = 'assessment visible';
    speakResponse(alexReply.split('.').slice(0,2).join('.') + '.');
    return;
  }}

  panel.innerHTML   = html;
  panel.className   = 'assessment visible';
  const toSpeak = (verdict === 'PARTIAL' && a.probe)
    ? a.probe
    : (a.feedback || '').split('.').slice(0,2).join('.') + '.';
  speakResponse(toSpeak);
  document.getElementById('record-hint').textContent = '';
  showStatus('');
}}

async function handoverToJordan() {{
  const btn = document.getElementById('ready-btn');
  btn.disabled    = true;
  btn.textContent = 'Handing over…';
  btn.style.opacity = '0.7';
  try {{
    const audio = document.getElementById('stage-audio');
    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}
    await fetch(`/session/${{SESSION_ID}}/teach/complete`, {{method:'POST'}});
  }} catch(e) {{}}
  loadStage(currentStage);
}}

async function backToAlex() {{
  const btn = document.getElementById('back-to-alex-btn');
  btn.disabled    = true;
  btn.textContent = '← Handing back…';
  btn.style.opacity = '0.7';
  try {{
    const audio = document.getElementById('stage-audio');
    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}
    await fetch(`/session/${{SESSION_ID}}/teach/restart`, {{method:'POST'}});
  }} catch(e) {{
    btn.disabled    = false;
    btn.textContent = '← Alistair';
    btn.style.opacity = '';
    return;
  }}
  btn.textContent = '← Loading…';
  const readyBtn = document.getElementById('ready-btn');
  if (readyBtn) {{ readyBtn.disabled = false; readyBtn.textContent = 'Test me →'; }}
  await loadStage(1);
  btn.disabled    = false;
  btn.textContent = '← Alistair';
  btn.style.opacity = '';
}}

function advanceStage(n) {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  deactivateWhiteboard();
  loadProgress();
  loadStage(n);
}}

function resetForProbe() {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  activateWhiteboard({{
    by:       'imogen',
    required: false,
    prompt:   'Upload written work or a proof sketch — optional',
  }});
  enableRecording();
  document.getElementById('record-hint').textContent = 'Answer the follow-up';
}}

function goEvaluate() {{
  window.location.href = `/session/${{SESSION_ID}}/evaluate`;
}}

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
let diagramRequired    = false;
let diagramRequiredBy  = null;
let currentRubric      = [];
let referenceConceptId = null;

function activateWhiteboard(opts = {{}}) {{
  const by        = opts.by       || 'alex';
  const required  = opts.required || false;
  const conceptId = opts.conceptId || null;
  currentRubric   = opts.rubric   || [];

  const panel  = document.getElementById('whiteboard');
  const banner = document.getElementById('whiteboard-banner');
  const btext  = document.getElementById('whiteboard-banner-text');

  panel.classList.add('active');
  banner.style.display = 'flex';
  banner.className     = 'whiteboard-banner mode-' + (required ? 'required' : by);
  panel.classList.toggle('mode-required', required);

  const defaultPrompts = {{
    alex:     'Sketch this out for me',
    alistair: 'Upload written work or a diagram',
    jordan:   'Draw it out — show me the approach',
    imogen:   'Upload written work or a proof sketch',
  }};
  btext.textContent = opts.prompt || defaultPrompts[by] || 'Upload your diagram';

  diagramRequired   = required;
  diagramRequiredBy = by;

  if (conceptId && conceptId !== referenceConceptId) {{
    referenceConceptId = conceptId;
    loadReferenceDiagram(conceptId);
  }} else if (!conceptId) {{
    document.getElementById('whiteboard-reference').classList.remove('visible');
  }}
  updateSubmitGate();
}}

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

function updateSubmitGate() {{
  const btn        = document.getElementById('record-btn');
  const hint       = document.getElementById('diagram-gate-hint');
  const thumbs     = document.querySelectorAll('.whiteboard-thumb');
  const hasDrawing = thumbs.length > 0;
  const blocked    = diagramRequired && !hasDrawing;
  btn.classList.toggle('diagram-pending', blocked);
  if (hint) hint.classList.toggle('visible', blocked);
  const banner = document.getElementById('whiteboard-banner');
  if (diagramRequired && banner) {{
    banner.className = 'whiteboard-banner mode-' + (blocked ? 'required' : diagramRequiredBy);
  }}
}}

async function loadReferenceDiagram(conceptId) {{
  const refPanel = document.getElementById('whiteboard-reference');
  const inner    = document.getElementById('whiteboard-reference-inner');
  refPanel.classList.add('visible');
  inner.innerHTML = '<div class="whiteboard-reference-loading">loading reference…</div>';
  try {{
    const res = await fetch(`/concept/${{conceptId}}/diagram`);
    if (!res.ok) throw new Error('not found');
    const svg  = await res.text();
    inner.innerHTML = svg;
    const svgEl = inner.querySelector('svg');
    if (svgEl) {{
      svgEl.style.width    = '100%';
      svgEl.style.height   = 'auto';
      svgEl.style.maxHeight = '120px';
      svgEl.style.display  = 'block';
    }}
  }} catch(e) {{
    refPanel.classList.remove('visible');
    inner.innerHTML = '';
  }}
}}

function renderRubric(rubric, scores) {{
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
    return `<div class="rubric-item">
      <span class="rubric-icon ${{ic.cls}}">${{ic.icon}}</span>
      <span class="rubric-text${{req}}">${{item.label}}${{item.required ? ' *' : ''}}</span>
    </div>`;
  }}).join('');
  return `<div class="rubric-list">${{items}}
    <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin-top:4px">* required element</div>
  </div>`;
}}

// ── Boot ─────────────────────────────────────────────────────────
startTimer();
loadStage(1);
</script>
</body>
</html>"""
