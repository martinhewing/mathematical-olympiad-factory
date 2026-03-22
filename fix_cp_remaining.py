"""
fix_cp_remaining.py

Fixes the 3 remaining failures from patch_cp_factory.py:
  - Patch 7  : conversation_history in session_engine.py
  - Patch 8b : SCOPE HARD LIMIT in assess_submission.j2
  - Patch 9c : already handled by fix_cp_teach_ask.py (skipped here)

Run from competitive-programming-factory repo root:
    python3 fix_cp_remaining.py
"""
import pathlib, py_compile, sys, tempfile, os

ROOT = pathlib.Path(".")
SRC  = ROOT / "src/competitive_programming_factory"
changes  = []
failures = []


def compile_check(path, original):
    tmp = tempfile.mktemp(suffix=".py")
    try:
        pathlib.Path(tmp).write_text(path.read_text())
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        path.write_text(original)
        failures.append(f"SYNTAX ERROR in {path} — rolled back: {e}")
        print(f"  ✗ SYNTAX ERROR — rolled back: {e}")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# =============================================================================
# FIX 7 — session_engine.py: conversation_history
#
# The CP engine's render_and_call context for assess_submission uses
# "candidate_answer": answer  but in a block that also has diagram_scores
# and curriculum_concepts. We insert conversation_history after candidate_answer
# regardless of surrounding context.
# =============================================================================

ENGINE = SRC / "engine/session_engine.py"
if not ENGINE.exists():
    sys.exit(f"ERROR: {ENGINE} not found")

src      = ENGINE.read_text()
original = src

if "conversation_history" in src:
    print("  SKIP  FIX 7 — conversation_history already present in session_engine.py")
    changes.append("FIX 7 — already applied")
else:
    # Step A: insert the conversation_history extraction block.
    # Look for probe_history (however it is constructed) and append after it.
    # The CP engine builds probe_history as a list comprehension; we find the
    # closing line of that block.
    import re
    # Find probe_history assignment block end
    # Pattern: "    ]\n\n    raw = render_and_call" or "    ]\n\n    # Fetch"
    # We insert the conversation_history block right before raw = render_and_call
    INJECT_ANCHOR = '    raw = render_and_call("assess_submission.j2",'
    CONVERSATION_BLOCK = (
        '    # Build stateful conversation history for assess_submission.j2.\n'
        '    # Required to continue thread after off-topic turns.\n'
        '    # NOTE: assessment and teach turns excluded — they inject raw JSON blobs\n'
        '    # which break Claude\'s JSON output contract.\n'
        '    conversation_history = [\n'
        '        {"speaker": t.get("speaker", ""), "content": t.get("content", "")}\n'
        '        for t in (dll.current.turns if dll.current else [])\n'
        '        if t.get("turn_type") in ("text_submission", "probe")\n'
        '        and t.get("content")\n'
        '    ]\n'
        '\n'
    )

    if INJECT_ANCHOR in src:
        src = src.replace(INJECT_ANCHOR, CONVERSATION_BLOCK + INJECT_ANCHOR, 1)
        # Now add conversation_history to the context dict.
        # The CP context has "candidate_answer": answer — find it and add after.
        CTX_OLD = '        "candidate_answer":      answer,\n'
        CTX_NEW = (
            '        "candidate_answer":      answer,\n'
            '        "conversation_history":  conversation_history,\n'
        )
        if CTX_OLD in src:
            src = src.replace(CTX_OLD, CTX_NEW, 1)
            ENGINE.write_text(src)
            compile_check(ENGINE, original)
            changes.append("FIX 7 — session_engine.py: conversation_history added")
            print("  OK    FIX 7 — session_engine.py: conversation_history added")
        else:
            # Try the variant with different spacing
            CTX_OLD2 = '        "candidate_answer": answer,\n'
            CTX_NEW2 = (
                '        "candidate_answer": answer,\n'
                '        "conversation_history": conversation_history,\n'
            )
            if CTX_OLD2 in src:
                src = src.replace(CTX_OLD2, CTX_NEW2, 1)
                ENGINE.write_text(src)
                compile_check(ENGINE, original)
                changes.append("FIX 7 — session_engine.py: conversation_history added")
                print("  OK    FIX 7 — session_engine.py: conversation_history added")
            else:
                failures.append(
                    'FIX 7b FAILED — "candidate_answer": answer not found in render_and_call context.\n'
                    '  Run: grep -n "candidate_answer" src/competitive_programming_factory/engine/session_engine.py'
                )
                print('  ✗     FIX 7b FAILED — candidate_answer key not found in context dict')
                ENGINE.write_text(original)  # roll back the block insertion
    else:
        failures.append(
            'FIX 7a FAILED — render_and_call("assess_submission.j2" not found in session_engine.py.\n'
            '  Run: grep -n "assess_submission" src/competitive_programming_factory/engine/session_engine.py'
        )
        print('  ✗     FIX 7a FAILED — assess_submission.j2 render call anchor not found')


# =============================================================================
# FIX 8b — templates/assess_submission.j2: SCOPE HARD LIMIT
#
# CP factory uses "━━━ YOUR ASSESSMENT TASK ━━━" — OOD uses "YOUR TASK".
# =============================================================================

TEMPLATE = SRC / "templates/assess_submission.j2"
if not TEMPLATE.exists():
    sys.exit(f"ERROR: {TEMPLATE} not found")

src = TEMPLATE.read_text()

if "YOUR SCOPE THIS STAGE" in src:
    print("  SKIP  FIX 8b — SCOPE HARD LIMIT already present in assess_submission.j2")
    changes.append("FIX 8b — already applied")
else:
    # Try both heading variants
    for old_heading in ("━━━ YOUR ASSESSMENT TASK ━━━", "━━━ YOUR TASK ━━━"):
        if old_heading in src:
            SCOPE_BLOCK = (
                "━━━ YOUR SCOPE THIS STAGE — HARD LIMIT ━━━\n"
                "You are assessing ONE concept and ONE concept only: {{ stage_title }}.\n"
                "RULES:\n"
                "- Only probe and assess {{ stage_title }}. Nothing else.\n"
                "- If the candidate's answer drifts into other concepts, acknowledge any relevant insight briefly, "
                "then steer back: 'Good instinct — we'll get to that. For now, tell me more about {{ stage_title }}.'\n"
                "- Do NOT confirm a concept the candidate hasn't addressed yet just because they mentioned it in passing.\n"
                "- Do NOT issue probes about concepts outside {{ stage_title }}.\n"
                "\n"
            )
            src = src.replace(old_heading, SCOPE_BLOCK + old_heading, 1)
            TEMPLATE.write_text(src)
            changes.append("FIX 8b — assess_submission.j2: SCOPE HARD LIMIT added")
            print(f"  OK    FIX 8b — assess_submission.j2: SCOPE HARD LIMIT added (anchor: '{old_heading}')")
            break
    else:
        failures.append(
            'FIX 8b FAILED — neither "YOUR ASSESSMENT TASK" nor "YOUR TASK" heading found.\n'
            '  Run: grep -n "YOUR.*TASK\|━━━" src/competitive_programming_factory/templates/assess_submission.j2'
        )
        print('  ✗     FIX 8b FAILED — task heading not found in assess_submission.j2')


# =============================================================================
# Summary
# =============================================================================

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
for c in changes:
    print(f"  ✓  {c}")
if failures:
    print()
    print("FAILURES (run the grep commands shown to diagnose):")
    for f in failures:
        print(f"  ✗  {f}")
    sys.exit(1)
else:
    print()
    print(f"  All {len(changes)} fixes applied.")
    print()
    print("  Ready to commit:")
    print("    git add -A")
    print("    git commit -m 'fix: sync remaining ood-factory patches to cp-factory'")
    print("    git push origin main")
