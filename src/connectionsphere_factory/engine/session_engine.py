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
from connectionsphere_factory.engine.teach_spec import (
    build_single_concept_teach_spec,
    build_single_concept_jordan_spec,
    select_concepts_for_problem,
)
from connectionsphere_factory.curriculum import CONCEPT_BY_ID
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

    # ── Per-concept architecture setup ──────────────────────────────
    from connectionsphere_factory.engine.teach_spec import select_concepts_for_problem
    _concepts = select_concepts_for_problem(problem_statement)
    fsm.context.concept_ids = [c.id for c in _concepts]
    fsm.transition_to(State.CONCEPT_TEACH, trigger="session_created")
    node = dll.add_stage("concept_teach_001", "concept_teach")

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

    # Add DLL teach stage
    dll = FactoryConversationHistory()
    dll.add_stage("teach_001", "teach")

    # ── Per-concept architecture: set concept_ids on FSM context ──────
    # select_concepts_for_problem() is pure Python — instant, no Claude call.
    # concept_ids drives is_concept_session and all subsequent routing.
    _problem = store.load_field(session_id, "problem_statement") or problem_statement
    _concepts = select_concepts_for_problem(_problem)
    fsm.context.concept_ids = [c.id for c in _concepts]
    log.info(
        "session.concept_ids_set",
        session_id   = session_id,
        concept_ids  = fsm.context.concept_ids,
        concept_count = len(fsm.context.concept_ids),
    )

    # Transition to CONCEPT_TEACH for new-architecture sessions
    if fsm.can_transition_to(State.CONCEPT_TEACH):
        fsm.transition_to(State.CONCEPT_TEACH, trigger="session_created")

    store.save(session_id, fsm, dll)


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

    # ── Per-concept architecture ──────────────────────────────────────
    if fsm.is_concept_session:
        return _get_or_generate_concept_stage(session_id, stage_n, fsm, dll)

    # ── Legacy architecture (fall-through) ────────────────────────────
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

    # ── Per-concept architecture: Alex + Jordan paths ─────────────────
    if fsm.is_concept_session:
        return _process_concept_submission(
            session_id, stage_n, answer, images, fsm, dll,
        )

    # ── Legacy TEACH phase ────────────────────────────────────────────
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
        "agent":               fsm.state.agent,
        # Per-concept fields (non-null for concept sessions only)
        "concept_id":          fsm.context.current_concept_id,
        "concept_index":       fsm.context.concept_index,
        "concepts_total":      fsm.context.concepts_total,
        "concepts_confirmed":  fsm.context.concepts_confirmed,
        "concepts_flagged":    fsm.context.concepts_flagged,
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


# ─────────────────────────────────────────────────────────────────────────────
# Per-concept architecture helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_generate_concept_stage(
    session_id: str,
    stage_n:    int,
    fsm:        FactoryFSM,
    dll:        FactoryConversationHistory,
) -> dict[str, Any]:
    """
    Generate or return cached spec for a concept session stage.

    stage_n is the 1-based concept index.
    FSM state determines whether Alex (CONCEPT_TEACH/CHECK) or
    Jordan (CONCEPT_STAGE) is active.

    Cache key: "concept_{stage_n}_{alex|jordan}" so Alex and Jordan
    specs for the same concept are cached independently.
    """
    from connectionsphere_factory.domain.fsm.states import State as _State

    phase_key = "alex" if fsm.state.is_teach_phase else "jordan"
    cache_key = f"concept_{stage_n}_{phase_key}"

    specs = store.load_field(session_id, "stage_specs") or {}
    if cache_key in specs:
        return specs[cache_key]

    # Look up the concept — stage_n is 1-based
    concept_idx = stage_n - 1
    if concept_idx < 0 or concept_idx >= len(fsm.context.concept_ids):
        raise ValueError(
            f"stage_n={stage_n} out of range for "
            f"{len(fsm.context.concept_ids)} concepts"
        )

    concept_id = fsm.context.concept_ids[concept_idx]
    concept    = CONCEPT_BY_ID.get(concept_id)
    if not concept:
        raise ValueError(f"concept_id {concept_id!r} not found in curriculum")

    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    level      = store.load_field(session_id, "candidate_level") or "senior"
    problem    = store.load_field(session_id, "problem_statement") or ""

    if fsm.state.is_teach_phase:
        spec = build_single_concept_teach_spec(
            session_id           = session_id,
            concept              = concept,
            candidate_first_name = first_name,
            candidate_level      = level,
            problem_statement    = problem,
            concept_index        = concept_idx,
            concepts_total       = fsm.context.concepts_total,
        )
    else:
        spec = build_single_concept_jordan_spec(
            session_id          = session_id,
            concept             = concept,
            problem_statement   = problem,
            candidate_level     = level,
            concept_index       = concept_idx,
            concepts_total      = fsm.context.concepts_total,
            concepts_confirmed  = fsm.context.concepts_confirmed,
        )

    specs[cache_key] = spec
    store.save_field(session_id, "stage_specs", specs)

    if dll.current:
        dll.current.spec = spec
        store.save(session_id, fsm, dll)

    log.info(
        "concept_stage.generated",
        session_id = session_id,
        stage_n    = stage_n,
        concept_id = concept_id,
        phase      = phase_key,
    )
    return spec


def _process_concept_submission(
    session_id: str,
    stage_n:    int,
    answer:     str,
    images:     list | None,
    fsm:        FactoryFSM,
    dll:        FactoryConversationHistory,
) -> AssessmentResponse:
    """
    Handle a submission for a per-concept session.

    Alex path  (CONCEPT_TEACH / CONCEPT_TEACH_CHECK):
      Run teach_check.j2 against single concept minimum bar.
      CONFIRMED → transition to CONCEPT_STAGE (same stage_n).
      PARTIAL   → transition to CONCEPT_TEACH_CHECK (reteach loop).

    Jordan path (CONCEPT_STAGE):
      Run diagram evaluator if images present.
      Run assess_submission.j2.
      CONFIRMED → confirm concept, advance_concept(), next stage.
      PARTIAL   → probe (same stage_n).
      NOT_MET   → flag concept, advance_concept(), next stage.
    """
    from connectionsphere_factory.domain.fsm.states import State

    settings    = get_settings()
    probe_limit = settings.probe_limit
    spec        = get_or_generate_stage(session_id, stage_n)
    first_name  = store.load_field(session_id, "candidate_first_name") or "there"

    if dll.current:
        dll.current.add_turn("candidate", answer, turn_type="text_submission")
    fsm.increment_turn()

    # ── Alex path ─────────────────────────────────────────────────────────
    if fsm.state in {State.CONCEPT_TEACH, State.CONCEPT_TEACH_CHECK}:
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
            # Clear Alex's cached spec — Jordan needs a fresh one
            specs = store.load_field(session_id, "stage_specs") or {}
            specs.pop(f"concept_{stage_n}_alex", None)
            store.save_field(session_id, "stage_specs", specs)

            fsm.transition_to(State.CONCEPT_STAGE, trigger="comprehension_confirmed")
            store.save(session_id, fsm, dll)

            log.info(
                "concept.teach_confirmed",
                session_id = session_id,
                stage_n    = stage_n,
                concept_id = fsm.context.current_concept_id,
            )
            return AssessmentResponse(
                verdict               = "CONFIRMED",
                feedback              = feedback,
                probe                 = None,
                concepts_demonstrated = [fsm.context.current_concept_id or ""],
                concepts_missing      = [],
                next_url              = f"/session/{session_id}/stage/{stage_n}",
                session_complete      = False,
            )
        else:
            fsm.increment_reteach()
            fsm.transition_to(State.CONCEPT_TEACH_CHECK, trigger="comprehension_partial")
            store.save(session_id, fsm, dll)

            log.info(
                "concept.teach_reteach",
                session_id    = session_id,
                stage_n       = stage_n,
                reteach_count = fsm.context.reteach_count,
            )
            return AssessmentResponse(
                verdict               = "PARTIAL",
                feedback              = feedback,
                probe                 = (
                    check_result.get("reteach", "")
                    or check_result.get("comprehension_check", "")
                ),
                concepts_demonstrated = [],
                concepts_missing      = [check_result.get("gap_concept", "")],
                next_url              = f"/session/{session_id}/stage/{stage_n}",
                session_complete      = False,
            )

    # ── Jordan path (CONCEPT_STAGE) ───────────────────────────────────────
    if fsm.probe_limit_reached:
        fsm.flag_current_concept(
            f"Probe limit ({probe_limit}) reached on concept {fsm.context.current_concept_id}"
        )
        next_url = _advance_concept_and_route(session_id, stage_n, fsm, dll)
        store.save(session_id, fsm, dll)
        log.warning(
            "concept.probe_limit",
            session_id = session_id,
            stage_n    = stage_n,
            concept_id = fsm.context.current_concept_id,
        )
        return AssessmentResponse(
            verdict               = "NOT_MET",
            feedback              = (
                f"We've explored this across {probe_limit} rounds. "
                "Let's move on — we'll come back to this."
            ),
            probe                 = None,
            concepts_demonstrated = [],
            concepts_missing      = [spec.get("concept_id", "")],
            next_url              = next_url,
            session_complete      = fsm.state == State.SESSION_COMPLETE,
        )

    # Diagram evaluation
    pending_rubric  = store.load_field(session_id, f"pending_diagram_rubric_{stage_n}") or []
    diagram_scores: list[dict] = []
    if images and pending_rubric:
        raw_scores     = evaluate_diagram(images, pending_rubric)
        diagram_scores = [s.to_dict() for s in raw_scores]
        log.info(
            "concept.diagram_evaluated",
            session_id = session_id,
            stage_n    = stage_n,
            summary    = diagram_summary(raw_scores),
        )

    # Curriculum concepts for the probing guide (single concept)
    concept_id = spec.get("concept_id", fsm.context.current_concept_id or "")
    curriculum_concepts: list[dict] = []
    c = CONCEPT_BY_ID.get(concept_id)
    if c:
        curriculum_concepts = [{
            "concept_id":         c.id,
            "name":               c.name,
            "solicit_drawing":    c.solicit_drawing,
            "jordan_probes":      c.jordan_probes,
            "jordan_minimum_bar": c.jordan_minimum_bar,
            "faang_signal":       c.faang_signal,
            "drawing_rubric": [
                {"label": r.label, "description": r.description, "required": r.required}
                for r in c.drawing_rubric
            ],
        }]

    probe_history = [
        t["content"]
        for t in (dll.current.turns if dll.current else [])
        if t.get("turn_type") == "probe"
    ]

    accumulated_this_stage = sorted(get_accumulated_concepts(session_id, stage_n))

    raw = render_and_call("assess_submission.j2", {
        "problem_statement":     store.load_field(session_id, "problem_statement"),
        "candidate_level":       store.load_field(session_id, "candidate_level"),
        "session_type":          "system_design",
        "stage_title":           spec.get("stage_title", f"Stage {stage_n}"),
        "label_id":              f"CONCEPT-{stage_n}",
        "concepts_tested":       spec.get("concepts_tested", [concept_id]),
        "fsm_mermaid":           fsm.mermaid(),
        "progress":              fsm.context.progress_summary,
        "confirmed_concepts":    fsm.context.concepts_confirmed,
        "accumulated_concepts":  accumulated_this_stage,
        "opening_question":      spec.get("opening_question", ""),
        "minimum_bar":           spec.get("minimum_bar", ""),
        "strong_answer_signals": spec.get("strong_answer_signals", []),
        "weak_answer_signals":   spec.get("weak_answer_signals", []),
        "probe_rounds":          fsm.context.probe_rounds,
        "probe_limit":           probe_limit,
        "probe_history":         probe_history,
        "candidate_answer":      answer,
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

    # Concept accumulation (semilattice — same as legacy path)
    record_fragment(session_id, stage_n, answer)
    accumulated = accumulate_concepts(
        session_id, stage_n, concepts_demonstrated, confidence_scores,
    )
    lattice = evaluate_concepts(session_id, stage_n)
    if verdict == "PARTIAL" and lattice["passed"]:
        verdict  = "CONFIRMED"
        feedback = (
            feedback.rstrip()
            + " — and with that, you've demonstrated everything needed for this concept."
        )
        probe = None
    concepts_missing = sorted(lattice["missing"])

    # diagram_request
    diagram_request: dict | None = raw.get("diagram_request")
    if isinstance(diagram_request, dict) and diagram_request:
        pending = diagram_request.get("rubric") or []
        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", pending)
        log.info(
            "concept.diagram_request_fired",
            session_id   = session_id,
            stage_n      = stage_n,
            concept_id   = diagram_request.get("concept_id", ""),
            required     = diagram_request.get("required", False),
        )
    else:
        diagram_request = None
        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", [])

    if dll.current:
        dll.current.add_turn("claude", feedback, turn_type="assessment")
        if probe:
            dll.current.add_turn("claude", probe, turn_type="probe")

    # Drive FSM
    next_url = _drive_concept_fsm(
        session_id, stage_n, verdict,
        concepts_demonstrated, raw.get("internal_notes", ""),
        fsm, dll,
    )

    store.save(session_id, fsm, dll)

    log.info(
        "concept.assessed",
        session_id  = session_id,
        stage_n     = stage_n,
        concept_id  = concept_id,
        verdict     = verdict,
        probe_rounds = fsm.context.probe_rounds,
    )

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


def _advance_concept_and_route(
    session_id: str,
    stage_n:    int,
    fsm:        FactoryFSM,
    dll:        FactoryConversationHistory,
) -> str:
    """
    Advance to the next concept and return the next_url.
    Shared by CONFIRMED and NOT_MET/FLAGGED paths.
    """
    from connectionsphere_factory.domain.fsm.states import State

    fsm.advance_concept()

    if fsm.all_concepts_done:
        if fsm.can_transition_to(State.EVALUATE):
            fsm.transition_to(State.EVALUATE, trigger="all_concepts_done")
            dll.add_stage("evaluate_001", "evaluate")
        return f"/session/{session_id}/evaluate"

    # More concepts — transition to Alex for concept N+1
    next_stage = stage_n + 1
    # Clear any cached jordan spec for the next stage (not generated yet)
    specs = store.load_field(session_id, "stage_specs") or {}
    specs.pop(f"concept_{next_stage}_jordan", None)
    store.save_field(session_id, "stage_specs", specs)

    if fsm.can_transition_to(State.CONCEPT_TEACH):
        fsm.transition_to(State.CONCEPT_TEACH, trigger="concept_advance")
        dll.add_stage(f"concept_teach_{next_stage:03d}", "concept_teach")

    return f"/session/{session_id}/stage/{next_stage}"


def _drive_concept_fsm(
    session_id:            str,
    stage_n:               int,
    verdict:               str,
    concepts_demonstrated: list[str],
    internal_notes:        str,
    fsm:                   FactoryFSM,
    dll:                   FactoryConversationHistory,
) -> str | None:
    """Drive FSM transitions for Jordan's CONCEPT_STAGE verdicts."""
    from connectionsphere_factory.domain.fsm.states import State

    if verdict == "CONFIRMED":
        if dll.current:
            dll.current.confirm(comprehension_record={
                "concept_id":            fsm.context.current_concept_id,
                "concepts_demonstrated": concepts_demonstrated,
                "evidence_summary":      internal_notes,
                "verified_at":           datetime.now().isoformat(),
            })
        fsm.confirm_current_concept()
        return _advance_concept_and_route(session_id, stage_n, fsm, dll)

    elif verdict == "PARTIAL":
        # Stay on CONCEPT_STAGE — probe issued
        if fsm.can_transition_to(State.CONCEPT_STAGE):
            fsm.transition_to(State.CONCEPT_STAGE, trigger="partial_answer")
        return f"/session/{session_id}/stage/{stage_n}"

    else:
        # NOT_MET — flag and advance
        fsm.flag_current_concept(
            f"NOT_MET on concept {fsm.context.current_concept_id}"
        )
        return _advance_concept_and_route(session_id, stage_n, fsm, dll)
