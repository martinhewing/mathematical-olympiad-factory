path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

# Insert before the submit endpoint
old = '@router.post("/session/{session_id}/stage/{stage_n}/submit")'

new = '''@router.post("/session/{session_id}/teach/complete")
def teach_complete(session_id: str):
    """Advance FSM from TEACH to REQUIREMENTS — Alex hands over to Jordan."""
    import os
    from competitive_programming_factory.domain.fsm.states import State
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, dll = result
    from competitive_programming_factory.domain.fsm.states import State as _State
    if fsm.state in {_State.TEACH, _State.TEACH_CHECK}:
        fsm.transition_to(_State.TEACH_CHECK,  trigger="comprehension_skipped")
        fsm.transition_to(_State.REQUIREMENTS, trigger="teach_complete")
        dll.current.confirm({})
        dll.add_stage("requirements_001", "requirements")
        store.save_field(session_id, "stage_specs", {})
        store.save(session_id, fsm, dll)
    # clear cached audio so Jordan's is regenerated
    audio_file = f"/tmp/connectionsphere_audio/{session_id}_stage_1.wav"
    if os.path.exists(audio_file):
        os.remove(audio_file)
    return {"status": "ok", "fsm_state": fsm.state.value}


@router.post("/session/{session_id}/stage/{stage_n}/submit")'''

if '@router.post("/session/{session_id}/stage/{stage_n}/submit")' in text and 'teach/complete' not in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Already exists or pattern not found")
