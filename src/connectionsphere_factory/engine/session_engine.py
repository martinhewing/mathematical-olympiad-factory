"""
connectionsphere_factory/engine/session_engine.py

The session engine — the only component that coordinates FSM, DLL, and Claude.
Everything else delegates here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from connectionsphere_factory.config import get_settings
from connectionsphere_factory.logging import get_logger
from connectionsphere_factory.domain.conversation.history import FactoryConversationHistory
from connectionsphere_factory.domain.fsm.machine import FactoryFSM
from connectionsphere_factory.domain.fsm.states import State
from connectionsphere_factory.domain.agents import get_agent_for_state
from connectionsphere_factory.engine.prompt_renderer import render_and_call
from connectionsphere_factory.engine.diagram_evaluator import (
    evaluate_diagram, diagram_passes_minimum, diagram_summary,
)
from connectionsphere_factory.engine.teach_spec import build_teach_spec
from connectionsphere_factory.models.schemas import AssessmentResponse, CandidateLevel
import connectionsphere_factory.session_store as store
from connectionsphere_factory.engine.concept_store import (
    accumulate as accumulate_concepts,
    evaluate as evaluate_concepts,
    get_accumulated as get_accumulated_concepts,
    record_fragment,
)

log = get_logger(__name__)


def create_session(
    problem_statement: str,
    candidate_name:    str            = "Candidate",
    candidate_level:   CandidateLevel = CandidateLevel.SENIOR,
) -> str:
    session_id = str(uuid.uuid4())[:8]

    fsm = FactoryFSM(
        candidate_name    = candidate_name,
        candidate_level   = candidate_level.value,
        problem_statement = problem_statement,
    )
    dll = FactoryConversationHistory()

    fsm.transition_to(State.TEACH,        trigger="session_created")
    node = dll.add_stage("requirements_001", "requirements")

    scene_data = _generate_scene(problem_statement, candidate_level.value)
    node.add_turn("claude", scene_data["scene"], turn_type="scene")

    store.save_field(session_id, "scene",             scene_data)
    store.save_field(session_id, "problem_statement", problem_statement)
    store.save_field(session_id, "candidate_name",    candidate_name)
    store.save_field(session_id, "candidate_first_name", candidate_name.strip().split()[0] if candidate_name.strip() else "there")
    store.save_field(session_id, "candidate_level",   candidate_level.value)
    store.save_field(session_id, "created_at",        datetime.now().isoformat())
    store.save_field(session_id, "stage_specs",       {})
    store.save_field(session_id, "stage_assessments", {})

    # Fix: add teach stage to dll so get_or_generate_stage works correctly
    dll = FactoryConversationHistory()
    dll.add_stage("teach_001", "teach")
    store.save(session_id, fsm, dll)

    # Pre-generate lesson so interview page loads instantly
    try:
        get_or_generate_stage(session_id, 1)
        log.info("session.lesson_pregenerated", session_id=session_id)
    except Exception as e:
        log.warning("session.lesson_pregenerate_failed", session_id=session_id, error=str(e))

    log.info(
        "session.created",
        session_id      = session_id,
        candidate_name  = candidate_name,
        candidate_level = candidate_level.value,
    )
    return session_id


def get_or_generate_stage(session_id: str, stage_n: int) -> dict[str, Any]:
    specs = store.load_field(session_id, "stage_specs") or {}
    if str(stage_n) in specs:
        return specs[str(stage_n)]

    result = load_session(session_id)
    if not result:
        raise ValueError(f"Session {session_id} not found")
    fsm, dll = result

    label_id   = f"STAGE-{stage_n}"
    label_name = f"Stage {stage_n}"
    concepts   = _concepts_for_stage(
        store.load_field(session_id, "problem_statement") or "", stage_n
    )

    from connectionsphere_factory.domain.fsm.states import State as _State
    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}

    if is_teach:
        # Curriculum-backed: skeleton from curriculum.py, enriched by Claude.
        spec = build_teach_spec(
            session_id           = session_id,
            candidate_first_name = store.load_field(session_id, "candidate_first_name") or "there",
            candidate_level      = store.load_field(session_id, "candidate_level") or "senior",
            problem_statement    = store.load_field(session_id, "problem_statement") or "",
        )
    else:
        # Jordan stage: fully dynamic, unchanged.
        ctx = {
            "problem_statement":    store.load_field(session_id, "problem_statement"),
            "candidate_level":      store.load_field(session_id, "candidate_level"),
            "candidate_first_name": store.load_field(session_id, "candidate_first_name") or "there",
            "session_type":         "system_design",
            "stage_number":         stage_n,
            "fsm_state":            fsm.state.value,
            "fsm_mermaid":          fsm.mermaid(),
            "progress":             fsm.context.progress_summary,
            "confirmed_concepts":   dll.confirmed_labels,
            "label_id":             label_id,
            "label_name":           label_name,
            "concepts":             concepts,
        }
        spec = render_and_call(template, ctx)

    specs[str(stage_n)] = spec
    store.save_field(session_id, "stage_specs", specs)

    if dll.current:
        dll.current.spec = spec
        store.save(session_id, fsm, dll)

    return spec


def process_submission(
    session_id: str,
    stage_n:    int,
    answer:     str,
    images:     list | None = None,
) -> AssessmentResponse:
    result = load_session(session_id)
    if not result:
        raise ValueError(f"Session {session_id} not found")
    fsm, dll = result

    if dll.current:
        dll.current.add_turn("candidate", answer, turn_type="text_submission")

    fsm.increment_turn()

    settings    = get_settings()
    probe_limit = settings.probe_limit

    if fsm.probe_limit_reached:
        if fsm.can_transition_to(State.FLAGGED):
            fsm.context.raise_flag(
                reason   = f"Probe limit ({probe_limit}) reached on stage {stage_n}",
                label_id = f"STAGE-{stage_n}",
            )
            fsm.transition_to(State.FLAGGED, trigger="probe_limit")
        store.save(session_id, fsm, dll)
        log.warning(
            "session.flagged",
            session_id  = session_id,
            stage_n     = stage_n,
            flag_reason = getattr(fsm.context, "flag_reason", "probe_limit"),
        )
        return AssessmentResponse(
            verdict               = "NOT_MET",
            feedback              = (
                f"We've explored this concept across {probe_limit} rounds. "
                "Let's move on — we'll note the gap and come back to it."
            ),
            probe                 = None,
            concepts_demonstrated = [],
            concepts_missing      = _concepts_for_stage(
                store.load_field(session_id, "problem_statement") or "", stage_n
            ),
            next_url          = f"/session/{session_id}/flagged",
            session_complete  = False,
        )

    # ── TEACH phase — run comprehension check then advance to REQUIREMENTS ──
    if fsm.state in {State.TEACH, State.TEACH_CHECK}:
        spec       = get_or_generate_stage(session_id, stage_n)
        first_name = store.load_field(session_id, "candidate_first_name") or "there"
        check_result = render_and_call("teach_check.j2", {
            "problem_statement":   store.load_field(session_id, "problem_statement"),
            "candidate_first_name": first_name,
            "candidate_answer":    answer,
            "lesson_summary":      spec.get("ready_summary", ""),
            "minimum_bar":         spec.get("minimum_bar", ""),
            "comprehension_check": spec.get("comprehension_check", ""),
        })
        understood = check_result.get("advance_to_simulation", False)
        feedback   = check_result.get("feedback", "")
        if understood:
            fsm.transition_to(State.TEACH_CHECK,  trigger="comprehension_confirmed")
            fsm.transition_to(State.REQUIREMENTS, trigger="teach_complete")
            dll.current.confirm({})
            dll.add_stage("teach_check_001", "teach_check").confirm({})
            dll.add_stage("requirements_001", "requirements")
            store.save_field(session_id, "stage_specs", {})  # clear cached specs
            store.save(session_id, fsm, dll)
            return AssessmentResponse(
                verdict               = "CONFIRMED",
                feedback              = feedback,
                probe                 = None,
                concepts_demonstrated = ["teach_complete"],
                concepts_missing      = [],
                next_url              = f"/session/{session_id}/stage/{stage_n + 1}",
                session_complete      = False,
            )
        else:
            gap     = check_result.get("reteach", "")
            fsm.transition_to(State.TEACH_CHECK, trigger="comprehension_partial")
            store.save(session_id, fsm, dll)
            return AssessmentResponse(
                verdict               = "PARTIAL",
                feedback              = feedback,
                probe                 = gap or check_result.get("comprehension_check", ""),
                concepts_demonstrated = [],
                concepts_missing      = [check_result.get("gap_concept", "")],
                next_url              = f"/session/{session_id}/stage/{stage_n}",
                session_complete      = False,
            )

    spec          = get_or_generate_stage(session_id, stage_n)
    probe_history = [
        t["content"]
        for t in (dll.current.turns if dll.current else [])
        if t.get("turn_type") == "probe"
    ]

    # Fetch concepts accumulated across prior turns this stage
    accumulated_this_stage = sorted(get_accumulated_concepts(session_id, stage_n))

    # ── Diagram evaluation (runs before assess_submission.j2) ────────────
    pending_rubric  = store.load_field(session_id, f"pending_diagram_rubric_{stage_n}") or []
    diagram_scores: list[dict] = []
    if images and pending_rubric:
        raw_scores     = evaluate_diagram(images, pending_rubric)
        diagram_scores = [s.to_dict() for s in raw_scores]
        diagram_pass   = diagram_passes_minimum(raw_scores, pending_rubric)
        log.info(
            "diagram.evaluated",
            session_id = session_id,
            stage_n    = stage_n,
            summary    = diagram_summary(raw_scores),
            passes     = diagram_pass,
        )

    # ── Curriculum concepts for Jordan probing guide ──────────────────────
    all_concept_ids = (
        spec.get("all_concept_ids")
        or spec.get("concepts_tested")
        or []
    )
    curriculum_concepts: list[dict] = []
    if all_concept_ids:
        try:
            from connectionsphere_factory.curriculum import CONCEPT_BY_ID
            for cid in all_concept_ids:
                c = CONCEPT_BY_ID.get(cid)
                if c:
                    curriculum_concepts.append({
                        "concept_id":         c.id,
                        "name":               c.name,
                        "solicit_drawing":    c.solicit_drawing,
                        "jordan_probes":      c.jordan_probes,
                        "jordan_minimum_bar": c.jordan_minimum_bar,
                        "faang_signal":       c.faang_signal,
                        "drawing_rubric": [
                            {"label": r.label, "description": r.description,
                             "required": r.required}
                            for r in c.drawing_rubric
                        ],
                    })
        except Exception as _e:
            log.warning("session_engine.curriculum_lookup_failed", error=str(_e))

    raw = render_and_call("assess_submission.j2", {
        "problem_statement":     store.load_field(session_id, "problem_statement"),
        "candidate_level":       store.load_field(session_id, "candidate_level"),
        "session_type":          "system_design",
        "stage_title":           spec.get("stage_title", f"Stage {stage_n}"),
        "label_id":              f"STAGE-{stage_n}",
        "concepts_tested":       spec.get("concepts_tested", []),
        "fsm_mermaid":           fsm.mermaid(),
        "progress":              fsm.context.progress_summary,
        "confirmed_concepts":    dll.confirmed_labels,
        "accumulated_concepts":  accumulated_this_stage,
        "opening_question":      spec.get("opening_question", ""),
        "minimum_bar":           spec.get("minimum_bar", ""),
        "strong_answer_signals": spec.get("strong_answer_signals", []),
        "weak_answer_signals":   spec.get("weak_answer_signals", []),
        "probe_rounds":          fsm.context.probe_rounds,
        "probe_limit":           probe_limit,
        "probe_history":         probe_history,
        "candidate_answer":      answer,
        # E) diagram fields
        "has_candidate_diagram": bool(images),
        "curriculum_concepts":   curriculum_concepts,
        "diagram_scores":        diagram_scores,
    }, images=images or [])

    verdict               = raw.get("verdict", "NOT_MET")
    feedback              = raw.get("feedback", "")
    probe                 = raw.get("probe")
    concepts_demonstrated = raw.get("concepts_demonstrated", [])
    concepts_missing      = raw.get("concepts_missing", [])
    confidence_scores     = raw.get("confidence_scores", {})

    # ── diagram_request: extract + persist rubric for next submission ──
    diagram_request: dict | None = raw.get("diagram_request")
    if isinstance(diagram_request, dict) and diagram_request:
        pending = diagram_request.get("rubric") or []
        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", pending)
        log.info(
            "diagram.request_fired",
            session_id   = session_id,
            stage_n      = stage_n,
            concept_id   = diagram_request.get("concept_id", ""),
            required     = diagram_request.get("required", False),
            rubric_items = len(pending),
        )
    else:
        diagram_request = None
        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", [])

    # ── Concept accumulation (semilattice) ────────────────────────────
    record_fragment(session_id, stage_n, answer)
    accumulated = accumulate_concepts(
        session_id, stage_n, concepts_demonstrated, confidence_scores,
    )
    lattice = evaluate_concepts(session_id, stage_n)

    if verdict == "PARTIAL" and lattice["passed"]:
        log.info(
            "verdict.upgraded_by_lattice",
            session_id  = session_id,
            stage_n     = stage_n,
            accumulated = sorted(lattice["accumulated"]),
        )
        verdict  = "CONFIRMED"
        feedback = (
            feedback.rstrip()
            + " — and with that, you've demonstrated everything needed for this stage."
        )
        probe = None

    # Update concepts_missing from lattice (authoritative source)
    concepts_missing = sorted(lattice["missing"])
    # ── End concept accumulation ──────────────────────────────────────

    if dll.current:
        dll.current.add_turn("claude", feedback, turn_type="assessment")
        if probe:
            dll.current.add_turn("claude", probe, turn_type="probe")

    next_url = _drive_fsm(
        session_id, fsm, dll, stage_n, verdict,
        concepts_demonstrated, raw.get("internal_notes", ""),
    )

    store.save(session_id, fsm, dll)

    log.info(
        "stage.assessed",
        session_id            = session_id,
        stage_n               = stage_n,
        verdict               = verdict,
        concepts_demonstrated = concepts_demonstrated,
        concepts_missing      = concepts_missing,
        probe_rounds          = fsm.context.probe_rounds,
    )

    if fsm.state == State.SESSION_COMPLETE:
        log.info("session.complete", session_id=session_id)

    return AssessmentResponse(
        verdict               = verdict,
        feedback              = feedback,
        probe                 = probe if verdict == "PARTIAL" else None,
        concepts_demonstrated = concepts_demonstrated,
        concepts_missing      = concepts_missing,
        next_url              = next_url,
        session_complete      = fsm.state == State.SESSION_COMPLETE,
        diagram_request       = diagram_request,
        diagram_scores        = diagram_scores,
    )


def _drive_fsm(
    session_id:            str,
    fsm:                   FactoryFSM,
    dll:                   FactoryConversationHistory,
    stage_n:               int,
    verdict:               str,
    concepts_demonstrated: list[str],
    internal_notes:        str,
) -> str | None:
    if verdict == "CONFIRMED":
        if dll.current:
            dll.current.confirm(comprehension_record={
                "label_id":              f"STAGE-{stage_n}",
                "concepts_demonstrated": concepts_demonstrated,
                "evidence_summary":      internal_notes,
                "verified_at":           datetime.now().isoformat(),
            })
            fsm.context.confirm_label(f"STAGE-{stage_n}")

        next_stage = stage_n + 1
        if next_stage > 3:
            if fsm.can_transition_to(State.EVALUATE):
                fsm.transition_to(State.EVALUATE, trigger="all_stages_confirmed")
                dll.add_stage("evaluate_001", "evaluate")
            return f"/session/{session_id}/evaluate"

        if fsm.can_transition_to(State.OOD_STAGE):
            fsm.transition_to(State.OOD_STAGE, trigger="stage_confirmed")
        elif fsm.can_transition_to(State.NODE_SESSION):
            fsm.transition_to(State.NODE_SESSION, trigger="stage_confirmed")

        dll.add_stage(f"ood_STAGE-{next_stage}_{next_stage:03d}", "ood_stage")
        return f"/session/{session_id}/stage/{next_stage}"

    elif verdict == "PARTIAL":
        return f"/session/{session_id}/stage/{stage_n}"

    else:
        next_stage = stage_n + 1
        if next_stage > 3:
            if fsm.can_transition_to(State.EVALUATE):
                fsm.transition_to(State.EVALUATE, trigger="stages_complete_with_gaps")
                dll.add_stage("evaluate_001", "evaluate")
            return f"/session/{session_id}/evaluate"
        return f"/session/{session_id}/stage/{next_stage}"


def load_session(session_id: str) -> tuple[FactoryFSM, FactoryConversationHistory] | None:
    return store.load(session_id)


def get_state(session_id: str) -> dict[str, Any] | None:
    result = load_session(session_id)
    if not result:
        return None
    fsm, dll = result
    ctx = fsm.prompt_context()
    return {
        "session_id":          session_id,
        "fsm_state":           fsm.state.value,
        "phase":               fsm.phase,
        "turns_in_state":      fsm.turns_in_current_state,
        "probe_rounds":        fsm.context.probe_rounds,
        "probe_limit_reached": fsm.probe_limit_reached,
        "requires_voice":      fsm.state.requires_voice,
        "valid_transitions":   ctx["valid_transitions"],
        "current_node":        fsm.context.current_node_id,
        "current_label":       fsm.context.current_node_label,
        "progress":            fsm.context.progress_summary,
        "agent_name":          get_agent_for_state(fsm.state.value).display_name,
        "agent_role":          get_agent_for_state(fsm.state.value).role_label,
    }


def _generate_scene(problem_statement: str, candidate_level: str) -> dict[str, Any]:
    return render_and_call("generate_scene.j2", {
        "problem_statement": problem_statement,
        "candidate_level":   candidate_level,
    })


def _concepts_for_stage(problem_statement: str, stage_n: int) -> list[str]:
    """Return required concepts for a stage. Canonical source: concept_store."""
    from connectionsphere_factory.engine.concept_store import get_required
    return sorted(get_required(stage_n))
