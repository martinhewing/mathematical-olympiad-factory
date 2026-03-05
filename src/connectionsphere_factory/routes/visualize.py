"""connectionsphere_factory/routes/visualize.py"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.domain.conversation.visualization import DLLVisualizer
from connectionsphere_factory.domain.fsm.visualization import FSMVisualizer
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["visualize"])


@router.get("/session/{session_id}/fsm-visualize")
def fsm_visualize(session_id: str):
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
        return HTMLResponse(content=_fsm_text_fallback(fsm))


@router.get("/session/{session_id}/dll-visualize")
def dll_visualize(session_id: str):
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
        return HTMLResponse(content=_dll_text_fallback(dll))


@router.get("/session/{session_id}/fsm-mermaid")
def fsm_mermaid(session_id: str):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, _ = result
    return {"mermaid": fsm.mermaid(), "current_state": fsm.state.value}


def _fsm_text_fallback(fsm) -> str:
    transitions = [
        f"<li>{t.from_state} -> {t.to_state} ({t.trigger or 'auto'})</li>"
        for t in fsm.history[-10:]
    ]
    return f"""
    <div style="font-family:monospace;background:#1e293b;color:#e2e8f0;padding:1.5rem;border-radius:8px;font-size:.85rem">
      <p style="color:#6366f1;font-weight:700;margin-bottom:.75rem">FSM — Current state: {fsm.state.value}</p>
      <p style="color:#94a3b8;margin-bottom:.5rem">Phase: {fsm.phase}</p>
      <p style="color:#94a3b8;margin-bottom:1rem">Valid next: {', '.join(s.value for s in fsm.get_valid_transitions())}</p>
      <ul style="color:#cbd5e1;padding-left:1rem">{''.join(transitions) or '<li>None yet</li>'}</ul>
    </div>"""


def _dll_text_fallback(dll) -> str:
    stages = []
    for node in dll.iterate_oldest_first():
        icon       = "+" if node.status == "confirmed" else ("!" if node.status == "flagged" else ">")
        is_current = " <- current" if node == dll.current else ""
        stages.append(f"<li>{icon} {node.stage_id} [{node.stage_type}] {node.turn_count} turns{is_current}</li>")
    return f"""
    <div style="font-family:monospace;background:#1e293b;color:#e2e8f0;padding:1.5rem;border-radius:8px;font-size:.85rem">
      <p style="color:#6366f1;font-weight:700;margin-bottom:.75rem">Session Journey — {dll.size} stages</p>
      <ul style="color:#cbd5e1;padding-left:1rem;list-style:none">{''.join(stages) or '<li>No stages yet</li>'}</ul>
    </div>"""
