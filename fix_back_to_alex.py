path = "src/connectionsphere_factory/routes/stages.py"
text = open(path).read()

old = '@router.post("/session/{session_id}/teach/complete")'
new = '''@router.post("/session/{session_id}/teach/restart")
def teach_restart(session_id: str):
    """Reset FSM back to TEACH so candidate can review Alex lesson again."""
    import os
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, dll = result
    from connectionsphere_factory.domain.fsm.states import State as _State
    fsm.transition_to(_State.TEACH, trigger="back_to_teach")
    # Reset dll to teach stage
    dll = engine.FactoryConversationHistory()
    dll.add_stage("teach_001", "teach")
    store.save_field(session_id, "stage_specs", {})
    store.save(session_id, fsm, dll)
    # clear cached audio
    audio_file = f"/tmp/connectionsphere_audio/{session_id}_stage_1.wav"
    if os.path.exists(audio_file):
        os.remove(audio_file)
    return {"status": "ok", "fsm_state": fsm.state.value}


@router.post("/session/{session_id}/teach/complete")'''

if 'teach/restart' not in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed stages.py")
else:
    print("Already exists")
