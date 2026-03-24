"""
patch_voice_concept.py

Run from the competitive_programming_factory repo root:
    python3 patch_voice_concept.py

Three patches to src/competitive_programming_factory/routes/voice.py:

  PATCH 1  _stage_text(): recognise Concept Teach/Check/Stage states +
           shorten TTS to greeting only for concept sessions

  PATCH 2  CSS: progress pills styles added to _interview_html()

  PATCH 3  HTML + JS: progress bar element + loadProgress() + hook into
           loadStage() and advanceStage()
"""

import os
import pathlib
import py_compile
import sys
import tempfile

VOICE = pathlib.Path("src/competitive_programming_factory/routes/voice.py")
if not VOICE.exists():
    sys.exit(f"ERROR: {VOICE} not found — run from repo root")

src = VOICE.read_text()
original = src
changes = []


def _fail(patch_n: str, anchors: list[str]) -> None:
    print(f"\nDEBUG — {patch_n} anchors:")
    for a in anchors:
        print(f"  {'FOUND' if a in src else 'MISSING'}  {a!r}")
    sys.exit(f"\n{patch_n} FAILED — paste DEBUG output as a reply")


# =============================================================================
# PATCH 1 — _stage_text(): concept session TTS shortening
#
# OLD: teach phase sends greeting + lesson + concept_text (all 3 concepts) + check
# NEW: teach phase sends greeting only when in concept mode;
#      concept stage sends scene_hook + opening_question
#      Both new states recognised alongside legacy "Teach" / "Teach Comprehension Check"
# =============================================================================

P1_OLD = (
    "    # Teach phase: use lesson greeting + lesson content\n"
    '    if fsm_state in {"Teach", "Teach Comprehension Check"}:\n'
    "        greeting = agent.greeting(first_name)\n"
    '        lesson = spec.get("greeting", "")\n'
    '        check = spec.get("comprehension_check", "")\n'
    "        parts = [p for p in [greeting, lesson, check] if p]"
)

P1_OLD_FALLBACK = (
    "    # Teach phase: use lesson greeting + lesson content\n"
    '    if fsm_state in {"Teach", "Teach Comprehension Check"}:\n'
    "        greeting = agent.greeting(first_name)\n"
    '        lesson   = spec.get("greeting", "")\n'
    '        concepts = spec.get("concepts", [])\n'
    '        concept_text = "  ".join(\n'
    "            f\"{c.get('name','')}: {c.get('explanation','')}  For example: {c.get('example','')}\"\n"
    "            for c in concepts[:3]\n"
    "        )\n"
    '        check = spec.get("comprehension_check", "")\n'
    "        parts = [p for p in [greeting, lesson, concept_text, check] if p]"
)

P1_NEW = (
    "    # Teach phase: determine TTS text based on session architecture\n"
    "    _TEACH_STATES = {\n"
    '        "Teach", "Teach Comprehension Check",\n'
    '        "Concept Teach", "Concept Teach Check",\n'
    "    }\n"
    '    _JORDAN_STATES = {"Concept Stage"}\n'
    "    if fsm_state in _TEACH_STATES:\n"
    '        greeting = spec.get("greeting", "")\n'
    '        check    = spec.get("comprehension_check", "")\n'
    "        # For concept sessions, just speak the greeting —\n"
    "        # full lesson is shown on screen. Fast TTS (~150 chars).\n"
    "        # For legacy sessions, include check question too.\n"
    '        if fsm_state in {"Concept Teach", "Concept Teach Check"}:\n'
    "            parts = [p for p in [greeting] if p]\n"
    "        else:\n"
    "            parts = [p for p in [greeting, check] if p]\n"
    "    elif fsm_state in _JORDAN_STATES:\n"
    "        # Concept stage: scene hook + opening question\n"
    '        scene_hook = spec.get("scene_hook", "")\n'
    '        question   = spec.get("opening_question", "")\n'
    "        parts      = [p for p in [scene_hook, question] if p]"
)

if '"Concept Teach"' in src and "_TEACH_STATES" in src:
    print("  SKIP  PATCH 1 — concept states already in _stage_text()")
    changes.append("PATCH 1 — already applied")
elif P1_OLD in src:
    src = src.replace(P1_OLD, P1_NEW, 1)
    changes.append("PATCH 1 — _stage_text(): concept states + TTS shortening")
elif P1_OLD_FALLBACK in src:
    src = src.replace(P1_OLD_FALLBACK, P1_NEW, 1)
    changes.append("PATCH 1 — _stage_text(): concept states + TTS shortening (fallback match)")
else:
    _fail(
        "PATCH 1",
        [
            "    # Teach phase: use lesson greeting + lesson content",
            '    if fsm_state in {"Teach", "Teach Comprehension Check"}:',
        ],
    )


# =============================================================================
# PATCH 2 — CSS: progress pills
#
# Inject into the <style> block in _interview_html just before the closing </style>
# =============================================================================

P2_CSS = """
/* ── Concept progress pills ──────────────────────────────────── */
.progress-bar {{
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px;
  overflow-x: auto;
  scrollbar-width: none;
  flex: 1;
  min-width: 0;
}}
.progress-bar::-webkit-scrollbar {{ display: none; }}

.concept-pill {{
  flex-shrink: 0;
  height: 6px;
  width: 24px;
  border-radius: 3px;
  background: var(--subtle);
  transition: background 0.3s, width 0.3s;
  cursor: default;
  position: relative;
}}
.concept-pill[title]:hover::after {{
  content: attr(title);
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg3);
  color: var(--text);
  font-size: 10px;
  white-space: nowrap;
  padding: 3px 6px;
  border-radius: 3px;
  border: 1px solid var(--border);
  pointer-events: none;
  z-index: 100;
}}
.concept-pill.confirmed  {{ background: var(--confirm); }}
.concept-pill.current-alex {{ background: var(--accent); width: 32px; }}
.concept-pill.current-jordan {{ background: var(--partial); width: 32px; }}
.concept-pill.flagged    {{ background: var(--danger); }}
"""

P2_ANCHOR = "/* ── Top bar ─────────────────────────────────────────────────── */"
P2_ANCHOR_ALT = "/* ── Tsrc/competitive_programming_factory/routes/voice.py"

if ".concept-pill" in src:
    print("  SKIP  PATCH 2 — progress pill CSS already present")
    changes.append("PATCH 2 — already applied")
elif P2_ANCHOR in src:
    src = src.replace(P2_ANCHOR, P2_CSS + "\n" + P2_ANCHOR, 1)
    changes.append("PATCH 2 — progress pill CSS added")
else:
    # Try to find any style block close tag
    if "</style>" in src:
        # Insert before first </style>
        src = src.replace("</style>", P2_CSS + "\n</style>", 1)
        changes.append("PATCH 2 — progress pill CSS added (</style> anchor)")
    else:
        _fail("PATCH 2", [P2_ANCHOR, "</style>"])


# =============================================================================
# PATCH 3A — HTML: add progress bar element to topbar
#
# Find the topbar HTML and insert the progress bar div
# =============================================================================

P3A_OLD = '<span class="stage-indicator" id="stage-indicator">Stage —</span>'
P3A_NEW = (
    '<span class="stage-indicator" id="stage-indicator">Stage —</span>\n'
    '      <div class="progress-bar" id="progress-bar"></div>'
)

if 'id="progress-bar"' in src:
    print("  SKIP  PATCH 3A — progress bar HTML already present")
    changes.append("PATCH 3A — already applied")
elif P3A_OLD in src:
    src = src.replace(P3A_OLD, P3A_NEW, 1)
    changes.append("PATCH 3A — progress bar div added to topbar HTML")
else:
    _fail(
        "PATCH 3A",
        [
            '<div id="stage-indicator" class="stage-indicator">Stage 1</div>',
        ],
    )


# =============================================================================
# PATCH 3B — JS: loadProgress() function
#
# Insert after startTimer() function definition
# =============================================================================

LOAD_PROGRESS_FN = """
// ── Progress bar ─────────────────────────────────────────────────
async function loadProgress() {{
  try {{
    const res  = await fetch(`/session/${{SESSION_ID}}/progress`);
    if (!res.ok) return;
    const data = await res.json();
    const bar  = document.getElementById('progress-bar');
    if (!bar || !data.concepts || !data.concepts.length) return;

    bar.innerHTML = data.concepts.map(c => {{
      let cls   = 'concept-pill';
      const st  = c.status;
      if (st === 'confirmed')     cls += ' confirmed';
      else if (st === 'flagged')  cls += ' flagged';
      else if (st === 'current' && data.agent === 'alex')   cls += ' current-alex';
      else if (st === 'current' && data.agent === 'jordan') cls += ' current-jordan';
      // Convert concept_id to display name: "load_balancer" → "Load Balancer"
      const label = c.concept_id.replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
      return `<div class="${{cls}}" title="${{label}}"></div>`;
    }}).join('');
  }} catch(e) {{
    // Non-fatal — progress bar stays empty
  }}
}}

"""

P3B_ANCHOR = "// ── Load stage ───────────────────────────────────────────"
P3B_ANCHOR_ALT = "// ── Load stage ──────────────────────────────────────────────────"

if "async function loadProgress()" in src:
    print("  SKIP  PATCH 3B — loadProgress() already defined")
    changes.append("PATCH 3B — already applied")
elif P3B_ANCHOR in src:
    src = src.replace(P3B_ANCHOR, LOAD_PROGRESS_FN + P3B_ANCHOR, 1)
    changes.append("PATCH 3B — loadProgress() function added")
elif P3B_ANCHOR_ALT in src:
    src = src.replace(P3B_ANCHOR_ALT, LOAD_PROGRESS_FN + P3B_ANCHOR_ALT, 1)
    changes.append("PATCH 3B — loadProgress() function added (alt anchor)")
else:
    _fail(
        "PATCH 3B",
        [
            P3B_ANCHOR,
            P3B_ANCHOR_ALT,
            "// ── Timer ──────────────────────────────────────────────────────",
        ],
    )


# =============================================================================
# PATCH 3C — JS: call loadProgress() inside loadStage()
#
# Add loadProgress() call right after stageData is successfully fetched
# =============================================================================

P3C_OLD = (
    "    const res  = await fetch(`/session/${{SESSION_ID}}/stage/${{n}}`);\n"
    "    stageData  = await res.json();\n"
    "\n"
    "    // Show question + scene based on phase"
)

P3C_NEW = (
    "    const res  = await fetch(`/session/${{SESSION_ID}}/stage/${{n}}`);\n"
    "    stageData  = await res.json();\n"
    "    loadProgress();  // refresh concept pills (non-blocking)\n"
    "\n"
    "    // Show question + scene based on phase"
)

if "loadProgress();  // refresh concept pills" in src:
    print("  SKIP  PATCH 3C — loadProgress() call already in loadStage()")
    changes.append("PATCH 3C — already applied")
elif P3C_OLD in src:
    src = src.replace(P3C_OLD, P3C_NEW, 1)
    changes.append("PATCH 3C — loadProgress() called inside loadStage()")
else:
    _fail(
        "PATCH 3C",
        [
            "    const res  = await fetch(`/session/${{SESSION_ID}}/stage/${{n}}`);\n"
            "    stageData  = await res.json();",
        ],
    )


# =============================================================================
# PATCH 3D — JS: call loadProgress() inside advanceStage()
# =============================================================================

P3D_OLD = (
    "function advanceStage(n) {{\n"
    "  document.getElementById('assessment').className = 'assessment';\n"
    "  document.getElementById('transcript-preview').className = 'transcript-preview';\n"
    "  deactivateWhiteboard();\n"
    "  loadStage(n);\n"
    "}}"
)

P3D_NEW = (
    "function advanceStage(n) {{\n"
    "  document.getElementById('assessment').className = 'assessment';\n"
    "  document.getElementById('transcript-preview').className = 'transcript-preview';\n"
    "  deactivateWhiteboard();\n"
    "  loadProgress();\n"
    "  loadStage(n);\n"
    "}}"
)

if "loadProgress();\n  loadStage(n);\n}}" in src:
    print("  SKIP  PATCH 3D — loadProgress() already in advanceStage()")
    changes.append("PATCH 3D — already applied")
elif P3D_OLD in src:
    src = src.replace(P3D_OLD, P3D_NEW, 1)
    changes.append("PATCH 3D — loadProgress() called inside advanceStage()")
else:
    _fail(
        "PATCH 3D",
        [
            "function advanceStage(n) {{",
            "  loadStage(n);",
        ],
    )


# =============================================================================
# Write + validate
# =============================================================================

VOICE.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print()
    for c in changes:
        print(f"  OK  {c}")
    print()
    print(f"voice.py patched ({len(changes)} changes applied)")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR after patching: {e}")
    VOICE.write_text(original)
    print("voice.py rolled back")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
