path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

# Fix 1: In teach/complete, save Alex's spec before clearing
old1 = """        # Clear stage_specs so Jordan's spec is generated fresh
        store.save_field(session_id, "stage_specs", {})
        store.save(session_id, fsm, dll)"""

new1 = """        # Save Alex's spec before clearing, so we can restore on back
        current_specs = store.load_field(session_id, "stage_specs") or {}
        if "1" in current_specs:
            store.save_field(session_id, "teach_spec", current_specs["1"])
        # Clear stage_specs so Jordan's spec is generated fresh
        store.save_field(session_id, "stage_specs", {})
        store.save(session_id, fsm, dll)"""

# Fix 2: In teach/restart, restore Alex's spec
old2 = """    # clear cached audio
    audio_file = f"/tmp/connectionsphere_audio/{session_id}_stage_1.wav"
    if os.path.exists(audio_file):
        os.remove(audio_file)
    return {"status": "ok", "fsm_state": fsm.state.value}


@router.post("/session/{session_id}/teach/complete")"""

new2 = """    # Restore Alex's cached spec so page loads instantly
    teach_spec = store.load_field(session_id, "teach_spec")
    if teach_spec:
        store.save_field(session_id, "stage_specs", {"1": teach_spec})
    else:
        store.save_field(session_id, "stage_specs", {})
    return {"status": "ok", "fsm_state": fsm.state.value}


@router.post("/session/{session_id}/teach/complete")"""

if old1 in text:
    text = text.replace(old1, new1)
    print("✓ Fixed teach/complete")
else:
    print("✗ teach/complete pattern not found")

if old2 in text:
    text = text.replace(old2, new2)
    print("✓ Fixed teach/restart")
else:
    print("✗ teach/restart pattern not found")
    for i, l in enumerate(text.splitlines()[78:92], 79):
        print(f"  {i}: {repr(l)}")

open(path, "w").write(text)

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
