path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

old = """        # Clear stage_specs so Jordan's spec is generated fresh
        store.save_field(session_id, "stage_specs", {})"""

new = """        # Only clear stage_specs on first handover so Jordan's spec is reused
        if not store.load_field(session_id, "jordan_spec_ready"):
            store.save_field(session_id, "stage_specs", {})
            store.save_field(session_id, "jordan_spec_ready", True)"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
    for i, l in enumerate(text.splitlines()[160:168], 161):
        print(f"  {i}: {repr(l)}")

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
