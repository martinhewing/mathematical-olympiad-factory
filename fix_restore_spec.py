path = "src/connectionsphere_factory/routes/stages.py"
text = open(path).read()

old = "    # keep stage_specs cache on restart so lesson loads instantly"

new = """    # Restore Alex's cached spec so page loads instantly
    teach_spec = store.load_field(session_id, "teach_spec")
    if teach_spec:
        store.save_field(session_id, "stage_specs", {"1": teach_spec})
    else:
        store.save_field(session_id, "stage_specs", {})
    # keep stage_specs cache on restart so lesson loads instantly"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    for i, l in enumerate(text.splitlines()[79:90], 80):
        print(f"  {i}: {repr(l)}")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
