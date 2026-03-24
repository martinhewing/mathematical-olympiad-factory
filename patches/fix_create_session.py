"""
fix_create_session.py
Run from repo root: python3 fix_create_session.py
"""

import os
import pathlib
import py_compile
import sys
import tempfile

ENGINE = pathlib.Path("src/competitive_programming_factory/engine/session_engine.py")
src = ENGINE.read_text()
original = src

OLD = '    fsm.transition_to(State.TEACH,        trigger="session_created")\n    node = dll.add_stage("requirements_001", "requirements")'

NEW = (
    "    # ── Per-concept architecture setup ──────────────────────────────\n"
    "    from competitive_programming_factory.engine.teach_spec import select_concepts_for_problem\n"
    "    _concepts = select_concepts_for_problem(problem_statement)\n"
    "    fsm.context.concept_ids = [c.id for c in _concepts]\n"
    '    fsm.transition_to(State.CONCEPT_TEACH, trigger="session_created")\n'
    '    node = dll.add_stage("concept_teach_001", "concept_teach")'
)

if OLD not in src:
    sys.exit(f"FAILED — anchor not found:\n{OLD!r}")

src = src.replace(OLD, NEW, 1)
ENGINE.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print("OK  create_session fixed — TEACH → CONCEPT_TEACH")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
    ENGINE.write_text(original)
    print("Rolled back")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
