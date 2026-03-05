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
from connectionsphere_factory.engine.prompt_renderer import render_and_call
from connectionsphere_factory.models.schemas import AssessmentResponse, CandidateLevel
import connectionsphere_factory.session_store as store

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
    fsm.transition_to(State.TEACH_CHECK,  trigger="auto_teach_pass")
    fsm.transition_to(State.REQUIREMENTS, trigger="auto_teach_pass")
    dll.add_stage("teach_001",       "teach").confirm({})
    dll.add_stage("teach_check_001", "teach_check").confirm({})
    node = dll.add_stage("requirements_001", "requirements")

    scene_data = _generate_scene(problem_statement, candidate_level.value)
    node.add_turn("claude", scene_data["scene"], turn_type="scene")

    store.save_field(session_id, "scene",             scene_data)
    store.save_field(session_id, "problem_statement", problem_statement)
    store.save_field(session_id, "candidate_name",    candidate_name)
    store.save_field(session_id, "candidate_level",   candidate_level.value)
    store.save_field(session_id, "created_at",        datetime.now().isoformat())
    store.save_field(session_id, "stage_specs",       {})
    store.save_field(session_id, "stage_assessments", {})
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

    label_id   = f"STAGE-{stage_n}"
    label_name = f"Stage {stage_n}"
    concepts   = _concepts_for_stage(
        store.load_field(session_id, "problem_statement") or "", stage_n
    )

    spec = render_and_call("generate_stage.j2", {
        "problem_statement":  store.load_field(session_id, "problem_statement"),
        "candidate_level":    store.load_field(session_id, "candidate_level"),
        "session_type":       "system_design",
        "stage_number":       stage_n,
        "fsm_state":          fsm.state.value,
        "fsm_mermaid":        fsm.mermaid(),
        "progress":           fsm.context.progress_summary,
        "confirmed_concepts": dll.confirmed_labels,
        "label_id":           label_id,
        "label_name":         label_name,
        "concepts":           concepts,
    })

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

    spec          = get_or_generate_stage(session_id, stage_n)
    probe_history = [
        t["content"]
        for t in (dll.current.turns if dll.current else [])
        if t.get("turn_type") == "probe"
    ]

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
        "opening_question":      spec.get("opening_question", ""),
        "minimum_bar":           spec.get("minimum_bar", ""),
        "strong_answer_signals": spec.get("strong_answer_signals", []),
        "weak_answer_signals":   spec.get("weak_answer_signals", []),
        "probe_rounds":          fsm.context.probe_rounds,
        "probe_limit":           probe_limit,
        "probe_history":         probe_history,
        "candidate_answer":      answer,
    })

    verdict               = raw.get("verdict", "NOT_MET")
    feedback              = raw.get("feedback", "")
    probe                 = raw.get("probe")
    concepts_demonstrated = raw.get("concepts_demonstrated", [])
    concepts_missing      = raw.get("concepts_missing", [])

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
    }


def _generate_scene(problem_statement: str, candidate_level: str) -> dict[str, Any]:
    return render_and_call("generate_scene.j2", {
        "problem_statement": problem_statement,
        "candidate_level":   candidate_level,
    })


def _concepts_for_stage(problem_statement: str, stage_n: int) -> list[str]:
    stage_concepts = {
        1: ["requirements_clarification", "scale_estimation", "api_design"],
        2: ["data_model", "storage_choice", "schema_design"],
        3: ["system_components", "scalability", "fault_tolerance"],
    }
    return stage_concepts.get(stage_n, [f"concept_{stage_n}_a", f"concept_{stage_n}_b"])
