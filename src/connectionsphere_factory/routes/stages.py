"""connectionsphere_factory/routes/stages.py"""

import html
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import HTMLResponse

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.config import get_settings
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["stages"])


@router.get("/session/{session_id}/stage/{stage_n}", response_class=HTMLResponse)
def get_stage(session_id: str, stage_n: int):
    settings = get_settings()
    if stage_n < 1 or stage_n > settings.max_stage_n:
        raise HTTPException(status_code=400, detail=f"stage_n must be 1–{settings.max_stage_n}")
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    spec           = engine.get_or_generate_stage(session_id, stage_n)
    state          = engine.get_state(session_id)
    problem        = html.escape(store.load_field(session_id, "problem_statement") or "")
    scene_data     = store.load_field(session_id, "scene") or {}
    candidate_name = html.escape(store.load_field(session_id, "candidate_name") or "Candidate")

    result       = engine.load_session(session_id)
    probe_rounds = result[0].context.probe_rounds if result else 0
    probe_limit  = settings.probe_limit

    return _render_stage_html(
        session_id     = session_id,
        stage_n        = stage_n,
        spec           = spec,
        scene          = scene_data.get("scene", ""),
        problem        = problem,
        candidate_name = candidate_name,
        probe_rounds   = probe_rounds,
        probe_limit    = probe_limit,
        fsm_state      = state["fsm_state"],
        phase          = state["phase"],
        progress       = state["progress"],
    )


@router.post("/session/{session_id}/stage/{stage_n}/submit")
def submit_stage(
    session_id: str,
    stage_n:    int,
    answer:     str = Form(..., max_length=4000),
):
    if len(answer) > 4000:
        raise HTTPException(status_code=422, detail="Answer exceeds 4000 character limit")
    if len(answer.strip()) < 10:
        raise HTTPException(status_code=422, detail="Answer is too short")
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = answer.strip(),
    )


@router.get("/session/{session_id}/evaluate", response_class=HTMLResponse)
def get_evaluate(session_id: str):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result         = engine.load_session(session_id)
    dll            = result[1] if result else None
    records        = dll.all_comprehension_records if dll else []
    problem        = store.load_field(session_id, "problem_statement") or ""
    candidate_name = store.load_field(session_id, "candidate_name") or "Candidate"
    confirmed      = [r["label_id"] for r in records if r]
    assessments    = store.load_field(session_id, "stage_assessments") or {}

    return _render_evaluate_html(
        session_id     = session_id,
        problem        = problem,
        candidate_name = candidate_name,
        confirmed      = confirmed,
        gaps           = [],
        assessments    = assessments,
    )


@router.get("/session/{session_id}/flagged", response_class=HTMLResponse)
def get_flagged(session_id: str):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, _ = result

    return HTMLResponse(content=f"""
    <!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Flagged — {session_id}</title>{_base_styles()}</head><body>
    <div class="container">
      <div class="flag-banner">
        <h2>Stage Flagged</h2>
        <p>{fsm.context.flag_reason}</p>
        <p>Label: <strong>{fsm.context.flag_label_id}</strong></p>
        <div class="actions">
          <a href="/session/{session_id}/stage/{_next_stage(session_id)}" class="btn">
            Continue to next stage
          </a>
          <a href="/session/{session_id}/evaluate" class="btn btn-secondary">
            Go to evaluation
          </a>
        </div>
      </div>
    </div></body></html>
    """)


def _render_stage_html(
    session_id, stage_n, spec, scene, problem,
    candidate_name, probe_rounds, probe_limit, fsm_state, phase, progress,
) -> str:
    opening_q   = spec.get("opening_question", "")
    stage_title = spec.get("stage_title", f"Stage {stage_n}")

    probe_indicator = ""
    if probe_rounds > 0:
        remaining = probe_limit - probe_rounds
        colour    = "#ef4444" if remaining <= 1 else "#f59e0b"
        probe_indicator = f"""
        <div class="probe-indicator" style="color:{colour}">
          Probe round {probe_rounds}/{probe_limit}
          {"— final round" if remaining == 1 else ""}
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{stage_title} — {session_id}</title>
{_base_styles()}
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head><body>
<div class="container">
  <header class="session-header">
    <div class="session-meta">
      <span class="tag phase-{phase}">{phase.upper()}</span>
      <span class="tag">{fsm_state}</span>
      <span class="session-id">#{session_id}</span>
    </div>
    <h1 class="problem">{problem}</h1>
    <p class="progress-text">{progress}</p>
  </header>
  <div class="scene-box">
    <div class="scene-label">INTERVIEWER</div>
    <p class="scene-text">{scene}</p>
  </div>
  <div class="stage-card">
    <div class="stage-header">
      <span class="stage-number">Stage {stage_n}</span>
      <h2 class="stage-title">{stage_title}</h2>
      {probe_indicator}
    </div>
    <div class="question-box">
      <div class="question-label">QUESTION</div>
      <p class="question-text">{opening_q}</p>
    </div>
    <form hx-post="/session/{session_id}/stage/{stage_n}/submit"
          hx-target="#assessment-panel"
          hx-swap="innerHTML"
          hx-indicator="#spinner">
      <div class="answer-area">
        <label for="answer">Your answer</label>
        <textarea id="answer" name="answer" rows="8"
          placeholder="Think out loud. Walk through your reasoning."></textarea>
      </div>
      <div class="submit-row">
        <button type="submit" class="btn btn-primary">Submit answer</button>
        <span id="spinner" class="htmx-indicator">Assessing...</span>
      </div>
    </form>
  </div>
  <div id="assessment-panel"></div>
  <div class="viz-row">
    <a href="/session/{session_id}/fsm-visualize" target="_blank" class="viz-link">FSM diagram</a>
    <a href="/session/{session_id}/dll-visualize" target="_blank" class="viz-link">Session journey</a>
  </div>
</div></body></html>"""


def _render_evaluate_html(
    session_id, problem, candidate_name, confirmed, gaps, assessments
) -> str:
    confirmed_html = "".join(
        f'<li class="confirmed">+ {c}</li>' for c in confirmed
    ) or "<li>No stages confirmed.</li>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Evaluation — {session_id}</title>{_base_styles()}</head><body>
<div class="container">
  <header class="session-header">
    <h1>Session Complete</h1>
    <p class="problem">{problem}</p>
    <p>Candidate: <strong>{candidate_name}</strong></p>
  </header>
  <div class="eval-card">
    <h2>Concepts Demonstrated</h2>
    <ul class="concept-list">{confirmed_html}</ul>
  </div>
  <div class="eval-card">
    <h2>Next Steps</h2>
    <p>Start a new session to practice a different problem.</p>
    <a href="/" class="btn btn-primary">New session</a>
  </div>
</div></body></html>"""


def _next_stage(session_id: str) -> int:
    specs = store.load_field(session_id, "stage_specs") or {}
    return len(specs) + 1


def _base_styles() -> str:
    return """<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.container { max-width: 860px; margin: 0 auto; padding: 2rem 1.5rem; }
.session-header { margin-bottom: 2rem; }
.session-meta { display: flex; gap: .5rem; align-items: center; margin-bottom: .75rem; flex-wrap: wrap; }
.tag { padding: .25rem .6rem; border-radius: 4px; font-size: .7rem; font-weight: 700;
       letter-spacing: .05em; text-transform: uppercase; }
.phase-teach    { background: #1e40af; color: #bfdbfe; }
.phase-simulate { background: #92400e; color: #fde68a; }
.phase-evaluate { background: #065f46; color: #a7f3d0; }
.phase-lifecycle{ background: #374151; color: #d1d5db; }
.session-id { font-size: .7rem; color: #64748b; font-family: monospace; }
.problem { font-size: 1.4rem; font-weight: 700; color: #f8fafc; margin-bottom: .4rem; }
.progress-text { font-size: .8rem; color: #94a3b8; }
.scene-box { background: #1e293b; border-left: 3px solid #6366f1;
             padding: 1.25rem 1.5rem; border-radius: 6px; margin-bottom: 1.5rem; }
.scene-label { font-size: .65rem; font-weight: 700; letter-spacing: .1em;
               color: #6366f1; margin-bottom: .5rem; }
.scene-text { line-height: 1.7; color: #cbd5e1; font-size: .95rem; }
.stage-card { background: #1e293b; border-radius: 8px; padding: 1.75rem; margin-bottom: 1.5rem; }
.stage-header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
.stage-number { font-size: .7rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: .08em; color: #64748b; }
.stage-title { font-size: 1.15rem; font-weight: 600; color: #f1f5f9; }
.probe-indicator { font-size: .75rem; font-weight: 600; margin-left: auto;
                   padding: .2rem .5rem; border-radius: 4px; background: #1c1917; }
.question-box { background: #0f172a; border-radius: 6px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
.question-label { font-size: .65rem; font-weight: 700; letter-spacing: .1em;
                  color: #94a3b8; margin-bottom: .4rem; }
.question-text { color: #e2e8f0; line-height: 1.6; font-size: .95rem; }
.answer-area { margin-bottom: 1rem; }
.answer-area label { display: block; font-size: .75rem; font-weight: 600; color: #94a3b8;
                     margin-bottom: .4rem; text-transform: uppercase; letter-spacing: .06em; }
textarea { width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 6px;
           color: #e2e8f0; padding: .75rem 1rem; font-size: .95rem; line-height: 1.6;
           resize: vertical; font-family: inherit; }
textarea:focus { outline: none; border-color: #6366f1; }
.btn { display: inline-block; padding: .6rem 1.25rem; border-radius: 6px;
       font-size: .875rem; font-weight: 600; cursor: pointer;
       text-decoration: none; border: none; }
.btn-primary   { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-secondary { background: #334155; color: #e2e8f0; }
.submit-row { display: flex; align-items: center; gap: 1rem; }
.htmx-indicator { display: none; color: #94a3b8; font-size: .85rem; }
.htmx-request .htmx-indicator { display: inline; }
#assessment-panel { margin-top: 1.5rem; }
.assessment-card { border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }
.verdict-CONFIRMED { background: #064e3b; border-left: 4px solid #10b981; }
.verdict-PARTIAL   { background: #451a03; border-left: 4px solid #f59e0b; }
.verdict-NOT_MET   { background: #450a0a; border-left: 4px solid #ef4444; }
.verdict-label { font-size: .7rem; font-weight: 800; letter-spacing: .1em;
                 text-transform: uppercase; margin-bottom: .5rem; }
.verdict-CONFIRMED .verdict-label { color: #10b981; }
.verdict-PARTIAL   .verdict-label { color: #f59e0b; }
.verdict-NOT_MET   .verdict-label { color: #ef4444; }
.feedback-text { line-height: 1.7; color: #e2e8f0; margin-bottom: 1rem; }
.concepts-row { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.concept-group { flex: 1; min-width: 180px; }
.concept-group h4 { font-size: .7rem; text-transform: uppercase;
                    letter-spacing: .06em; color: #64748b; margin-bottom: .4rem; }
.concept-list { list-style: none; }
.confirmed { color: #34d399; font-size: .85rem; padding: .15rem 0; }
.next-link { display: inline-block; margin-top: 1rem; padding: .6rem 1.25rem;
             background: #6366f1; color: #fff; border-radius: 6px;
             text-decoration: none; font-weight: 600; font-size: .875rem; }
.eval-card { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
.eval-card h2 { color: #f1f5f9; margin-bottom: 1rem; }
.flag-banner { background: #450a0a; border-left: 4px solid #ef4444;
               border-radius: 8px; padding: 1.5rem; }
.flag-banner h2 { color: #ef4444; margin-bottom: .5rem; }
.flag-banner p { color: #fca5a5; margin-bottom: .5rem; }
.actions { display: flex; gap: 1rem; margin-top: 1.25rem; flex-wrap: wrap; }
.viz-row { display: flex; gap: 1.5rem; margin-top: 1rem; }
.viz-link { font-size: .8rem; color: #6366f1; text-decoration: none; }
.viz-link:hover { text-decoration: underline; }
</style>"""
