"""connectionsphere_factory/routes/sessions.py"""

from fastapi import APIRouter, HTTPException

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.models.schemas import CreateSessionRequest, SessionResponse
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(req: CreateSessionRequest):
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
        "created_at":        created,
        **state,
    }


@router.get("/sessions")
def list_sessions():
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
    return {"sessions": sessions}
