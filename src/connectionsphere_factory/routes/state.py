"""connectionsphere_factory/routes/state.py"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from connectionsphere_factory.engine import session_engine as engine
from connectionsphere_factory.models.schemas import AssessmentResponse, StateResponse
import connectionsphere_factory.session_store as store

router = APIRouter(tags=["state"])


@router.get("/session/{session_id}/state", response_model=StateResponse)
def get_state(session_id: str):
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    state = engine.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found")
    return StateResponse(**state)


@router.post(
    "/session/{session_id}/stage/{stage_n}/assessment-fragment",
    response_class=HTMLResponse,
)
def assessment_fragment(session_id: str, stage_n: int, assessment: AssessmentResponse):
    return _render_assessment_html(session_id, stage_n, assessment)


def render_assessment_html(
    session_id: str, stage_n: int, assessment: AssessmentResponse
) -> str:
    return _render_assessment_html(session_id, stage_n, assessment)


def _render_assessment_html(
    session_id: str, stage_n: int, assessment: AssessmentResponse
) -> str:
    verdict   = assessment.verdict
    feedback  = assessment.feedback or ""
    probe     = assessment.probe or ""
    confirmed = assessment.concepts_demonstrated or []
    missing   = assessment.concepts_missing or []
    next_url  = assessment.next_url or ""

    confirmed_html = "".join(f'<li class="confirmed">+ {c}</li>' for c in confirmed) or "<li>—</li>"
    missing_html   = "".join(f'<li style="color:#f87171">- {c}</li>' for c in missing) or "<li>—</li>"

    probe_html = ""
    if probe and verdict == "PARTIAL":
        probe_html = f"""
        <div class="probe-box">
          <div class="probe-label">FOLLOW-UP QUESTION</div>
          <p style="color:#e2e8f0;line-height:1.6">{probe}</p>
        </div>"""

    next_html = ""
    if next_url and verdict != "PARTIAL":
        label     = "Continue to evaluation" if "evaluate" in next_url else f"Continue to stage {stage_n + 1}"
        next_html = f'<a href="{next_url}" class="next-link">{label}</a>'
    elif verdict == "PARTIAL":
        next_html = """
        <form hx-post="./submit" hx-target="#assessment-panel" hx-swap="innerHTML" style="margin-top:1rem">
          <textarea name="answer" rows="5"
            style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;
                   color:#e2e8f0;padding:.75rem;font-family:inherit;font-size:.9rem;resize:vertical"
            placeholder="Continue your answer..."></textarea>
          <button type="submit" class="btn btn-primary" style="margin-top:.75rem">Submit follow-up</button>
        </form>"""

    return f"""
    <div class="assessment-card verdict-{verdict}">
      <div class="verdict-label">{verdict}</div>
      <p class="feedback-text">{feedback}</p>
      {probe_html}
      <div class="concepts-row">
        <div class="concept-group"><h4>Demonstrated</h4><ul class="concept-list">{confirmed_html}</ul></div>
        <div class="concept-group"><h4>Missing</h4><ul class="concept-list">{missing_html}</ul></div>
      </div>
    </div>
    {next_html}
    """
