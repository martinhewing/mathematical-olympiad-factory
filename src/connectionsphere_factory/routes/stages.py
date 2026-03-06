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
