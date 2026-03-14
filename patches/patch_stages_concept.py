"""
patch_stages_concept.py

Run from the connectionsphere_factory repo root:
    python3 patch_stages_concept.py

Two patches to src/connectionsphere_factory/routes/stages.py:

  PATCH 1  GET /session/{id}/stage/{n}
           Add concept fields to response: agent, concept_id, scene_hook,
           solicit_drawing, drawing_rubric, concept_index, concepts_total,
           concepts_confirmed, reteach_count.

  PATCH 2  GET /session/{id}/progress  (new endpoint)
           Returns per-concept progress for the UI progress bar.

  PATCH 3  teach/restart: also handles CONCEPT_TEACH state.
"""

import pathlib, py_compile, sys, tempfile, os

STAGES = pathlib.Path("src/connectionsphere_factory/routes/stages.py")
if not STAGES.exists():
    sys.exit(f"ERROR: {STAGES} not found — run from repo root")

src      = STAGES.read_text()
original = src
changes  = []


def _fail(patch_n: str, anchors: list[str]) -> None:
    print(f"\nDEBUG — {patch_n} anchors:")
    for a in anchors:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit(f"\n{patch_n} FAILED — paste DEBUG output as a reply")


# =============================================================================
# PATCH 1 — enrich GET /stage/{n} response with concept fields
# =============================================================================

P1_OLD = (
    '        "comprehension_check": spec.get("comprehension_check", ""),\n'
    '        "concepts":          spec.get("concepts", []),\n'
    '        "greeting":          spec.get("greeting", ""),\n'
    '        "agent_name":        state.get("agent_name", ""),\n'
    '        "agent_role":        state.get("agent_role", ""),\n'
    '    }'
)

P1_NEW = (
    '        "comprehension_check": spec.get("comprehension_check", ""),\n'
    '        "comprehension_check_mode": spec.get("comprehension_check_mode", "verbal"),\n'
    '        "concepts":          spec.get("concepts", []),\n'
    '        "greeting":          spec.get("greeting", ""),\n'
    '        "agent_name":        state.get("agent_name", ""),\n'
    '        "agent_role":        state.get("agent_role", ""),\n'
    '        # Per-concept fields (populated for concept-architecture sessions)\n'
    '        "agent":             state.get("agent", spec.get("agent", "")),\n'
    '        "concept_id":        state.get("concept_id", spec.get("concept_id", "")),\n'
    '        "scene_hook":        spec.get("scene_hook", ""),\n'
    '        "solicit_drawing":   spec.get("solicit_drawing", False),\n'
    '        "drawing_rubric":    spec.get("drawing_rubric", []),\n'
    '        "concept_index":     state.get("concept_index", 0),\n'
    '        "concepts_total":    state.get("concepts_total", 0),\n'
    '        "concepts_confirmed":state.get("concepts_confirmed", []),\n'
    '        "reteach_count":     result[0].context.reteach_count if result else 0,\n'
    '    }'
)

if "scene_hook" in src and "solicit_drawing" in src:
    print("  SKIP  PATCH 1 — concept fields already in GET stage response")
    changes.append("PATCH 1 — already applied")
elif P1_OLD in src:
    src = src.replace(P1_OLD, P1_NEW, 1)
    changes.append("PATCH 1 — GET stage: concept fields added to response")
else:
    _fail("PATCH 1", [
        '        "comprehension_check": spec.get("comprehension_check", ""),',
        '        "concepts":          spec.get("concepts", []),',
        '        "agent_name":        state.get("agent_name", ""),',
    ])


# =============================================================================
# PATCH 2 — new GET /session/{id}/progress endpoint
# =============================================================================

PROGRESS_ENDPOINT = '''

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
'''

if "get_progress" in src:
    print("  SKIP  PATCH 2 — /progress endpoint already present")
    changes.append("PATCH 2 — already applied")
else:
    # Append before the submit endpoint so it groups logically with get_stage
    # Insert after the closing brace of get_stage's return dict + before @router.post
    P2_ANCHOR = '@router.post("/session/{session_id}/teach/restart")'
    if P2_ANCHOR in src:
        src = src.replace(P2_ANCHOR, PROGRESS_ENDPOINT + "\n\n" + P2_ANCHOR, 1)
        changes.append("PATCH 2 — GET /progress endpoint added")
    else:
        # Fallback: append near end before submit_stage
        P2_ANCHOR2 = '@router.post("/session/{session_id}/stage/{stage_n}/submit")'
        if P2_ANCHOR2 in src:
            src = src.replace(P2_ANCHOR2, PROGRESS_ENDPOINT + "\n\n" + P2_ANCHOR2, 1)
            changes.append("PATCH 2 — GET /progress endpoint added (alt anchor)")
        else:
            _fail("PATCH 2", [P2_ANCHOR, P2_ANCHOR2])


# =============================================================================
# PATCH 3 — teach/restart: also handle CONCEPT_TEACH state
# =============================================================================

P3_OLD = (
    '    from connectionsphere_factory.domain.fsm.states import State as _State\n'
    '    if fsm.state in {_State.TEACH, _State.TEACH_CHECK}:'
)

P3_NEW = (
    '    from connectionsphere_factory.domain.fsm.states import State as _State\n'
    '    if fsm.state in {\n'
    '        _State.TEACH, _State.TEACH_CHECK,\n'
    '        _State.CONCEPT_TEACH, _State.CONCEPT_TEACH_CHECK, _State.CONCEPT_STAGE,\n'
    '    }:'
)

if "_State.CONCEPT_TEACH," in src:
    print("  SKIP  PATCH 3 — teach/restart already handles concept states")
    changes.append("PATCH 3 — already applied")
elif P3_OLD in src:
    src = src.replace(P3_OLD, P3_NEW, 1)
    changes.append("PATCH 3 — teach/restart: handles CONCEPT_TEACH/CHECK/STAGE states")
else:
    _fail("PATCH 3", [
        '    from connectionsphere_factory.domain.fsm.states import State as _State',
        '    if fsm.state in {_State.TEACH, _State.TEACH_CHECK}:',
    ])


# =============================================================================
# Write + validate
# =============================================================================

STAGES.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print()
    for c in changes:
        print(f"  OK  {c}")
    print()
    print(f"stages.py patched ({len(changes)} changes applied)")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR after patching: {e}")
    STAGES.write_text(original)
    print("stages.py rolled back")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
