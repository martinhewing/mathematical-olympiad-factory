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
