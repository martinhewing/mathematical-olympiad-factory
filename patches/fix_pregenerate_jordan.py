path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

old = """        # keep stage_specs cache on restart so lesson loads instantly
        store.save(session_id, fsm, dll)
    # clear cached audio so Jordan's is regenerated
    audio_file = f"/tmp/connectionsphere_audio/{session_id}_stage_1.wav"
    if os.path.exists(audio_file):
        os.remove(audio_file)
    return {"status": "ok", "fsm_state": fsm.state.value}"""

new = """        # Clear stage_specs so Jordan's spec is generated fresh
        store.save_field(session_id, "stage_specs", {})
        store.save(session_id, fsm, dll)
    # Clear cached audio so Jordan's voice is used
    audio_file = f"/tmp/connectionsphere_audio/{session_id}_stage_1.wav"
    if os.path.exists(audio_file):
        os.remove(audio_file)
    # Pre-generate Jordan's stage spec so handover is instant
    try:
        engine.get_or_generate_stage(session_id, 1)
    except Exception as e:
        pass  # non-fatal — will generate on demand
    return {"status": "ok", "fsm_state": fsm.state.value}"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
