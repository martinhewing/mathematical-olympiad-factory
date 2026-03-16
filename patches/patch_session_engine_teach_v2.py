"""
patch_session_engine_teach_v2.py  — corrected to match your actual session_engine.py

Run from the competitive_programming_factory repo root:
    python3 patch_session_engine_teach_v2.py

Applies 3 patches:
  PATCH 1 — import build_teach_spec
  PATCH 2 — replace the teach/Jordan branch in get_or_generate_stage()
  PATCH 3 — pass minimum_bar + comprehension_check into teach_check.j2
"""

import pathlib, py_compile, sys, tempfile, os

ENGINE = pathlib.Path("src/competitive_programming_factory/engine/session_engine.py")
if not ENGINE.exists():
    sys.exit(f"ERROR: {ENGINE} not found. Run from repo root.")

src      = ENGINE.read_text()
original = src
changes  = []

# =============================================================================
# PATCH 1 — import build_teach_spec
# =============================================================================

OLD_P1 = "from competitive_programming_factory.engine.prompt_renderer import render_and_call"
NEW_P1 = (
    "from competitive_programming_factory.engine.prompt_renderer import render_and_call\n"
    "from competitive_programming_factory.engine.teach_spec import build_teach_spec"
)

if "from competitive_programming_factory.engine.teach_spec import build_teach_spec" in src:
    print("  SKIP  PATCH 1 — build_teach_spec already imported")
    changes.append("PATCH 1 — already applied")
elif OLD_P1 in src:
    src = src.replace(OLD_P1, NEW_P1, 1)
    changes.append("PATCH 1 — import build_teach_spec added")
else:
    sys.exit("PATCH 1 FAILED — prompt_renderer import not found")


# =============================================================================
# PATCH 2 — replace the teach/Jordan branch in get_or_generate_stage()
#
# Actual code in your file (from grep output):
#
#     from competitive_programming_factory.domain.fsm.states import State as _State
#     is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}
#     template  = "teach_lesson.j2" if is_teach else "generate_stage.j2"
#     ctx = {
#         "problem_statement":    store.load_field(session_id, "problem_statement"),
#         "candidate_level":      store.load_field(session_id, "candidate_level"),
#         "candidate_first_name": store.load_field(session_id, "candidate_first_name") or "there",
#         "session_type":         "system_design",
#         "stage_number":         stage_n,
#         "fsm_state":            fsm.state.value,
#         "fsm_mermaid":          fsm.mermaid(),
#         "progress":             fsm.context.progress_summary,
#         "confirmed_concepts":   dll.confirmed_labels,
#         "label_id":             label_id,
#         "label_name":           label_name,
#         "concepts":             concepts,
#     }
#     spec = render_and_call(template, ctx)
# =============================================================================

OLD_P2 = (
    '    from competitive_programming_factory.domain.fsm.states import State as _State\n'
    '    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}\n'
    '    template  = "teach_lesson.j2" if is_teach else "generate_stage.j2"\n'
    '    ctx = {\n'
    '        "problem_statement":    store.load_field(session_id, "problem_statement"),\n'
    '        "candidate_level":      store.load_field(session_id, "candidate_level"),\n'
    '        "candidate_first_name": store.load_field(session_id, "candidate_first_name") or "there",\n'
    '        "session_type":         "system_design",\n'
    '        "stage_number":         stage_n,\n'
    '        "fsm_state":            fsm.state.value,\n'
    '        "fsm_mermaid":          fsm.mermaid(),\n'
    '        "progress":             fsm.context.progress_summary,\n'
    '        "confirmed_concepts":   dll.confirmed_labels,\n'
    '        "label_id":             label_id,\n'
    '        "label_name":           label_name,\n'
    '        "concepts":             concepts,\n'
    '    }\n'
    '    spec = render_and_call(template, ctx)'
)

NEW_P2 = (
    '    from competitive_programming_factory.domain.fsm.states import State as _State\n'
    '    is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}\n'
    '\n'
    '    if is_teach:\n'
    '        # Curriculum-backed: skeleton from curriculum.py, enriched by Claude.\n'
    '        spec = build_teach_spec(\n'
    '            session_id           = session_id,\n'
    '            candidate_first_name = store.load_field(session_id, "candidate_first_name") or "there",\n'
    '            candidate_level      = store.load_field(session_id, "candidate_level") or "senior",\n'
    '            problem_statement    = store.load_field(session_id, "problem_statement") or "",\n'
    '        )\n'
    '    else:\n'
    '        # Jordan stage: fully dynamic, unchanged.\n'
    '        ctx = {\n'
    '            "problem_statement":    store.load_field(session_id, "problem_statement"),\n'
    '            "candidate_level":      store.load_field(session_id, "candidate_level"),\n'
    '            "candidate_first_name": store.load_field(session_id, "candidate_first_name") or "there",\n'
    '            "session_type":         "system_design",\n'
    '            "stage_number":         stage_n,\n'
    '            "fsm_state":            fsm.state.value,\n'
    '            "fsm_mermaid":          fsm.mermaid(),\n'
    '            "progress":             fsm.context.progress_summary,\n'
    '            "confirmed_concepts":   dll.confirmed_labels,\n'
    '            "label_id":             label_id,\n'
    '            "label_name":           label_name,\n'
    '            "concepts":             concepts,\n'
    '        }\n'
    '        spec = render_and_call(template, ctx)'
)

if OLD_P2 in src:
    src = src.replace(OLD_P2, NEW_P2, 1)
    changes.append("PATCH 2 — teach branch -> build_teach_spec(); Jordan branch unchanged")
else:
    # Print a diff hint to help debug further mismatches
    print("\nDEBUG — scanning for partial match:")
    anchors = [
        'is_teach = fsm.state in {_State.TEACH, _State.TEACH_CHECK}',
        'template  = "teach_lesson.j2" if is_teach else "generate_stage.j2"',
        '"stage_number":         stage_n,',
        '"label_name":           label_name,',
        'spec = render_and_call(template, ctx)',
    ]
    for a in anchors:
        found = a in src
        print(f"  {'FOUND' if found else 'MISSING'}  {a!r}")
    sys.exit("\nPATCH 2 FAILED — paste the DEBUG output above as a reply and we'll fix it")


# =============================================================================
# PATCH 3 — pass minimum_bar + comprehension_check into teach_check.j2 call
#
# Actual code (from project knowledge):
#
#         check_result = render_and_call("teach_check.j2", {
#             "problem_statement": store.load_field(session_id, "problem_statement"),
#             "candidate_first_name": first_name,
#             "candidate_answer":  answer,
#             "lesson_summary":    spec.get("ready_summary", ""),
#         })
# =============================================================================

OLD_P3 = (
    '        check_result = render_and_call("teach_check.j2", {\n'
    '            "problem_statement": store.load_field(session_id, "problem_statement"),\n'
    '            "candidate_first_name": first_name,\n'
    '            "candidate_answer":  answer,\n'
    '            "lesson_summary":    spec.get("ready_summary", ""),\n'
    '        })'
)

NEW_P3 = (
    '        check_result = render_and_call("teach_check.j2", {\n'
    '            "problem_statement":   store.load_field(session_id, "problem_statement"),\n'
    '            "candidate_first_name": first_name,\n'
    '            "candidate_answer":    answer,\n'
    '            "lesson_summary":      spec.get("ready_summary", ""),\n'
    '            "minimum_bar":         spec.get("minimum_bar", ""),\n'
    '            "comprehension_check": spec.get("comprehension_check", ""),\n'
    '        })'
)

if OLD_P3 in src:
    src = src.replace(OLD_P3, NEW_P3, 1)
    changes.append("PATCH 3 — teach_check.j2: minimum_bar + comprehension_check added")
elif "minimum_bar" in src and "teach_check.j2" in src:
    print("  SKIP  PATCH 3 — minimum_bar already in teach_check call")
    changes.append("PATCH 3 — already applied")
else:
    print("\nDEBUG — scanning for teach_check.j2 call anchors:")
    anchors = [
        'render_and_call("teach_check.j2"',
        '"lesson_summary":    spec.get("ready_summary",',
        '"candidate_answer":  answer,',
    ]
    for a in anchors:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit("\nPATCH 3 FAILED — paste the DEBUG output above as a reply")


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
    print("session_engine.py patched successfully")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR after patching: {e}")
    ENGINE.write_text(original)
    print("session_engine.py rolled back to original")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
