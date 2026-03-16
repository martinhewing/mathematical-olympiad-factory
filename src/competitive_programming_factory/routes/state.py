"""
competitive_programming_factory/routes/state.py

State polling endpoint — pure JSON.
Called by Scalar to show current FSM position.
"""

from fastapi import APIRouter, HTTPException

from competitive_programming_factory.engine import session_engine as engine
from competitive_programming_factory.models.schemas import StateResponse
import competitive_programming_factory.session_store as store

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
