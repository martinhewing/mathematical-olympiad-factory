"""
patches/add_concept_accumulation.py

Run from the connectionsphere-factory repo root:
    python3 patches/add_concept_accumulation.py

Patch summary (3 files touched, 1 new file):

1. NEW  engine/concept_store.py       — accumulation layer + semilattice evaluator
2. EDIT session_engine.py             — accumulate after Claude, inject before Claude,
                                        override verdict from union evaluation
3. EDIT assess_submission.j2          — inject accumulated concepts into Claude's context
                                        + add confidence_scores to output format

Pre-flight: copies originals to .bak files.
Post-flight: syntax-checks every touched Python file.
"""

import pathlib
import sys
import py_compile
import tempfile
import os
import shutil

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT     = pathlib.Path(".")
SRC      = ROOT / "src" / "connectionsphere_factory"
ENGINE   = SRC / "engine" / "session_engine.py"
TEMPLATE = SRC / "templates" / "assess_submission.j2"
CONCEPT_STORE_DEST = SRC / "engine" / "concept_store.py"

touched: list[pathlib.Path] = []
errors:  list[str]          = []


def backup(path: pathlib.Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def check_syntax(path: pathlib.Path, content: str) -> bool:
    tmp = tempfile.mktemp(suffix=".py")
    try:
        pathlib.Path(tmp).write_text(content)
        py_compile.compile(tmp, doraise=True)
        print(f"  ✓ {path.name} syntax OK")
        return True
    except py_compile.PyCompileError as e:
        msg = f"  ✗ {path.name} SYNTAX ERROR: {e}"
        print(msg)
        errors.append(msg)
        return False
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── Pre-flight checks ────────────────────────────────────────────────────────

for path in [ENGINE, TEMPLATE]:
    if not path.exists():
        print(f"✗ FATAL: {path} not found — are you in the repo root?")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 1. INSTALL concept_store.py
# ══════════════════════════════════════════════════════════════════════════════

print("═" * 60)
print("1. Installing engine/concept_store.py")
print("═" * 60)

# Look in patches/src/... first, then patches/ directly
CONCEPT_STORE_SRC = pathlib.Path(__file__).parent / "src" / "connectionsphere_factory" / "engine" / "concept_store.py"
if not CONCEPT_STORE_SRC.exists():
    CONCEPT_STORE_SRC = pathlib.Path(__file__).parent / "concept_store.py"

if CONCEPT_STORE_SRC.exists():
    shutil.copy2(CONCEPT_STORE_SRC, CONCEPT_STORE_DEST)
    touched.append(CONCEPT_STORE_DEST)
    print(f"  ✓ Copied {CONCEPT_STORE_SRC.name} → {CONCEPT_STORE_DEST}")
    check_syntax(CONCEPT_STORE_DEST, CONCEPT_STORE_DEST.read_text())
else:
    # Check if it's already in place (manual copy)
    if CONCEPT_STORE_DEST.exists():
        print(f"  ✓ concept_store.py already in place at {CONCEPT_STORE_DEST}")
        touched.append(CONCEPT_STORE_DEST)
    else:
        msg = (
            f"  ✗ concept_store.py not found.\n"
            f"    Copy it manually to {CONCEPT_STORE_DEST}"
        )
        print(msg)
        errors.append(msg)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PATCH session_engine.py
# ══════════════════════════════════════════════════════════════════════════════

print()
print("═" * 60)
print("2. Patching session_engine.py")
print("═" * 60)

backup(ENGINE)
engine_src = ENGINE.read_text()

# ── 2a. Add import ────────────────────────────────────────────────────────────

OLD_IMPORT = "import connectionsphere_factory.session_store as store"
NEW_IMPORT = """\
import connectionsphere_factory.session_store as store
from connectionsphere_factory.engine.concept_store import (
    accumulate as accumulate_concepts,
    evaluate as evaluate_concepts,
    get_accumulated as get_accumulated_concepts,
    record_fragment,
)"""

if OLD_IMPORT in engine_src and "concept_store" not in engine_src:
    engine_src = engine_src.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("  ✓ Added concept_store import")
elif "concept_store" in engine_src:
    print("  ⚠  concept_store import already present — skipped")
else:
    print("  ✗ Could not find import anchor")
    errors.append("Import anchor not found in session_engine.py")


# ── 2b. Inject accumulated_concepts into the render_and_call context ──────────

OLD_RENDER = """\
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
        "minimum_bar":           spec.get("minimum_bar", ""),"""

NEW_RENDER = """\
    # Fetch concepts accumulated across prior turns this stage
    accumulated_this_stage = sorted(get_accumulated_concepts(session_id, stage_n))

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
        "minimum_bar":           spec.get("minimum_bar", ""),"""

if OLD_RENDER in engine_src:
    engine_src = engine_src.replace(OLD_RENDER, NEW_RENDER, 1)
    print("  ✓ Injected accumulated_concepts into render_and_call context")
else:
    print("  ✗ Could not find render_and_call block — manual patch needed")
    errors.append("render_and_call block not found in session_engine.py")


# ── 2c. After Claude returns verdict, accumulate + semilattice override ───────

OLD_VERDICT_BLOCK = """\
    verdict               = raw.get("verdict", "NOT_MET")
    feedback              = raw.get("feedback", "")
    probe                 = raw.get("probe")
    concepts_demonstrated = raw.get("concepts_demonstrated", [])
    concepts_missing      = raw.get("concepts_missing", [])

    if dll.current:
        dll.current.add_turn("claude", feedback, turn_type="assessment")
        if probe:
            dll.current.add_turn("claude", probe, turn_type="probe")

    next_url = _drive_fsm("""

NEW_VERDICT_BLOCK = """\
    verdict               = raw.get("verdict", "NOT_MET")
    feedback              = raw.get("feedback", "")
    probe                 = raw.get("probe")
    concepts_demonstrated = raw.get("concepts_demonstrated", [])
    concepts_missing      = raw.get("concepts_missing", [])
    confidence_scores     = raw.get("confidence_scores", {})

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

    next_url = _drive_fsm("""

if OLD_VERDICT_BLOCK in engine_src:
    engine_src = engine_src.replace(OLD_VERDICT_BLOCK, NEW_VERDICT_BLOCK, 1)
    print("  ✓ Injected concept accumulation + semilattice verdict override")
else:
    print("  ✗ Could not find verdict block — manual patch needed")
    errors.append("Verdict block not found in session_engine.py")


# ── 2d. Replace _concepts_for_stage with concept_store.get_required ───────────

OLD_CONCEPTS_FN = """\
def _concepts_for_stage(problem_statement: str, stage_n: int) -> list[str]:
    stage_concepts = {
        1: ["requirements_clarification", "scale_estimation", "api_design"],
        2: ["data_model", "storage_choice", "schema_design"],
        3: ["system_components", "scalability", "fault_tolerance"],
    }
    return stage_concepts.get(stage_n, [f"concept_{stage_n}_a", f"concept_{stage_n}_b"])"""

NEW_CONCEPTS_FN = """\
def _concepts_for_stage(problem_statement: str, stage_n: int) -> list[str]:
    \"\"\"Return required concepts for a stage. Canonical source: concept_store.\"\"\"
    from connectionsphere_factory.engine.concept_store import get_required
    return sorted(get_required(stage_n))"""

if OLD_CONCEPTS_FN in engine_src:
    engine_src = engine_src.replace(OLD_CONCEPTS_FN, NEW_CONCEPTS_FN, 1)
    print("  ✓ Replaced _concepts_for_stage with concept_store.get_required")
else:
    print("  ⚠  _concepts_for_stage differs — skipped (not critical)")


ENGINE.write_text(engine_src)
touched.append(ENGINE)
check_syntax(ENGINE, engine_src)


# ══════════════════════════════════════════════════════════════════════════════
# 3. PATCH assess_submission.j2
# ══════════════════════════════════════════════════════════════════════════════

print()
print("═" * 60)
print("3. Patching assess_submission.j2")
print("═" * 60)

backup(TEMPLATE)
tmpl_src = TEMPLATE.read_text()

# 3a. Inject accumulated concepts section before the question
OLD_QUESTION_SECTION = """\
━━━ THE QUESTION THAT WAS ASKED ━━━
{{ opening_question }}"""

NEW_QUESTION_SECTION = """\
━━━ CONCEPTS ALREADY DEMONSTRATED THIS STAGE (accumulated across turns) ━━━
{% if accumulated_concepts %}{% for c in accumulated_concepts %}- {{ c }}
{% endfor %}
Do NOT re-assess concepts listed above — they are already locked in.
Only assess what is NEW in this answer.
{% else %}None yet — this is the first answer for this stage.{% endif %}

━━━ THE QUESTION THAT WAS ASKED ━━━
{{ opening_question }}"""

if OLD_QUESTION_SECTION in tmpl_src:
    tmpl_src = tmpl_src.replace(OLD_QUESTION_SECTION, NEW_QUESTION_SECTION, 1)
    print("  ✓ Injected accumulated concepts section")
else:
    print("  ✗ Could not find question section anchor — manual patch needed")
    errors.append("Question section anchor not found in assess_submission.j2")

# 3b. Add confidence_scores to the output format
OLD_OUTPUT = """\
  "concepts_missing": ["concept3"],
  "internal_notes": "What you observed — for the comprehension record, not shown to candidate"
}"""

NEW_OUTPUT = """\
  "concepts_missing": ["concept3"],
  "confidence_scores": {"concept1": 0.95, "concept2": 0.80},
  "internal_notes": "What you observed — for the comprehension record, not shown to candidate"
}

IMPORTANT: confidence_scores must map each concept in concepts_demonstrated to a
float 0.0–1.0. Only concepts with confidence >= 0.85 will be accumulated.
If unsure about a concept, use 0.5 — do NOT inflate confidence."""

if OLD_OUTPUT in tmpl_src:
    tmpl_src = tmpl_src.replace(OLD_OUTPUT, NEW_OUTPUT, 1)
    print("  ✓ Added confidence_scores to output format")
else:
    print("  ⚠  Output format anchor differs — confidence_scores skipped")

TEMPLATE.write_text(tmpl_src)
touched.append(TEMPLATE)
print("  ✓ Template written")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════

print()
print("═" * 60)
print("PATCH COMPLETE")
print("═" * 60)
print()
print("Files touched:")
for f in touched:
    print(f"  • {f}")
print()

if errors:
    print("⚠  WARNINGS:")
    for e in errors:
        print(f"  {e}")
    print()
    print("Some patches could not be applied automatically.")
    print("Review the warnings above and apply manually if needed.")
    sys.exit(1)
else:
    print("All patches applied cleanly.")
    print()
    print("What changed:")
    print("  1. concept_store.py      — accumulation + semilattice evaluator (NEW)")
    print("  2. session_engine.py     — accumulate after Claude, inject before Claude,")
    print("                             override PARTIAL → CONFIRMED when union covers required")
    print("  3. assess_submission.j2  — accumulated concepts in prompt + confidence_scores output")
    print("  4. _concepts_for_stage   — now delegates to concept_store.get_required()")
    print()
    print("Run tests:")
    print("  uv run python -m pytest tests/unit/test_concept_store.py -v")
