"""
competitive_programming_factory/routes/stages.py

Stage routes — pure JSON. Scalar is the UI.

GET  /session/{id}/stage/{n}         — stage spec + scene + FSM state
POST /session/{id}/stage/{n}/submit  — submit answer, get assessment
GET  /session/{id}/evaluate          — session debrief
GET  /session/{id}/flagged           — flagged stage detail
"""

from fastapi import APIRouter, HTTPException, Form, UploadFile, File

from competitive_programming_factory.engine import session_engine as engine
from competitive_programming_factory.config import get_settings
import competitive_programming_factory.session_store as store

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
        "comprehension_check": spec.get("comprehension_check", ""),
        "comprehension_check_mode": spec.get("comprehension_check_mode", "verbal"),
        "concepts":          spec.get("concepts", []),
        "greeting":          spec.get("greeting", ""),
        "agent_name":        state.get("agent_name", ""),
        "agent_role":        state.get("agent_role", ""),
        # Per-concept fields (populated for concept-architecture sessions)
        "agent":             state.get("agent", spec.get("agent", "")),
        "concept_id":        state.get("concept_id", spec.get("concept_id", "")),
        "scene_hook":        spec.get("scene_hook", ""),
        "solicit_drawing":   spec.get("solicit_drawing", False),
        "drawing_rubric":    spec.get("drawing_rubric", []),
        "concept_index":     state.get("concept_index", 0),
        "concepts_total":    state.get("concepts_total", 0),
        "concepts_confirmed":state.get("concepts_confirmed", []),
        "reteach_count":     result[0].context.reteach_count if result else 0,
    }




@router.get("/session/{session_id}/progress")
def get_progress(session_id: str):
    """
    Per-concept progress for this session.

    Returns a breakdown of all concepts selected for this session:
    which are confirmed, which are flagged, which are pending, and which
    is currently active. Used by the UI progress bar.

    Only meaningful for sessions using the per-concept architecture
    (concept_ids will be empty for legacy sessions).
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    fsm, _ = result
    ctx    = fsm.context

    # Build a per-concept status list in curriculum order
    concept_statuses = []
    for cid in ctx.concept_ids:
        if cid in ctx.concepts_confirmed:
            status = "confirmed"
        elif cid in ctx.concepts_flagged:
            status = "flagged"
        elif cid == ctx.current_concept_id:
            status = "current"
        else:
            status = "pending"
        concept_statuses.append({"concept_id": cid, "status": status})

    return {
        "session_id":         session_id,
        "total":              ctx.concepts_total,
        "current_index":      ctx.concept_index,
        "current_concept_id": ctx.current_concept_id,
        "confirmed":          ctx.concepts_confirmed,
        "flagged":            ctx.concepts_flagged,
        "pending":            ctx.concepts_pending,
        "concepts":           concept_statuses,
        "all_done":           ctx.all_concepts_done,
        "phase":              fsm.phase,
        "agent":              fsm.state.agent,
    }


@router.post("/session/{session_id}/teach/restart")
def teach_restart(session_id: str):
    """Reset FSM back to TEACH so candidate can review Alex lesson again."""
    import os
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, dll = result
    from competitive_programming_factory.domain.fsm.states import State as _State
    if fsm.is_concept_session:
        fsm.transition_to(_State.RESTART, trigger="back_to_teach")
        fsm.transition_to(_State.SESSION_START, trigger="restarted")
        fsm.transition_to(_State.CONCEPT_TEACH, trigger="session_created")
        dll = engine.FactoryConversationHistory()
        dll.add_stage("concept_teach_001", "concept_teach")
        # Clear Jordan spec cache so Alex spec reloads
        specs = store.load_field(session_id, "stage_specs") or {}
        specs.pop("concept_1_jordan", None)
        store.save_field(session_id, "stage_specs", specs)
    else:
        fsm.transition_to(_State.RESTART, trigger="back_to_teach"); fsm.transition_to(_State.SESSION_START, trigger="restarted"); fsm.transition_to(_State.TEACH, trigger="session_created")
        dll = engine.FactoryConversationHistory()
        dll.add_stage("teach_001", "teach")
    # Restore Alex's cached spec so page loads instantly
    teach_spec = store.load_field(session_id, "teach_spec")
    if teach_spec:
        store.save_field(session_id, "stage_specs", {"1": teach_spec})
    else:
        store.save_field(session_id, "stage_specs", {})
    # keep stage_specs cache on restart so lesson loads instantly
    store.save(session_id, fsm, dll)
    # clear cached audio
    return {"status": "ok", "fsm_state": fsm.state.value}


@router.post("/session/{session_id}/teach/ask")
async def teach_ask(
    session_id: str,
    audio: UploadFile = File(...),
    images: list[UploadFile] = File(default=[]),
):
    """Candidate asks Alex a question during TEACH phase via voice + optional diagrams."""
    from competitive_programming_factory.config import get_settings
    from competitive_programming_factory.voice.stt import transcribe
    import anthropic, json, re, base64
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript   = await transcribe(audio_bytes, content_type=content_type)
    spec       = engine.get_or_generate_stage(session_id, 1)
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    problem    = store.load_field(session_id, "problem_statement") or ""
    concepts   = spec.get("concepts", [])
    concept_text = "\n".join(f"- {c.get('name','')}: {c.get('explanation','')}" for c in concepts)
    prompt_text = (
        f"You are Alex, a warm Senior Staff Engineer tutoring a candidate.\n"
        f"Problem: {problem}\n"
        f"Concepts covered:\n{concept_text}\n\n"
        f"The candidate says: \"{transcript}\"\n\n"
        + ("The candidate has also shared diagram(s) of their design. Review them as part of your feedback.\n\n" if images else "")
        + f"Reply in 2-3 sentences. Be encouraging. Address them as {first_name}.\n"
        + 'Return ONLY JSON: {"reply": "your response"}'
    )
    # Build message content — text + optional images
    user_content = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            media_type = img.content_type or "image/png"
            user_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type,
                           "data": base64.b64encode(img_bytes).decode()},
            })
    user_content.append({"type": "text", "text": prompt_text})
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = msg.content[0].text.strip()
    try:
        clean = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        reply = json.loads(clean).get("reply", clean)
    except Exception:
        reply = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return {
        "verdict":               "PARTIAL",
        "feedback":              reply,
        "probe":                 reply,
        "transcript":            transcript,
        "concepts_demonstrated": [],
        "concepts_missing":      [],
        "next_url":              f"/session/{session_id}/stage/1",
        "session_complete":      False,
    }

@router.post("/session/{session_id}/teach/complete")
def teach_complete(session_id: str):
    """Advance FSM from TEACH to REQUIREMENTS — Alex hands over to Jordan."""
    import os
    from competitive_programming_factory.domain.fsm.states import State
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, dll = result
    from competitive_programming_factory.domain.fsm.states import State as _State
    if fsm.state in {_State.CONCEPT_TEACH, _State.CONCEPT_TEACH_CHECK}:
        # Concept session: skip Alex check, hand to Jordan for this concept
        fsm.transition_to(_State.CONCEPT_STAGE, trigger="comprehension_skipped")
        dll.current.confirm({})
        # Clear Alex's cached spec so Jordan's spec is generated fresh
        _specs = store.load_field(session_id, "stage_specs") or {}
        _stage_key = f"concept_{fsm.context.concept_index + 1}_alex"
        _specs.pop(_stage_key, None)
        store.save_field(session_id, "stage_specs", _specs)
        store.save(session_id, fsm, dll)
    elif fsm.state in {_State.TEACH, _State.TEACH_CHECK}:
        # Legacy session
        fsm.transition_to(_State.TEACH_CHECK,  trigger="comprehension_skipped")
        fsm.transition_to(_State.REQUIREMENTS, trigger="teach_complete")
        dll.current.confirm({})
        dll.add_stage("requirements_001", "requirements")
        current_specs = store.load_field(session_id, "stage_specs") or {}
        if "1" in current_specs:
            store.save_field(session_id, "teach_spec", current_specs["1"])
        store.save(session_id, fsm, dll)
    # Pre-generate Jordan's stage spec so handover is instant
    try:
        engine.get_or_generate_stage(session_id, 1)
    except Exception as e:
        pass  # non-fatal — will generate on demand
    return {"status": "ok", "fsm_state": fsm.state.value}


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
