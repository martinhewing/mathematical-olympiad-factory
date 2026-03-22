"""
patch_cp_factory.py

Applies all OOD-factory changes to the competitive-programming factory instance.
Run from the competitive-programming-factory repo root:
    python3 patch_cp_factory.py

Patches applied (10 total):
  1. config.py               — probe_limit 3 → 10
  2. domain/fsm/machine.py   — PROBE_LIMIT 3 → 10
  3. domain/fsm/states.py    — allow CONCEPT_TEACH → CONCEPT_STAGE direct transition
  4. models/schemas.py       — answer max_length 4000 → 8000
  5. engine/prompt_renderer.py — BadRequestError → 422; fix images content list
  6. engine/teach_spec.py    — max_tokens bumps (1200→2000, 800→2000)
  7. engine/session_engine.py — conversation_history extraction (text_submission + probe only)
  8. templates/assess_submission.j2 — CONVERSATION SO FAR + SCOPE HARD LIMIT sections
  9. routes/stages.py        — teach_ask: concept-scoped system prompt + already-covered guard + mic guard
 10. routes/voice.py         — Jordan soft mic guard; audio cache key fix; autoplay fix; backToAlex UI
"""

import pathlib
import py_compile
import sys
import tempfile
import os

ROOT = pathlib.Path(".")

changes  = []
failures = []


def check(path: pathlib.Path) -> None:
    if not path.exists():
        sys.exit(f"ERROR: {path} not found — run from competitive-programming-factory repo root")


def compile_check(path: pathlib.Path, original: str) -> None:
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


# Auto-detect source package
pkg = None
for candidate in ["src/competitive_programming_factory", "src/cp_factory", "src/factory"]:
    if (ROOT / candidate).is_dir():
        pkg = candidate
        break
if pkg is None:
    sys.exit(
        "ERROR: Could not detect source package directory. "
        "Expected src/competitive_programming_factory — run from repo root."
    )

SRC = ROOT / pkg
print(f"Package root: {SRC}")
print()


# =============================================================================
# PATCH 1 — config.py: probe_limit default 3 → 10
# =============================================================================

CONFIG = SRC / "config.py"
check(CONFIG)

src      = CONFIG.read_text()
original = src

if "probe_limit: int = 10" in src:
    print("  SKIP  PATCH 1 — probe_limit already 10")
    changes.append("PATCH 1 — already applied")
elif "probe_limit: int = 3" in src:
    src = src.replace("probe_limit: int = 3", "probe_limit: int = 10", 1)
    CONFIG.write_text(src)
    compile_check(CONFIG, original)
    changes.append("PATCH 1 — config.py: probe_limit 3 → 10")
    print("  OK    PATCH 1 — config.py: probe_limit 3 → 10")
else:
    failures.append("PATCH 1 FAILED — probe_limit field not found in config.py")
    print("  ✗     PATCH 1 FAILED — probe_limit field not found in config.py")


# =============================================================================
# PATCH 2 — domain/fsm/machine.py: PROBE_LIMIT 3 → 10
# =============================================================================

MACHINE = SRC / "domain/fsm/machine.py"
check(MACHINE)

src      = MACHINE.read_text()
original = src

if "PROBE_LIMIT = 10" in src:
    print("  SKIP  PATCH 2 — PROBE_LIMIT already 10")
    changes.append("PATCH 2 — already applied")
elif "PROBE_LIMIT = 3" in src:
    src = src.replace("PROBE_LIMIT = 3", "PROBE_LIMIT = 10", 1)
    MACHINE.write_text(src)
    compile_check(MACHINE, original)
    changes.append("PATCH 2 — domain/fsm/machine.py: PROBE_LIMIT 3 → 10")
    print("  OK    PATCH 2 — domain/fsm/machine.py: PROBE_LIMIT 3 → 10")
else:
    failures.append("PATCH 2 FAILED — PROBE_LIMIT constant not found in machine.py")
    print("  ✗     PATCH 2 FAILED — PROBE_LIMIT constant not found in machine.py")


# =============================================================================
# PATCH 3 — domain/fsm/states.py: allow CONCEPT_TEACH → CONCEPT_STAGE direct transition
# =============================================================================

STATES = SRC / "domain/fsm/states.py"
check(STATES)

src      = STATES.read_text()
original = src

P3_OLD = "        State.CONCEPT_STAGE:      {State.CONCEPT_TEACH_CHECK},"
P3_NEW = "        State.CONCEPT_STAGE:      {State.CONCEPT_TEACH_CHECK, State.CONCEPT_TEACH},"

if "State.CONCEPT_TEACH}" in src or "State.CONCEPT_TEACH," in src:
    print("  SKIP  PATCH 3 — CONCEPT_TEACH already in CONCEPT_STAGE allowed sources")
    changes.append("PATCH 3 — already applied")
elif P3_OLD in src:
    src = src.replace(P3_OLD, P3_NEW, 1)
    STATES.write_text(src)
    compile_check(STATES, original)
    changes.append("PATCH 3 — domain/fsm/states.py: CONCEPT_TEACH → CONCEPT_STAGE direct transition")
    print("  OK    PATCH 3 — domain/fsm/states.py: CONCEPT_TEACH direct transition added")
else:
    failures.append("PATCH 3 FAILED — CONCEPT_STAGE transition line not found in states.py")
    print("  ✗     PATCH 3 FAILED — CONCEPT_STAGE transition line not found")


# =============================================================================
# PATCH 4 — models/schemas.py: answer max_length 4000 → 8000
# =============================================================================

SCHEMAS = SRC / "models/schemas.py"
check(SCHEMAS)

src      = SCHEMAS.read_text()
original = src

if "max_length=8000" in src:
    print("  SKIP  PATCH 4 — answer max_length already 8000")
    changes.append("PATCH 4 — already applied")
elif "max_length=4000" in src:
    src = src.replace("max_length=4000", "max_length=8000", 1)
    SCHEMAS.write_text(src)
    compile_check(SCHEMAS, original)
    changes.append("PATCH 4 — models/schemas.py: answer max_length 4000 → 8000")
    print("  OK    PATCH 4 — models/schemas.py: answer max_length 4000 → 8000")
else:
    failures.append("PATCH 4 FAILED — max_length=4000 not found in schemas.py")
    print("  ✗     PATCH 4 FAILED — max_length=4000 not found in schemas.py")


# =============================================================================
# PATCH 5 — engine/prompt_renderer.py: BadRequestError → 422; fix images content list
# =============================================================================

RENDERER = SRC / "engine/prompt_renderer.py"
check(RENDERER)

src      = RENDERER.read_text()
original = src

# Sub-patch 5a: BadRequestError → clean 422
P5A_OLD = (
    "    except anthropic.BadRequestError as e:\n"
    "        raise e\n"
)
P5A_NEW = (
    "    except anthropic.BadRequestError as e:\n"
    "        raise HTTPException(\n"
    "            status_code=422,\n"
    "            detail=f\"Prompt renderer rejected by Claude API: {e}\",\n"
    "        ) from e\n"
)

if "Prompt renderer rejected by Claude API" not in src and P5A_OLD in src:
    src = src.replace(P5A_OLD, P5A_NEW, 1)
    print("  OK    PATCH 5a — prompt_renderer.py: BadRequestError → 422")
    changes.append("PATCH 5a — prompt_renderer.py: BadRequestError → clean 422")
elif "Prompt renderer rejected by Claude API" in src:
    print("  SKIP  PATCH 5a — BadRequestError handler already updated")
else:
    print("  SKIP  PATCH 5a — BadRequestError pattern not found (may be structured differently)")

# Sub-patch 5b: fix images content list so image blocks come before text
P5B_OLD = (
    '            content = [{"type": "text", "text": prompt_text}]\n'
    '            for img in images:\n'
)
P5B_NEW = (
    '            img_blocks = []\n'
    '            for img in images:\n'
)
P5B_CLOSE_OLD = (
    '                    })\n'
    '            content.extend(img_blocks)\n'
    '            content.append({"type": "text", "text": prompt_text})\n'
)

if "img_blocks" not in src and P5B_OLD in src:
    src = src.replace(P5B_OLD, P5B_NEW, 1)
    if '            content.extend(img_blocks)' not in src:
        # Add the content assembly after the loop
        P5B_LOOP_END = '                    })\n            content = [{"type": "text", "text": prompt_text}]\n'
        if P5B_LOOP_END in src:
            src = src.replace(
                P5B_LOOP_END,
                '                    })\n'
                '            content = img_blocks + [{"type": "text", "text": prompt_text}]\n',
                1,
            )
    RENDERER.write_text(src)
    compile_check(RENDERER, original)
    changes.append("PATCH 5b — prompt_renderer.py: images content list ordering fixed")
    print("  OK    PATCH 5b — prompt_renderer.py: image blocks before text")
else:
    print("  SKIP  PATCH 5b — images content list already correct or not found")


# =============================================================================
# PATCH 6 — engine/teach_spec.py: max_tokens bumps
# =============================================================================

TEACH_SPEC = SRC / "engine/teach_spec.py"
check(TEACH_SPEC)

src      = TEACH_SPEC.read_text()
original = src

applied_6 = False

# Alex spec builder: 1200 → 2000
if "max_tokens=2000" not in src or src.count("max_tokens=2000") < 2:
    if "max_tokens=1200" in src:
        src = src.replace("max_tokens=1200", "max_tokens=2000", 1)
        applied_6 = True
        print("  OK    PATCH 6a — teach_spec.py: Alex max_tokens 1200 → 2000")
        changes.append("PATCH 6a — teach_spec.py: Alex max_tokens 1200 → 2000")
    else:
        print("  SKIP  PATCH 6a — max_tokens=1200 not found (may already be updated)")
else:
    print("  SKIP  PATCH 6a — Alex max_tokens already 2000")

# Jordan spec builder: 800 → 2000
if "max_tokens=800" in src:
    src = src.replace("max_tokens=800", "max_tokens=2000", 1)
    applied_6 = True
    print("  OK    PATCH 6b — teach_spec.py: Jordan max_tokens 800 → 2000")
    changes.append("PATCH 6b — teach_spec.py: Jordan max_tokens 800 → 2000")
else:
    print("  SKIP  PATCH 6b — max_tokens=800 not found (may already be updated)")

if applied_6:
    TEACH_SPEC.write_text(src)
    compile_check(TEACH_SPEC, original)


# =============================================================================
# PATCH 7 — engine/session_engine.py: conversation_history extraction
# =============================================================================

ENGINE = SRC / "engine/session_engine.py"
check(ENGINE)

src      = ENGINE.read_text()
original = src

P7A_OLD = (
    '    probe_history = [\n'
    '        t.get("content", "")\n'
    '        for t in (dll.current.turns if dll.current else [])\n'
    '        if t.get("turn_type") == "probe" and t.get("content")\n'
    '    ]\n'
)
P7A_NEW = (
    '    probe_history = [\n'
    '        t.get("content", "")\n'
    '        for t in (dll.current.turns if dll.current else [])\n'
    '        if t.get("turn_type") == "probe" and t.get("content")\n'
    '    ]\n'
    '\n'
    '    # Build stateful conversation history for assess_submission.j2.\n'
    '    # Required to continue thread after off-topic turns.\n'
    '    # NOTE: assessment and teach turns are excluded — they inject raw JSON blobs\n'
    '    # which break Claude\'s JSON output contract.\n'
    '    conversation_history = [\n'
    '        {"speaker": t.get("speaker", ""), "content": t.get("content", "")}\n'
    '        for t in (dll.current.turns if dll.current else [])\n'
    '        if t.get("turn_type") in ("text_submission", "probe")\n'
    '        and t.get("content")\n'
    '    ]'
)

P7B_OLD = '        "candidate_answer":      answer,\n'
P7B_NEW = (
    '        "candidate_answer":      answer,\n'
    '        "conversation_history":  conversation_history,\n'
)

if "conversation_history" in src:
    print("  SKIP  PATCH 7 — conversation_history already present")
    changes.append("PATCH 7 — already applied")
else:
    applied_7 = True
    if P7A_OLD in src:
        src = src.replace(P7A_OLD, P7A_NEW, 1)
    else:
        failures.append("PATCH 7a FAILED — probe_history block not found in session_engine.py")
        print("  ✗     PATCH 7a FAILED — probe_history block not found")
        applied_7 = False

    if applied_7 and P7B_OLD in src:
        src = src.replace(P7B_OLD, P7B_NEW, 1)
    elif applied_7:
        failures.append("PATCH 7b FAILED — candidate_answer key not found in render_and_call context")
        print("  ✗     PATCH 7b FAILED — candidate_answer key not found")
        applied_7 = False

    if applied_7:
        ENGINE.write_text(src)
        compile_check(ENGINE, original)
        changes.append("PATCH 7 — session_engine.py: conversation_history (text_submission + probe only)")
        print("  OK    PATCH 7 — session_engine.py: conversation_history added")


# =============================================================================
# PATCH 8 — templates/assess_submission.j2: CONVERSATION SO FAR + SCOPE HARD LIMIT
# =============================================================================

TEMPLATE = SRC / "templates/assess_submission.j2"
check(TEMPLATE)

src = TEMPLATE.read_text()

P8A_OLD = "━━━ CANDIDATE'S ANSWER ━━━\n{{ candidate_answer }}"
P8A_NEW = (
    "━━━ CONVERSATION SO FAR THIS STAGE ━━━\n"
    "{% if conversation_history %}{% for turn in conversation_history %}{{ turn.speaker | upper }}: {{ turn.content }}\n"
    "{% endfor %}{% else %}No prior turns — this is the opening answer.\n"
    "{% endif %}\n"
    "IMPORTANT: The conversation above is the full thread. If the candidate went off-topic in a prior turn, DO NOT reset. "
    "Continue from the last substantive probe that was not yet answered adequately.\n\n"
    "━━━ CANDIDATE'S CURRENT ANSWER ━━━\n"
    "{{ candidate_answer }}"
)

P8B_OLD = "━━━ YOUR TASK ━━━"
P8B_NEW = (
    "━━━ YOUR SCOPE THIS STAGE — HARD LIMIT ━━━\n"
    "You are assessing ONE concept and ONE concept only: {{ stage_title }}.\n"
    "RULES:\n"
    "- Only probe and assess {{ stage_title }}. Nothing else.\n"
    "- If the candidate's answer drifts into other concepts, acknowledge any relevant insight briefly, "
    "then steer back: 'Good instinct — we'll get to that. For now, tell me more about {{ stage_title }}.'\n"
    "- Do NOT confirm a concept the candidate hasn't addressed yet just because they mentioned it in passing.\n"
    "- Do NOT issue probes about concepts outside {{ stage_title }}.\n"
    "\n"
    "━━━ YOUR TASK ━━━"
)

applied_8 = 0

if "CONVERSATION SO FAR" not in src:
    if P8A_OLD in src:
        src = src.replace(P8A_OLD, P8A_NEW, 1)
        applied_8 += 1
    else:
        failures.append("PATCH 8a FAILED — CANDIDATE'S ANSWER section not found in assess_submission.j2")
        print("  ✗     PATCH 8a FAILED — CANDIDATE'S ANSWER section not found")
else:
    print("  SKIP  PATCH 8a — CONVERSATION SO FAR already present")
    applied_8 += 1

if "YOUR SCOPE THIS STAGE" not in src:
    if P8B_OLD in src:
        src = src.replace(P8B_OLD, P8B_NEW, 1)
        applied_8 += 1
    else:
        failures.append("PATCH 8b FAILED — YOUR TASK section not found in assess_submission.j2")
        print("  ✗     PATCH 8b FAILED — YOUR TASK section not found")
else:
    print("  SKIP  PATCH 8b — SCOPE HARD LIMIT already present")
    applied_8 += 1

if applied_8 > 0:
    TEMPLATE.write_text(src)
    changes.append(f"PATCH 8 — assess_submission.j2: {applied_8}/2 sections added")
    print(f"  OK    PATCH 8 — assess_submission.j2: {applied_8}/2 sections applied")


# =============================================================================
# PATCH 9 — routes/stages.py: Form max_length + answer length guard + teach_ask guards
# =============================================================================

STAGES = SRC / "routes/stages.py"
check(STAGES)

src      = STAGES.read_text()
original = src

# Sub-patch 9a: Form max_length 4000 → 8000
P9A_OLD = "    answer:     str = Form(..., max_length=4000),"
P9A_NEW = "    answer:     str = Form(..., max_length=8000),"

if "Form(..., max_length=8000)" not in src and P9A_OLD in src:
    src = src.replace(P9A_OLD, P9A_NEW, 1)
    print("  OK    PATCH 9a — stages.py: Form max_length 4000 → 8000")
    changes.append("PATCH 9a — stages.py: Form max_length 4000 → 8000")
else:
    print("  SKIP  PATCH 9a — Form max_length already updated or not found")

# Sub-patch 9b: answer length guard
P9B_OLD = (
    '    if len(answer.strip()) < 10:\n'
    '        raise HTTPException(status_code=422, detail="Answer is too short (minimum 10 characters)")\n'
    '    if not store.exists(session_id):\n'
)
P9B_NEW = (
    '    if len(answer.strip()) < 10:\n'
    '        raise HTTPException(status_code=422, detail="Answer is too short (minimum 10 characters)")\n'
    '\n'
    '    if len(answer.strip()) > 4000:\n'
    '        raise HTTPException(\n'
    '            status_code=422,\n'
    '            detail=(\n'
    '                "Sorry, we can\'t process an answer that long. "\n'
    '                "Please keep your response to around 700 words — "\n'
    '                "that\'s roughly 4-5 minutes of speaking at a normal pace."\n'
    '            ),\n'
    '        )\n'
    '\n'
    '    if not store.exists(session_id):\n'
)

if "we can't process an answer that long" not in src and P9B_OLD in src:
    src = src.replace(P9B_OLD, P9B_NEW, 1)
    print("  OK    PATCH 9b — stages.py: answer length guard added")
    changes.append("PATCH 9b — stages.py: answer > 4000 char guard")
else:
    print("  SKIP  PATCH 9b — answer length guard already present or anchor not found")

# Sub-patch 9c: teach_ask concept-scoped system prompt + already-covered guard
P9C_OLD = (
    '    system_prompt = (\n'
    '        TutorAgent().system_prompt(first_name)\n'
    '        + f"\\n\\nSESSION CONTEXT:\\nProblem: {problem}\\n"\n'
    '        + f"Concepts being taught:\\n{concept_text}\\n\\n"\n'
    '        + "Respond naturally as Alex in 2-4 sentences. "\n'
    '        + "If the candidate goes off-topic, acknowledge briefly and redirect warmly. "\n'
    '        + "Do NOT reset or restart — always continue forward from where you left off. "\n'
    '        + "Do NOT repeat or re-summarise anything in the ALREADY SAID list above. "\n'
    '        + \'Return ONLY JSON: {"reply": "your response"}\'\n'
    '    )\n'
)
P9C_NEW = (
    '    # ── Build \'already covered\' guard from Alex\'s prior turns ─────────\n'
    '    alex_prior = [\n'
    '        t["content"] for t in (dll.current.turns if dll.current else [])\n'
    '        if t.get("speaker") == "alex" and t.get("content")\n'
    '    ]\n'
    '    already_covered = (\n'
    '        "WHAT YOU HAVE ALREADY SAID (do NOT repeat any of this):\\n"\n'
    '        + "\\n".join(f"- {t[:120]}" for t in alex_prior)\n'
    '        if alex_prior else\n'
    '        "Nothing covered yet — this is your opening."\n'
    '    )\n'
    '\n'
    '    # ── Extract the SINGLE concept in scope for this segment ──────────\n'
    '    concept_name        = spec.get("stage_title") or spec.get("concept_id", "the current concept")\n'
    '    concept_explanation = spec.get("explanation", "")\n'
    '    concept_analogy     = spec.get("analogy", "")\n'
    '    concept_probe_warn  = spec.get("probe_warning", "")\n'
    '    if not concept_explanation and spec.get("concepts"):\n'
    '        c = spec["concepts"][0]\n'
    '        concept_name        = c.get("name", concept_name)\n'
    '        concept_explanation = c.get("explanation", "")\n'
    '        concept_probe_warn  = c.get("probe_warning", "")\n'
    '\n'
    '    system_prompt = (\n'
    '        TutorAgent().system_prompt(first_name)\n'
    '        + f"\\n\\n"\n'
    '        + "━━━ YOUR SCOPE THIS SEGMENT — HARD LIMIT ━━━\\n"\n'
    '        + f"You are teaching ONE concept and ONE concept only: **{concept_name}**.\\n"\n'
    '        + f"Problem context: {problem}\\n"\n'
    '        + f"What {concept_name} means: {concept_explanation}\\n"\n'
    '        + (f"Key probe point: {concept_probe_warn}\\n" if concept_probe_warn else "")\n'
    '        + (f"Your analogy: {concept_analogy}\\n" if concept_analogy else "")\n'
    '        + "\\n"\n'
    '        + "RULES:\\n"\n'
    '        + f"- ONLY discuss {concept_name}. Nothing else.\\n"\n'
    '        + "- If the candidate asks about a different concept, redirect warmly: "\n'
    '          f"\'Great question — we\'ll cover that in its own segment. "\n'
    '          f"For now let\'s stay focused on {concept_name}.\'\\n"\n'
    '        + "- Do NOT preview, hint at, or explain concepts from other segments.\\n"\n'
    '        + "- Do NOT expand the scope even if the candidate pushes you to.\\n"\n'
    '        + "\\n"\n'
    '        + already_covered + "\\n\\n"\n'
    '        + "Respond in 2-4 sentences. "\n'
    '        + "Do NOT repeat anything in the ALREADY SAID list above. "\n'
    '        + \'Return ONLY JSON: {"reply": "your response"}\'\n'
    '    )\n'
)

if "YOUR SCOPE THIS SEGMENT" not in src:
    if P9C_OLD in src:
        src = src.replace(P9C_OLD, P9C_NEW, 1)
        print("  OK    PATCH 9c — stages.py: teach_ask concept-scoped system prompt")
        changes.append("PATCH 9c — stages.py: teach_ask scoped to single concept + already-covered guard")
    else:
        failures.append("PATCH 9c FAILED — teach_ask system_prompt block not found in stages.py")
        print("  ✗     PATCH 9c FAILED — system_prompt block not found")
else:
    print("  SKIP  PATCH 9c — concept scope already present in teach_ask")

# Sub-patch 9d: accidental mic guard in teach_ask (< 8 words)
P9D_ANCHOR = "    # ── 2. Short-circuit accidental/empty recordings"
P9D_OLD = (
    "    transcript   = await transcribe(audio_bytes, content_type=content_type)\n"
    "\n"
    "    result = engine.load_session(session_id)\n"
)
P9D_NEW = (
    "    transcript   = await transcribe(audio_bytes, content_type=content_type)\n"
    "\n"
    "    # ── 2. Short-circuit accidental/empty recordings ──────────────────────\n"
    "    if len(transcript.split()) < 8:\n"
    "        nudge = (\n"
    "            \"Sorry, I didn't catch that — it sounded like the mic cut off. \"\n"
    "            \"Take your time and ask when you're ready.\"\n"
    "        )\n"
    "        return {\n"
    "            \"verdict\": \"PARTIAL\", \"feedback\": nudge, \"probe\": nudge,\n"
    "            \"transcript\": transcript, \"concepts_demonstrated\": [],\n"
    "            \"concepts_missing\": [], \"next_url\": f\"/session/{session_id}/stage/1\",\n"
    "            \"session_complete\": False,\n"
    "        }\n"
    "\n"
    "    result = engine.load_session(session_id)\n"
)

if P9D_ANCHOR not in src:
    if P9D_OLD in src:
        src = src.replace(P9D_OLD, P9D_NEW, 1)
        print("  OK    PATCH 9d — stages.py: teach_ask accidental mic guard")
        changes.append("PATCH 9d — stages.py: teach_ask mic guard (< 8 words)")
    else:
        print("  SKIP  PATCH 9d — teach_ask mic guard anchor not found (may be structured differently)")
else:
    print("  SKIP  PATCH 9d — mic guard already present in teach_ask")

STAGES.write_text(src)
compile_check(STAGES, original)


# =============================================================================
# PATCH 10 — routes/voice.py: Jordan soft mic guard + cache key + autoplay + backToAlex
# =============================================================================

VOICE = SRC / "routes/voice.py"
check(VOICE)

src      = VOICE.read_text()
original = src

# Sub-patch 10a: Jordan hard 422 → soft mic guard
P10A_OLD = (
    "    if len(transcript.strip()) < 10:\n"
    "        raise HTTPException(\n"
    "            status_code=422,\n"
    "            detail=\"We couldn't hear that clearly. Check your microphone is connected and try again — speak for at least 3 seconds.\",\n"
    "        )\n"
)
P10A_NEW = (
    "    # Soft guard — accidental press or mic noise. Return a nudge without\n"
    "    # touching the DLL so Jordan's conversation thread is unaffected.\n"
    "    if len(transcript.split()) < 8:\n"
    "        nudge = (\n"
    "            \"Sorry, I didn't catch that — it sounded like the mic cut off. \"\n"
    "            \"Take your time and answer when you're ready.\"\n"
    "        )\n"
    "        return {\n"
    "            \"verdict\":               \"PARTIAL\",\n"
    "            \"feedback\":              nudge,\n"
    "            \"probe\":                 nudge,\n"
    "            \"transcript\":            transcript,\n"
    "            \"concepts_demonstrated\": [],\n"
    "            \"concepts_missing\":      [],\n"
    "            \"next_url\":              f\"/session/{session_id}/stage/{stage_n}\",\n"
    "            \"session_complete\":      False,\n"
    "            \"input_mode\":            \"voice\",\n"
    "        }\n"
)

if "Jordan's conversation thread is unaffected" not in src:
    if P10A_OLD in src:
        src = src.replace(P10A_OLD, P10A_NEW, 1)
        print("  OK    PATCH 10a — voice.py: Jordan hard 422 → soft mic guard")
        changes.append("PATCH 10a — voice.py: Jordan mic guard soft nudge")
    else:
        failures.append("PATCH 10a FAILED — Jordan 422 guard not found in voice.py")
        print("  ✗     PATCH 10a FAILED — 422 guard not found")
else:
    print("  SKIP  PATCH 10a — Jordan soft guard already present")

# Sub-patch 10b: long transcript guard
P10B_OLD = "    if len(transcript.strip()) > 4000:\n"
if P10B_OLD not in src:
    P10B_ANCHOR = "            \"input_mode\":            \"voice\",\n        }\n\n"
    if P10B_ANCHOR in src:
        P10B_INSERT = (
            "            \"input_mode\":            \"voice\",\n"
            "        }\n"
            "\n"
            "    if len(transcript.strip()) > 4000:\n"
            "        raise HTTPException(\n"
            "            status_code=422,\n"
            "            detail=(\n"
            "                \"That recording was too long to process. \"\n"
            "                \"Please keep your answer to around 4-5 minutes and try again.\"\n"
            "            ),\n"
            "        )\n"
            "\n"
        )
        src = src.replace(P10B_ANCHOR, P10B_INSERT, 1)
        print("  OK    PATCH 10b — voice.py: long transcript guard added")
        changes.append("PATCH 10b — voice.py: long transcript > 4000 guard")
    else:
        print("  SKIP  PATCH 10b — anchor not found, skipping long transcript guard")
else:
    print("  SKIP  PATCH 10b — long transcript guard already present")

# Sub-patch 10c: audio cache key includes concept teach states
P10C_OLD = (
    '    _phase = "teach" if (_fsm_result and _fsm_result[0].state.value in {"Teach", "Teach Comprehension Check"}) else "interview"\n'
)
P10C_NEW = (
    '    _TEACH_VALS = {"Teach", "Teach Comprehension Check", "Concept Teach", "Concept Teach Check"}\n'
    '    _phase = "teach" if (_fsm_result and _fsm_result[0].state.value in _TEACH_VALS) else "interview"\n'
)

if "_TEACH_VALS" not in src:
    if P10C_OLD in src:
        src = src.replace(P10C_OLD, P10C_NEW, 1)
        print("  OK    PATCH 10c — voice.py: audio cache key includes concept teach states")
        changes.append("PATCH 10c — voice.py: audio cache key concept teach states")
    else:
        print("  SKIP  PATCH 10c — audio phase line not found (may already include concept states)")
else:
    print("  SKIP  PATCH 10c — _TEACH_VALS already present")

# Sub-patch 10d: autoplay failure → show play button + enable mic
P10D_OLD = "  audio.play().catch(() => {{ label.textContent = 'no audio'; enableRecording(); }});"
P10D_NEW = (
    "  audio.play().catch(() => {{\n"
    "    label.textContent = '▶ Play';\n"
    "    label.onclick     = () => audio.play();\n"
    "    enableRecording();\n"
    "  }});"
)

if "▶ Play" not in src:
    if P10D_OLD in src:
        src = src.replace(P10D_OLD, P10D_NEW, 1)
        print("  OK    PATCH 10d — voice.py: autoplay failure → play button")
        changes.append("PATCH 10d — voice.py: autoplay catch shows play button")
    else:
        print("  SKIP  PATCH 10d — autoplay catch line not found")
else:
    print("  SKIP  PATCH 10d — play button already present")

# Sub-patch 10e: backToAlex button feedback
P10E_OLD = "async function backToAlex() {{\n  "
P10E_NEW = (
    "async function backToAlex() {{\n"
    "  const btn = document.getElementById('back-to-alex-btn');\n"
    "  if (btn) {{\n"
    "    btn.disabled = true;\n"
    "    btn.textContent = '← Handing back…';\n"
    "    btn.style.opacity = '0.7';\n"
    "  }}\n"
    "  try {{\n"
    "    const audio = document.getElementById('stage-audio');\n"
    "    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}\n"
    "    await fetch(`/session/${{SESSION_ID}}/teach/restart`, {{method:'POST'}});\n"
    "  }} catch(e) {{\n"
    "    if (btn) {{ btn.disabled = false; btn.textContent = '← Alex'; btn.style.opacity = ''; }}\n"
    "    return;\n"
    "  }}\n"
    "  if (btn) {{ btn.textContent = '← Loading…'; }}\n"
    "  const readyBtn = document.getElementById('ready-btn');\n"
    "  if (readyBtn) {{ readyBtn.disabled = false; readyBtn.textContent = 'Test me →'; }}\n"
    "  await loadStage(1);\n"
    "  if (btn) {{ btn.disabled = false; btn.textContent = '← Alex'; btn.style.opacity = ''; }}\n"
    "}}\n\nasync function _backToAlex_old() {{\n  "
)

if "← Handing back…" not in src:
    if P10E_OLD in src:
        src = src.replace(P10E_OLD, P10E_NEW, 1)
        print("  OK    PATCH 10e — voice.py: backToAlex button feedback")
        changes.append("PATCH 10e — voice.py: backToAlex 'Handing back…' feedback")
    else:
        print("  SKIP  PATCH 10e — backToAlex block not found (UI may differ)")
else:
    print("  SKIP  PATCH 10e — backToAlex already updated")

# Sub-patch 10f: handoverToJordan reloads stage instead of advancing
P10F_OLD = "  advanceStage(currentStage);\n}}\n\nasync function backToAlex()"
P10F_NEW = (
    "  // Reload same stage — FSM now on CONCEPT_STAGE, cache miss will get Jordan spec\n"
    "  loadStage(currentStage);\n"
    "}}\n\nasync function backToAlex()"
)

if "Reload same stage" not in src:
    if P10F_OLD in src:
        src = src.replace(P10F_OLD, P10F_NEW, 1)
        print("  OK    PATCH 10f — voice.py: handoverToJordan reloads stage")
        changes.append("PATCH 10f — voice.py: handoverToJordan loadStage not advanceStage")
    else:
        print("  SKIP  PATCH 10f — handoverToJordan block not found")
else:
    print("  SKIP  PATCH 10f — handoverToJordan already reloads")

VOICE.write_text(src)
compile_check(VOICE, original)


# =============================================================================
# Summary
# =============================================================================

print()
print("=" * 70)
print("PATCH SUMMARY")
print("=" * 70)
for c in changes:
    print(f"  ✓  {c}")
if failures:
    print()
    print("FAILURES:")
    for f in failures:
        print(f"  ✗  {f}")
print()
if failures:
    print(f"  {len(changes)} applied, {len(failures)} failed.")
    print("  Review failures above — manual fix may be needed.")
    sys.exit(1)
else:
    print(f"  All {len(changes)} patches applied (or already present). No failures.")
    print()
    print("  Next step — run the teach_ask full upgrade:")
    print("    python3 fix_cp_teach_ask.py")
    print()
    print("  Then deploy:")
    print("    git add -A && git commit -m 'fix: sync ood-factory improvements to cp-factory'")
    print("    git push origin main")
