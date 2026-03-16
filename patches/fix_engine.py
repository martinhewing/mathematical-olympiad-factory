path = "src/competitive_programming_factory/engine/session_engine.py"
text = open(path).read()

old = '''    store.save_field(session_id, "stage_specs",       {})
    store.save_field(session_id, "stage_assessments", {})
    store.save(session_id, fsm, dll)

    log.info(
        "session.created",'''

new = '''    store.save_field(session_id, "stage_specs",       {})
    store.save_field(session_id, "stage_assessments", {})

    # Fix: add teach stage to dll so get_or_generate_stage works correctly
    dll = FactoryConversationHistory()
    dll.add_stage("teach_001", "teach")
    store.save(session_id, fsm, dll)

    # Pre-generate lesson so interview page loads instantly
    try:
        get_or_generate_stage(session_id, 1)
        log.info("session.lesson_pregenerated", session_id=session_id)
    except Exception as e:
        log.warning("session.lesson_pregenerate_failed", session_id=session_id, error=str(e))

    log.info(
        "session.created",'''

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found — showing context:")
    for i, l in enumerate(text.splitlines()[48:70], 49):
        print(f"  {i}: {repr(l)}")
