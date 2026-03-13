"""
patch_schemas_e.py

Run from connectionsphere-factory repo root:
    python3 patch_schemas_e.py

Adds two optional fields to AssessmentResponse in schemas.py:
  diagram_request  — dict | None   Jordan's diagram request payload
  diagram_scores   — list[dict]    rubric scores from diagram_evaluator

The UI (patch C) already reads both fields from the assessment JSON.
This patch makes Pydantic validate and serialise them correctly.
"""

import pathlib, py_compile, sys, tempfile, os

SCHEMAS = pathlib.Path("src/connectionsphere_factory/models/schemas.py")

if not SCHEMAS.exists():
    sys.exit(f"ERROR: {SCHEMAS} not found. Run from repo root.")

src      = SCHEMAS.read_text()
original = src

OLD = (
    "class AssessmentResponse(BaseModel):\n"
    "    verdict:               str\n"
    "    feedback:              str\n"
    "    probe:                 str | None\n"
    "    concepts_demonstrated: list[str]\n"
    "    concepts_missing:      list[str]\n"
    "    next_url:              str | None\n"
    "    session_complete:      bool = False"
)

NEW = (
    "class AssessmentResponse(BaseModel):\n"
    "    verdict:               str\n"
    "    feedback:              str\n"
    "    probe:                 str | None\n"
    "    concepts_demonstrated: list[str]\n"
    "    concepts_missing:      list[str]\n"
    "    next_url:              str | None\n"
    "    session_complete:      bool = False\n"
    "    # Diagram fields — set by process_submission when Jordan requests / evaluates a drawing\n"
    "    diagram_request:  dict | None = None   # Jordan's diagram_request payload (nullable)\n"
    "    diagram_scores:   list[dict]  = Field(default_factory=list)  # rubric scores from evaluator"
)

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("OK  AssessmentResponse: diagram_request + diagram_scores added")
else:
    sys.exit("FAIL — AssessmentResponse block not found in schemas.py")

# Ensure Field is imported (it already is in the existing file, but guard anyway)
if "from pydantic import BaseModel, Field" not in src:
    src = src.replace(
        "from pydantic import BaseModel",
        "from pydantic import BaseModel, Field",
        1,
    )
    print("OK  Added Field to pydantic imports")
else:
    print("OK  Field already imported")

SCHEMAS.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print("OK  schemas.py syntax-valid")
except py_compile.PyCompileError as e:
    print(f"FAIL syntax error: {e}")
    SCHEMAS.write_text(original)
    print("     schemas.py rolled back")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
