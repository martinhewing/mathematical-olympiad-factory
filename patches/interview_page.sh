#!/usr/bin/env bash
# interview_page.sh
# Adds GET /session/{id}/interview — the candidate-facing interview UI
# Run from inside connectionsphere_factory/

set -euo pipefail

cat >> src/connectionsphere_factory/routes/voice.py << 'PYEOF'


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

    return HTMLResponse(content=_interview_html(
        session_id = session_id,
        problem    = problem,
        name       = name,
        scene      = scene.get("scene", ""),
        fsm_state  = state["fsm_state"],
        phase      = state["phase"],
    ))


def _interview_html(session_id, problem, name, scene, fsm_state, phase) -> str:
    import json
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{problem} — ConnectionSphere</title>
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
  min-width: 60px;
  text-align: right;
}}

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
      <span class="panel-label">Interviewer</span>
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
    <div class="audio-bar">
      <div class="audio-progress">
        <div class="audio-fill" id="audio-fill"></div>
      </div>
      <span class="audio-label" id="audio-label">—</span>
    </div>
  </div>

  <!-- Right: Candidate -->
  <div class="right-panel">
    <div class="candidate-header">
      <span class="candidate-name">{name}</span>
      <span class="stage-indicator" id="stage-indicator">Stage —</span>
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
  </div>

</div>

<audio id="stage-audio" style="display:none"></audio>

<script>
const SESSION_ID = {json.dumps(session_id)};
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

    // Show question
    qt.innerHTML  = stageData.opening_question;
    qt.className  = 'question-text visible';

    // Update FSM badge
    document.getElementById('fsm-badge').textContent = stageData.fsm_state;

    // Play audio
    await playStageAudio(n);

  }} catch(e) {{
    qt.innerHTML = 'Failed to load stage. ' + e.message;
    qt.className = 'question-text visible';
  }}
}}

// ── Audio playback ───────────────────────────────────────────────
async function playStageAudio(n) {{
  const dot   = document.getElementById('speaking-dot');
  const fill  = document.getElementById('audio-fill');
  const label = document.getElementById('audio-label');
  const audio = document.getElementById('stage-audio');

  dot.className  = 'speaking-dot active';
  fill.style.width = '0%';
  label.textContent = '▶ playing';

  audio.src = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;

  audio.addEventListener('timeupdate', () => {{
    if (audio.duration) {{
      fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
      const rem = Math.ceil(audio.duration - audio.currentTime);
      label.textContent = rem + 's';
    }}
  }}, {{ once: false }});

  audio.addEventListener('ended', () => {{
    dot.className  = 'speaking-dot';
    fill.style.width = '100%';
    label.textContent = '✓ done';
    enableRecording();
  }}, {{ once: true }});

  audio.addEventListener('error', () => {{
    dot.className = 'speaking-dot';
    label.textContent = 'no audio';
    enableRecording();
  }}, {{ once: true }});

  try {{ await audio.play(); }} catch(e) {{
    // Autoplay blocked — enable recording immediately
    dot.className = 'speaking-dot';
    label.textContent = 'click ▶ to play';
    audio.controls = true;
    document.querySelector('.audio-bar').appendChild(audio);
    audio.style.display = 'block';
    audio.style.width   = '100%';
    enableRecording();
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
  const blob = new Blob(audioChunks, {{ type: 'audio/webm' }});
  const form = new FormData();
  form.append('audio', blob, 'answer.webm');

  showStatus('Transcribing…');

  try {{
    const res        = await fetch(`/session/${{SESSION_ID}}/stage/${{currentStage}}/voice`, {{
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

  panel.innerHTML   = html;
  panel.className   = 'assessment visible';
  document.getElementById('record-hint').textContent = '';
  showStatus('');
}}

function advanceStage(n) {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  loadStage(n);
}}

function resetForProbe() {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
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

// ── Boot ─────────────────────────────────────────────────────────
startTimer();
loadStage(1);
</script>
</body>
</html>"""
PYEOF

echo "Done. Add to auth public prefix list and restart."

# Also add /session/ interview to public paths (already covered by /session/ prefix)
echo "Interview page added to routes/voice.py"
echo ""
echo "Test it:"
echo "  Create a session → note session_id"
echo "  Open: http://localhost:8391/session/{session_id}/interview"
