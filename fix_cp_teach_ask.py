"""
fix_cp_teach_ask.py
Run from competitive-programming-factory repo root: python3 fix_cp_teach_ask.py

Requires teach_ask_cp_new.py in the same directory.
Splices the fully upgraded teach_ask function body into
src/competitive_programming_factory/routes/stages.py.
"""

import os
import pathlib
import py_compile
import sys
import tempfile

STAGES = pathlib.Path("src/competitive_programming_factory/routes/stages.py")
NEW_FUNC = pathlib.Path("teach_ask_cp_new.py")

for f in [STAGES, NEW_FUNC]:
    if not f.exists():
        sys.exit(f"ERROR: {f} not found — run from competitive-programming-factory repo root")

src = STAGES.read_text()
original = src
new_body = NEW_FUNC.read_text()

# ── Find teach_ask function boundaries ───────────────────────────────────────
lines = src.splitlines(keepends=True)
start = None
end = None
for i, line in enumerate(lines):
    if "async def teach_ask(" in line or "def teach_ask(" in line:
        start = i
    if (
        start is not None
        and i > start
        and (
            line.startswith("@router")
            or ((line.startswith("def ") or line.startswith("async def ")) and i > start + 2)
        )
    ):
        end = i
        break

if start is None or end is None:
    sys.exit(f"teach_ask not found in {STAGES}: start={start} end={end}")

print(f"teach_ask found at lines {start + 1}–{end}")

old_body = "".join(lines[start:end])

if "YOUR SCOPE THIS SEGMENT" in old_body:
    print("SKIP — teach_ask already upgraded")
    sys.exit(0)

if "audio" not in old_body:
    print("UNEXPECTED — 'audio' not in teach_ask body; inspect manually")
    sys.exit(1)

# Ensure new body ends with a blank line
if not new_body.endswith("\n\n"):
    new_body = new_body.rstrip("\n") + "\n\n"

new_lines = lines[:start] + [new_body] + lines[end:]
STAGES.write_text("".join(new_lines))

# ── Syntax check ─────────────────────────────────────────────────────────────
tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(STAGES.read_text())
    py_compile.compile(tmp, doraise=True)
    print("OK — teach_ask fully upgraded:")
    print("  - Stateful DLL-backed conversation history")
    print("  - Scoped strictly to single concept per segment")
    print("  - Already-covered guard (no repetition)")
    print("  - Accidental mic press guard (< 8 words)")
    print("  - Alistair persona (not generic OOD wording)")
    print("  - Model: claude-sonnet-4-20250514")
except py_compile.PyCompileError as e:
    STAGES.write_text(original)
    print(f"SYNTAX ERROR — rolled back: {e}")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
