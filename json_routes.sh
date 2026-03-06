#!/usr/bin/env bash
# json_routes.sh
# Run from inside connectionsphere_factory/
# Rewrites all routes to pure JSON — no HTML rendering.
# Scalar becomes the only UI.

set -euo pipefail

# ── routes/stages.py ─────────────────────────────────────────────────────────
cat > src/connectionsphere_factory/routes/stages.py << 'EOF'
"""
connectionsphere_factory/routes/stages.py

Stage routes — pure JSON. Scalar is the UI.

GET  /session/{id}/stage/{n}         — stage spec + scene + FSM state
POST /session/{id}/stage/{n}/submit  — submit answer, get assessment
GET  /session/{id}/evaluate          — session debrief
GET  /session/{id}/flagged           — flagged stage detail
"""

from fastapi import APIRouter, HTTPException, Form

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.config import get_settings
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["stages"])


@router.get("/session/{session_id}/stage/{stage_n}")
def get_stage(session_id: str, stage_n: int):
    """
    Get the current stage for a session.

    Returns the interviewer scene, the opening question, and current FSM state.
    Use the `opening_question` to begin the interview exchange.
    Submit your answer to `POST /session/{session_id}/stage/{stage_n}/submit`.
    """
    settings = get_settings()
    if stage_n < 1 or stage_n > settings.max_stage_n:
        raise HTTPException(status_code=400, detail=f"stage_n must be 1–{settings.max_stage_n}")
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    spec       = engine.get_or_generate_stage(session_id, stage_n)
    state      = engine.get_state(session_id)
    scene_data = store.load_field(session_id, "scene") or {}
    result     = engine.load_session(session_id)

    probe_rounds = result[0].context.probe_rounds if result else 0
    probe_limit  = settings.probe_limit

    return {
        "session_id":        session_id,
        "stage_n":           stage_n,
        "stage_title":       spec.get("stage_title", f"Stage {stage_n}"),
        "opening_question":  spec.get("opening_question", ""),
        "minimum_bar":       spec.get("minimum_bar", ""),
        "concepts_tested":   spec.get("concepts_tested", []),
        "scene":             scene_data.get("scene", ""),
        "primary_tension":   scene_data.get("primary_tension", ""),
        "fsm_state":         state["fsm_state"],
        "phase":             state["phase"],
        "progress":          state["progress"],
        "probe_rounds":      probe_rounds,
        "probe_limit":       probe_limit,
        "probes_remaining":  probe_limit - probe_rounds,
        "submit_url":        f"/session/{session_id}/stage/{stage_n}/submit",
    }


@router.post("/session/{session_id}/stage/{stage_n}/submit")
def submit_stage(
    session_id: str,
    stage_n:    int,
    answer:     str = Form(..., max_length=4000),
):
    """
    Submit your answer to the current stage.

    **verdict** values:
    - `CONFIRMED` — stage complete, follow `next_url` to advance
    - `PARTIAL`   — good start, answer the `probe` question and resubmit
    - `NOT_MET`   — stage flagged, follow `next_url` for options

    Answers must be 10–4000 characters.
    """
    if len(answer.strip()) < 10:
        raise HTTPException(status_code=422, detail="Answer is too short (minimum 10 characters)")
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = answer.strip(),
    )


@router.get("/session/{session_id}/evaluate")
def get_evaluate(session_id: str):
    """
    Session debrief — all confirmed concepts, gaps, and assessment history.

    Available once the FSM reaches SESSION_COMPLETE.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result         = engine.load_session(session_id)
    dll            = result[1] if result else None
    records        = dll.all_comprehension_records if dll else []
    problem        = store.load_field(session_id, "problem_statement") or ""
    candidate_name = store.load_field(session_id, "candidate_name") or "Candidate"
    assessments    = store.load_field(session_id, "stage_assessments") or {}

    confirmed_labels = [r["label_id"] for r in records if r]
    concepts_demonstrated = []
    for r in records:
        if r:
            concepts_demonstrated.extend(r.get("concepts_demonstrated", []))

    return {
        "session_id":             session_id,
        "candidate_name":         candidate_name,
        "problem_statement":      problem,
        "status":                 "complete",
        "confirmed_labels":       confirmed_labels,
        "concepts_demonstrated":  list(set(concepts_demonstrated)),
        "stage_count":            len(assessments),
        "comprehension_records":  records,
        "next_steps":             "Start a new session with POST /sessions",
    }


@router.get("/session/{session_id}/flagged")
def get_flagged(session_id: str):
    """
    Flagged stage detail — probe limit was reached on this stage.

    Options:
    - Retry the stage: follow `retry_url`
    - Skip to next node: follow `skip_url`
    - Go straight to evaluation: follow `evaluate_url`
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, _ = result

    next_stage = _next_stage(session_id)

    return {
        "session_id":    session_id,
        "status":        "flagged",
        "flag_reason":   fsm.context.flag_reason,
        "flag_label_id": fsm.context.flag_label_id,
        "probe_rounds":  fsm.context.probe_rounds,
        "retry_url":     f"/session/{session_id}/stage/{next_stage}",
        "skip_url":      f"/session/{session_id}/stage/{next_stage}",
        "evaluate_url":  f"/session/{session_id}/evaluate",
        "message":       "Probe limit reached. A reviewer can advance this session manually.",
    }


def _next_stage(session_id: str) -> int:
    specs = store.load_field(session_id, "stage_specs") or {}
    return len(specs) + 1
EOF

# ── routes/state.py ───────────────────────────────────────────────────────────
cat > src/connectionsphere_factory/routes/state.py << 'EOF'
"""
connectionsphere_factory/routes/state.py

State polling endpoint — pure JSON.
Called by Scalar to show current FSM position.
"""

from fastapi import APIRouter, HTTPException

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.models.schemas import StateResponse
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["state"])


@router.get("/session/{session_id}/state", response_model=StateResponse)
def get_state(session_id: str):
    """
    Current FSM state for a session.

    Poll this endpoint to track session progress.
    `valid_transitions` shows what states are reachable from here.
    `requires_voice` indicates voice input is expected at this stage.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    state = engine.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found")
    return StateResponse(**state)
EOF

# ── routes/sessions.py ────────────────────────────────────────────────────────
# Already clean JSON — just tighten the docstrings for Scalar display
cat > src/connectionsphere_factory/routes/sessions.py << 'EOF'
"""
connectionsphere_factory/routes/sessions.py

Session management — pure JSON.
"""

from fastapi import APIRouter, HTTPException

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.models.schemas import CreateSessionRequest, SessionResponse
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(req: CreateSessionRequest):
    """
    Start a new interview session.

    Claude generates an opening scene based on your `problem_statement`.
    The FSM advances to **Requirements Gathering** — the candidate's starting point.

    Once created, open `stage_url` to begin the interview.

    **candidate_level** options: `junior` | `senior` | `staff` | `principal`
    """
    session_id = engine.create_session(
        problem_statement = req.problem_statement,
        candidate_name    = req.candidate_name,
        candidate_level   = req.candidate_level,
    )
    state = engine.get_state(session_id)
    return SessionResponse(
        session_id        = session_id,
        candidate_name    = req.candidate_name,
        problem_statement = req.problem_statement,
        fsm_state         = state["fsm_state"],
        phase             = state["phase"],
        stage_url         = f"/session/{session_id}/stage/1",
    )


@router.get("/session/{session_id}")
def get_session(session_id: str):
    """
    Full session detail — scene, FSM state, and candidate metadata.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    state   = engine.get_state(session_id)
    scene   = store.load_field(session_id, "scene") or {}
    created = store.load_field(session_id, "created_at") or ""

    return {
        "session_id":        session_id,
        "candidate_name":    store.load_field(session_id, "candidate_name"),
        "candidate_level":   store.load_field(session_id, "candidate_level"),
        "problem_statement": store.load_field(session_id, "problem_statement"),
        "scene":             scene.get("scene", ""),
        "primary_tension":   scene.get("primary_tension", ""),
        "deliberate_omissions": scene.get("deliberate_omissions", []),
        "strong_opening_move":  scene.get("strong_opening_move", ""),
        "created_at":        created,
        **state,
    }


@router.get("/sessions")
def list_sessions():
    """
    List all active sessions.
    """
    sessions = []
    for sid in store.all_sessions():
        state = engine.get_state(sid)
        if state:
            sessions.append({
                "session_id":        sid,
                "candidate_name":    store.load_field(sid, "candidate_name"),
                "problem_statement": store.load_field(sid, "problem_statement"),
                "fsm_state":         state["fsm_state"],
                "phase":             state["phase"],
            })
    return {"sessions": sessions, "count": len(sessions)}
EOF

# ── routes/visualize.py ───────────────────────────────────────────────────────
# Keep SVG endpoints — they render inline in Scalar. Remove HTML fallbacks.
cat > src/connectionsphere_factory/routes/visualize.py << 'EOF'
"""
connectionsphere_factory/routes/visualize.py

FSM and DLL visualisation endpoints.
SVG responses render inline in Scalar.
Text fallback returns JSON when Graphviz is unavailable.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.domain.conversation.visualization import DLLVisualizer
from connectionsphere_factory.domain.fsm.visualization import FSMVisualizer
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["visualize"])


@router.get("/session/{session_id}/fsm-visualize")
def fsm_visualize(session_id: str):
    """
    FSM state diagram — SVG.

    Current state marked ★. Valid next states marked →.
    Renders inline in Scalar's response panel.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, _ = result
    try:
        svg = FSMVisualizer(fsm).visualize().pipe(format="svg").decode("utf-8")
        return Response(content=svg, media_type="image/svg+xml")
    except Exception:
        return _fsm_json_fallback(fsm)


@router.get("/session/{session_id}/dll-visualize")
def dll_visualize(session_id: str):
    """
    Session journey diagram — SVG.

    Shows all stages in traversal order (oldest → newest).
    Current stage highlighted. Confirmed stages marked ✓.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    _, dll = result
    try:
        svg = DLLVisualizer(dll).visualize().pipe(format="svg").decode("utf-8")
        return Response(content=svg, media_type="image/svg+xml")
    except Exception:
        return _dll_json_fallback(dll)


@router.get("/session/{session_id}/fsm-mermaid")
def fsm_mermaid(session_id: str):
    """
    FSM as Mermaid stateDiagram-v2 markup.

    Paste into any Mermaid renderer to visualise the current session state.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, _ = result
    return {
        "mermaid":       fsm.mermaid(),
        "current_state": fsm.state.value,
        "phase":         fsm.phase,
    }


def _fsm_json_fallback(fsm) -> dict:
    return {
        "current_state":      fsm.state.value,
        "phase":              fsm.phase,
        "valid_transitions":  [s.value for s in fsm.get_valid_transitions()],
        "recent_transitions": [
            {"from": t.from_state, "to": t.to_state, "trigger": t.trigger}
            for t in fsm.history[-10:]
        ],
        "note": "Graphviz not available — install graphviz system package for SVG output",
    }


def _dll_json_fallback(dll) -> dict:
    stages = []
    for node in dll.iterate_oldest_first():
        stages.append({
            "stage_id":   node.stage_id,
            "stage_type": node.stage_type,
            "status":     node.status,
            "turns":      node.turn_count,
            "is_current": node == dll.current,
        })
    return {
        "size":   dll.size,
        "stages": stages,
        "note":   "Graphviz not available — install graphviz system package for SVG output",
    }
EOF

echo "All routes rewritten to pure JSON."
echo "Restart the server and open http://localhost:8391/docs"
