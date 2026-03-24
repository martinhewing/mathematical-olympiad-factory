"""
patch_session_engine_e_v4.py

Run from the competitive_programming_factory repo root:
    python3 patch_session_engine_e_v4.py

Four patches:
  PATCH 1 — import diagram_evaluator
  PATCH 2 — enrich render_and_call context (diagram eval + curriculum concepts)
  PATCH 3 — extract diagram_request after confidence_scores line
  PATCH 4 — thread diagram_request + diagram_scores through AssessmentResponse
"""

import os
import pathlib
import py_compile
import sys
import tempfile

ENGINE = pathlib.Path("src/competitive_programming_factory/engine/session_engine.py")
if not ENGINE.exists():
    sys.exit(f"ERROR: {ENGINE} not found. Run from repo root.")

src = ENGINE.read_text()
original = src
changes = []


# =============================================================================
# PATCH 1 — import diagram_evaluator
# =============================================================================

OLD_P1 = "from competitive_programming_factory.engine.prompt_renderer import render_and_call"
NEW_P1 = (
    "from competitive_programming_factory.engine.prompt_renderer import render_and_call\n"
    "from competitive_programming_factory.engine.diagram_evaluator import (\n"
    "    evaluate_diagram, diagram_passes_minimum, diagram_summary,\n"
    ")"
)

if "from competitive_programming_factory.engine.diagram_evaluator import" in src:
    print("  SKIP  PATCH 1 — already imported")
    changes.append("PATCH 1 — already applied")
elif OLD_P1 in src:
    src = src.replace(OLD_P1, NEW_P1, 1)
    changes.append("PATCH 1 — import diagram_evaluator added")
else:
    sys.exit("PATCH 1 FAILED — prompt_renderer import not found")


# =============================================================================
# PATCH 2 — enrich render_and_call context
# =============================================================================

OLD_P2 = (
    "    # Fetch concepts accumulated across prior turns this stage\n"
    "    accumulated_this_stage = sorted(get_accumulated_concepts(session_id, stage_n))\n"
    "\n"
    '    raw = render_and_call("assess_submission.j2", {\n'
    '        "problem_statement":     store.load_field(session_id, "problem_statement"),\n'
    '        "candidate_level":       store.load_field(session_id, "candidate_level"),\n'
    '        "session_type":          "system_design",\n'
    '        "stage_title":           spec.get("stage_title", f"Stage {stage_n}"),\n'
    '        "label_id":              f"STAGE-{stage_n}",\n'
    '        "concepts_tested":       spec.get("concepts_tested", []),\n'
    '        "fsm_mermaid":           fsm.mermaid(),\n'
    '        "progress":              fsm.context.progress_summary,\n'
    '        "confirmed_concepts":    dll.confirmed_labels,\n'
    '        "accumulated_concepts":  accumulated_this_stage,\n'
    '        "opening_question":      spec.get("opening_question", ""),\n'
    '        "minimum_bar":           spec.get("minimum_bar", ""),\n'
    '        "strong_answer_signals": spec.get("strong_answer_signals", []),\n'
    '        "weak_answer_signals":   spec.get("weak_answer_signals", []),\n'
    '        "probe_rounds":          fsm.context.probe_rounds,\n'
    '        "probe_limit":           probe_limit,\n'
    '        "probe_history":         probe_history,\n'
    '        "candidate_answer":      answer,\n'
    "    }, images=images or [])"
)

NEW_P2 = (
    "    # Fetch concepts accumulated across prior turns this stage\n"
    "    accumulated_this_stage = sorted(get_accumulated_concepts(session_id, stage_n))\n"
    "\n"
    "    # ── Diagram evaluation (runs before assess_submission.j2) ────────────\n"
    '    pending_rubric  = store.load_field(session_id, f"pending_diagram_rubric_{stage_n}") or []\n'
    "    diagram_scores: list[dict] = []\n"
    "    if images and pending_rubric:\n"
    "        raw_scores     = evaluate_diagram(images, pending_rubric)\n"
    "        diagram_scores = [s.to_dict() for s in raw_scores]\n"
    "        diagram_pass   = diagram_passes_minimum(raw_scores, pending_rubric)\n"
    "        log.info(\n"
    '            "diagram.evaluated",\n'
    "            session_id = session_id,\n"
    "            stage_n    = stage_n,\n"
    "            summary    = diagram_summary(raw_scores),\n"
    "            passes     = diagram_pass,\n"
    "        )\n"
    "\n"
    "    # ── Curriculum concepts for Jordan probing guide ──────────────────────\n"
    "    all_concept_ids = (\n"
    '        spec.get("all_concept_ids")\n'
    '        or spec.get("concepts_tested")\n'
    "        or []\n"
    "    )\n"
    "    curriculum_concepts: list[dict] = []\n"
    "    if all_concept_ids:\n"
    "        try:\n"
    "            from competitive_programming_factory.curriculum import CONCEPT_BY_ID\n"
    "            for cid in all_concept_ids:\n"
    "                c = CONCEPT_BY_ID.get(cid)\n"
    "                if c:\n"
    "                    curriculum_concepts.append({\n"
    '                        "concept_id":         c.id,\n'
    '                        "name":               c.name,\n'
    '                        "solicit_drawing":    c.solicit_drawing,\n'
    '                        "jordan_probes":      c.jordan_probes,\n'
    '                        "jordan_minimum_bar": c.jordan_minimum_bar,\n'
    '                        "faang_signal":       c.faang_signal,\n'
    '                        "drawing_rubric": [\n'
    '                            {"label": r.label, "description": r.description,\n'
    '                             "required": r.required}\n'
    "                            for r in c.drawing_rubric\n"
    "                        ],\n"
    "                    })\n"
    "        except Exception as _e:\n"
    '            log.warning("session_engine.curriculum_lookup_failed", error=str(_e))\n'
    "\n"
    '    raw = render_and_call("assess_submission.j2", {\n'
    '        "problem_statement":     store.load_field(session_id, "problem_statement"),\n'
    '        "candidate_level":       store.load_field(session_id, "candidate_level"),\n'
    '        "session_type":          "system_design",\n'
    '        "stage_title":           spec.get("stage_title", f"Stage {stage_n}"),\n'
    '        "label_id":              f"STAGE-{stage_n}",\n'
    '        "concepts_tested":       spec.get("concepts_tested", []),\n'
    '        "fsm_mermaid":           fsm.mermaid(),\n'
    '        "progress":              fsm.context.progress_summary,\n'
    '        "confirmed_concepts":    dll.confirmed_labels,\n'
    '        "accumulated_concepts":  accumulated_this_stage,\n'
    '        "opening_question":      spec.get("opening_question", ""),\n'
    '        "minimum_bar":           spec.get("minimum_bar", ""),\n'
    '        "strong_answer_signals": spec.get("strong_answer_signals", []),\n'
    '        "weak_answer_signals":   spec.get("weak_answer_signals", []),\n'
    '        "probe_rounds":          fsm.context.probe_rounds,\n'
    '        "probe_limit":           probe_limit,\n'
    '        "probe_history":         probe_history,\n'
    '        "candidate_answer":      answer,\n'
    "        # E) diagram fields\n"
    '        "has_candidate_diagram": bool(images),\n'
    '        "curriculum_concepts":   curriculum_concepts,\n'
    '        "diagram_scores":        diagram_scores,\n'
    "    }, images=images or [])"
)

if "has_candidate_diagram" in src:
    print("  SKIP  PATCH 2 — already applied")
    changes.append("PATCH 2 — already applied")
elif OLD_P2 in src:
    src = src.replace(OLD_P2, NEW_P2, 1)
    changes.append("PATCH 2 — diagram eval + curriculum concepts injected")
else:
    print("\nDEBUG — PATCH 2 anchors:")
    for a in [
        "# Fetch concepts accumulated across prior turns this stage",
        "accumulated_this_stage = sorted(get_accumulated_concepts",
        '"accumulated_concepts":  accumulated_this_stage,',
        '"candidate_answer":      answer,',
        "}, images=images or [])",
    ]:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit("\nPATCH 2 FAILED — paste DEBUG output as a reply")


# =============================================================================
# PATCH 3 — extract diagram_request
# Inserted right after the confidence_scores line, before the lattice block.
# =============================================================================

OLD_P3 = (
    '    confidence_scores     = raw.get("confidence_scores", {})\n'
    "\n"
    "    # ── Concept accumulation (semilattice) ────────────────────────────\n"
)

NEW_P3 = (
    '    confidence_scores     = raw.get("confidence_scores", {})\n'
    "\n"
    "    # ── diagram_request: extract + persist rubric for next submission ──\n"
    '    diagram_request: dict | None = raw.get("diagram_request")\n'
    "    if isinstance(diagram_request, dict) and diagram_request:\n"
    '        pending = diagram_request.get("rubric") or []\n'
    '        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", pending)\n'
    "        log.info(\n"
    '            "diagram.request_fired",\n'
    "            session_id   = session_id,\n"
    "            stage_n      = stage_n,\n"
    '            concept_id   = diagram_request.get("concept_id", ""),\n'
    '            required     = diagram_request.get("required", False),\n'
    "            rubric_items = len(pending),\n"
    "        )\n"
    "    else:\n"
    "        diagram_request = None\n"
    '        store.save_field(session_id, f"pending_diagram_rubric_{stage_n}", [])\n'
    "\n"
    "    # ── Concept accumulation (semilattice) ────────────────────────────\n"
)

if "diagram_request: dict | None = raw.get" in src:
    print("  SKIP  PATCH 3 — already applied")
    changes.append("PATCH 3 — already applied")
elif OLD_P3 in src:
    src = src.replace(OLD_P3, NEW_P3, 1)
    changes.append("PATCH 3 — diagram_request extraction inserted")
else:
    print("\nDEBUG — PATCH 3 anchors:")
    for a in [
        '    confidence_scores     = raw.get("confidence_scores", {})',
        "    # ── Concept accumulation (semilattice) ────────────────────────────",
    ]:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit("\nPATCH 3 FAILED — paste DEBUG output as a reply")


# =============================================================================
# PATCH 4 — thread diagram_request + diagram_scores through AssessmentResponse
# =============================================================================

OLD_P4 = (
    "    return AssessmentResponse(\n"
    "        verdict               = verdict,\n"
    "        feedback              = feedback,\n"
    '        probe                 = probe if verdict == "PARTIAL" else None,\n'
    "        concepts_demonstrated = concepts_demonstrated,\n"
    "        concepts_missing      = concepts_missing,\n"
    "        next_url              = next_url,\n"
    "        session_complete      = fsm.state == State.SESSION_COMPLETE,\n"
    "    )"
)

OLD_P4b = (
    "    return AssessmentResponse(\n"
    "        verdict               = verdict,\n"
    "        feedback              = feedback,\n"
    '        probe                 = probe if verdict == "PARTIAL" else None,\n'
    "        concepts_demonstrated = concepts_demonstrated,\n"
    "        concepts_missing      = concepts_missing,\n"
    "        next_url              = next_url,\n"
    "        session_complete      = fsm.state == State.SESSION_COMPLETE\n"
    "    )"
)

NEW_P4 = (
    "    return AssessmentResponse(\n"
    "        verdict               = verdict,\n"
    "        feedback              = feedback,\n"
    '        probe                 = probe if verdict == "PARTIAL" else None,\n'
    "        concepts_demonstrated = concepts_demonstrated,\n"
    "        concepts_missing      = concepts_missing,\n"
    "        next_url              = next_url,\n"
    "        session_complete      = fsm.state == State.SESSION_COMPLETE,\n"
    "        diagram_request       = diagram_request,\n"
    "        diagram_scores        = diagram_scores,\n"
    "    )"
)

if "diagram_request       = diagram_request" in src:
    print("  SKIP  PATCH 4 — already applied")
    changes.append("PATCH 4 — already applied")
elif OLD_P4 in src:
    src = src.replace(OLD_P4, NEW_P4, 1)
    changes.append("PATCH 4 — AssessmentResponse: diagram fields added")
elif OLD_P4b in src:
    src = src.replace(OLD_P4b, NEW_P4, 1)
    changes.append("PATCH 4 — AssessmentResponse: diagram fields added (alt form)")
else:
    print("\nDEBUG — PATCH 4: actual AssessmentResponse return block:")
    idx = src.find("    return AssessmentResponse(")
    if idx != -1:
        print(repr(src[idx : idx + 500]))
    else:
        print("  'return AssessmentResponse(' not found at all")
    sys.exit("\nPATCH 4 FAILED — paste DEBUG output as a reply")


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
    print("session_engine.py patched successfully (4/4 patches)")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR after patching: {e}")
    ENGINE.write_text(original)
    print("session_engine.py rolled back to original")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
