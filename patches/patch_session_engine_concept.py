"""
patch_session_engine_concept.py

Run from the competitive_programming_factory repo root:
    python3 patch_session_engine_concept.py

Five surgical patches to session_engine.py for the per-concept architecture:

  PATCH 1  Import new spec builders + curriculum lookup
  PATCH 2  create_session: set concept_ids on FSM context at creation time
  PATCH 3  get_or_generate_stage: add per-concept branch (CONCEPT_TEACH/CHECK/STAGE)
  PATCH 4  process_submission: add per-concept Alex + Jordan paths
  PATCH 5  get_state: expose concept progress fields
"""

import pathlib, py_compile, sys, tempfile, os

ENGINE = pathlib.Path("src/competitive_programming_factory/engine/session_engine.py")
if not ENGINE.exists():
    sys.exit(f"ERROR: {ENGINE} not found — run from repo root")

src      = ENGINE.read_text()
original = src
changes  = []


def _fail(patch_n: str, anchors: list[str]) -> None:
    print(f"\nDEBUG — {patch_n} anchors:")
    for a in anchors:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit(f"\n{patch_n} FAILED — paste DEBUG output as a reply")


# =============================================================================
# PATCH 1 — imports
# =============================================================================

P1_NEW = (
    "from competitive_programming_factory.engine.teach_spec import build_teach_spec\n"
    "from competitive_programming_factory.engine.teach_spec import (\n"
    "    build_single_concept_teach_spec,\n"
    "    build_single_concept_jordan_spec,\n"
    "    select_concepts_for_problem,\n"
    ")\n"
    "from competitive_programming_factory.curriculum import CONCEPT_BY_ID"
)

P1_OLD = "from competitive_programming_factory.engine.teach_spec import build_teach_spec"

if "build_single_concept_teach_spec" in src:
    print("  SKIP  PATCH 1 — concept spec imports already present")
    changes.append("PATCH 1 — already applied")
elif P1_OLD in src:
    src = src.replace(P1_OLD, P1_NEW, 1)
    changes.append("PATCH 1 — concept spec imports added")
else:
    _fail("PATCH 1", [P1_OLD])


# =============================================================================
# PATCH 2 — create_session: set concept_ids on FSM context
#
# Target: the block after dll.add_stage("teach_001", "teach") and before
#         store.save(session_id, fsm, dll)
# =============================================================================

P2_OLD = (
    '    # Fix: add teach stage to dll so get_or_generate_stage works correctly\n'
    '    dll = FactoryConversationHistory()\n'
    '    dll.add_stage("teach_001", "teach")\n'
    '    store.save(session_id, fsm, dll)'
)

P2_NEW = (
    '    # Add DLL teach stage\n'
    '    dll = FactoryConversationHistory()\n'
    '    dll.add_stage("teach_001", "teach")\n'
    '\n'
    '    # ── Per-concept architecture: set concept_ids on FSM context ──────\n'
    '    # select_concepts_for_problem() is pure Python — instant, no Claude call.\n'
    '    # concept_ids drives is_concept_session and all subsequent routing.\n'
    '    _problem = store.load_field(session_id, "problem_statement") or problem_statement\n'
    '    _concepts = select_concepts_for_problem(_problem)\n'
    '    fsm.context.concept_ids = [c.id for c in _concepts]\n'
    '    log.info(\n'
    '        "session.concept_ids_set",\n'
    '        session_id   = session_id,\n'
    '        concept_ids  = fsm.context.concept_ids,\n'
    '        concept_count = len(fsm.context.concept_ids),\n'
    '    )\n'
    '\n'
    '    # Transition to CONCEPT_TEACH for new-architecture sessions\n'
    '    if fsm.can_transition_to(State.CONCEPT_TEACH):\n'
    '        fsm.transition_to(State.CONCEPT_TEACH, trigger="session_created")\n'
    '\n'
    '    store.save(session_id, fsm, dll)'
)

if "concept_ids_set" in src:
    print("  SKIP  PATCH 2 — concept_ids already set in create_session")
    changes.append("PATCH 2 — already applied")
elif P2_OLD in src:
    src = src.replace(P2_OLD, P2_NEW, 1)
    changes.append("PATCH 2 — create_session: concept_ids set on FSM context")
else:
    _fail("PATCH 2", [
        '    dll = FactoryConversationHistory()',
        '    dll.add_stage("teach_001", "teach")',
        '    store.save(session_id, fsm, dll)',
    ])


# =============================================================================
# PATCH 3 — get_or_generate_stage: per-concept branch
#
# Insert at the top of the function, after the cache check, so concept
# sessions use the new path and legacy sessions fall through unchanged.
# =============================================================================

P3_OLD = (
    '    result = load_session(session_id)\n'
    '    if not result:\n'
    '        raise ValueError(f"Session {session_id} not found")\n'
    '    fsm, dll = result\n'
    '\n'
    '    label_id   = f"STAGE-{stage_n}"\n'
    '    label_name = f"Stage {stage_n}"\n'
    '    concepts   = _concepts_for_stage(\n'
    '        store.load_field(session_id, "problem_statement") or "", stage_n\n'
    '    )\n'
    '\n'
    '    from competitive_programming_factory.domain.fsm.states import State as _State\n'
    '    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}'
)

P3_NEW = (
    '    result = load_session(session_id)\n'
    '    if not result:\n'
    '        raise ValueError(f"Session {session_id} not found")\n'
    '    fsm, dll = result\n'
    '\n'
    '    # ── Per-concept architecture ──────────────────────────────────────\n'
    '    if fsm.is_concept_session:\n'
    '        return _get_or_generate_concept_stage(session_id, stage_n, fsm, dll)\n'
    '\n'
    '    # ── Legacy architecture (fall-through) ────────────────────────────\n'
    '    label_id   = f"STAGE-{stage_n}"\n'
    '    label_name = f"Stage {stage_n}"\n'
    '    concepts   = _concepts_for_stage(\n'
    '        store.load_field(session_id, "problem_statement") or "", stage_n\n'
    '    )\n'
    '\n'
    '    from competitive_programming_factory.domain.fsm.states import State as _State\n'
    '    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}'
)

if "_get_or_generate_concept_stage" in src:
    print("  SKIP  PATCH 3 — concept stage routing already present")
    changes.append("PATCH 3 — already applied")
elif P3_OLD in src:
    src = src.replace(P3_OLD, P3_NEW, 1)
    changes.append("PATCH 3 — get_or_generate_stage: per-concept routing added")
else:
    _fail("PATCH 3", [
        '    result = load_session(session_id)',
        '    label_id   = f"STAGE-{stage_n}"',
        '    from competitive_programming_factory.domain.fsm.states import State as _State',
        '    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}',
    ])


# =============================================================================
# PATCH 4 — process_submission: per-concept Alex + Jordan paths
#
# Insert before the existing TEACH phase block. New sessions hit the concept
# branch; old sessions fall through to the legacy TEACH block unchanged.
# =============================================================================

P4_OLD = (
    '    # ── TEACH phase — run comprehension check then advance to REQUIREMENTS ──\n'
    '    if fsm.state in {State.TEACH, State.TEACH_CHECK}:'
)

P4_NEW = (
    '    # ── Per-concept architecture: Alex + Jordan paths ─────────────────\n'
    '    if fsm.is_concept_session:\n'
    '        return _process_concept_submission(\n'
    '            session_id, stage_n, answer, images, fsm, dll,\n'
    '        )\n'
    '\n'
    '    # ── Legacy TEACH phase ────────────────────────────────────────────\n'
    '    if fsm.state in {State.TEACH, State.TEACH_CHECK}:'
)

if "_process_concept_submission" in src:
    print("  SKIP  PATCH 4 — concept submission routing already present")
    changes.append("PATCH 4 — already applied")
elif P4_OLD in src:
    src = src.replace(P4_OLD, P4_NEW, 1)
    changes.append("PATCH 4 — process_submission: per-concept routing added")
else:
    _fail("PATCH 4", [
        '    # ── TEACH phase — run comprehension check then advance to REQUIREMENTS ──',
        '    if fsm.state in {State.TEACH, State.TEACH_CHECK}:',
    ])


# =============================================================================
# PATCH 5 — get_state: expose concept progress
#
# Append concept fields to the returned dict when it's a concept session.
# =============================================================================

P5_OLD = (
    '        "agent_name":          get_agent_for_state(fsm.state.value).display_name,\n'
    '        "agent_role":          get_agent_for_state(fsm.state.value).role_label,\n'
    '    }'
)

P5_NEW = (
    '        "agent_name":          get_agent_for_state(fsm.state.value).display_name,\n'
    '        "agent_role":          get_agent_for_state(fsm.state.value).role_label,\n'
    '        "agent":               fsm.state.agent,\n'
    '        # Per-concept fields (non-null for concept sessions only)\n'
    '        "concept_id":          fsm.context.current_concept_id,\n'
    '        "concept_index":       fsm.context.concept_index,\n'
    '        "concepts_total":      fsm.context.concepts_total,\n'
    '        "concepts_confirmed":  fsm.context.concepts_confirmed,\n'
    '        "concepts_flagged":    fsm.context.concepts_flagged,\n'
    '    }'
)

if '"concept_id":          fsm.context.current_concept_id' in src:
    print("  SKIP  PATCH 5 — concept fields already in get_state")
    changes.append("PATCH 5 — already applied")
elif P5_OLD in src:
    src = src.replace(P5_OLD, P5_NEW, 1)
    changes.append("PATCH 5 — get_state: concept progress fields added")
else:
    _fail("PATCH 5", [
        '"agent_name":          get_agent_for_state(fsm.state.value).display_name,',
        '"agent_role":          get_agent_for_state(fsm.state.value).role_label,',
    ])


# =============================================================================
# APPEND — two new helper functions at the end of the file
#
# _get_or_generate_concept_stage()  — spec generation for concept sessions
# _process_concept_submission()     — submission handling for concept sessions
# _drive_concept_fsm()              — FSM transitions for concept sessions
# =============================================================================

HELPERS = '''

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
    from competitive_programming_factory.domain.fsm.states import State as _State

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
    from competitive_programming_factory.domain.fsm.states import State

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
    from competitive_programming_factory.domain.fsm.states import State

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
    """Drive FSM transitions for Jordan\'s CONCEPT_STAGE verdicts."""
    from competitive_programming_factory.domain.fsm.states import State

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
'''

if "_get_or_generate_concept_stage" in src and "_drive_concept_fsm" in src:
    print("  SKIP  HELPERS — already appended")
    changes.append("HELPERS — already applied")
else:
    src = src + HELPERS
    changes.append("HELPERS — _get_or_generate_concept_stage, _process_concept_submission, _drive_concept_fsm appended")


# =============================================================================
# Write + validate
# =============================================================================

ENGINE.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print()
    for c in changes:
        print(f"  OK  {c}")
    print()
    print(f"session_engine.py patched ({len(changes)} changes applied)")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR after patching: {e}")
    ENGINE.write_text(original)
    print("session_engine.py rolled back")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
