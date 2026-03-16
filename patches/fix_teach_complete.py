import pathlib
p = pathlib.Path("src/competitive_programming_factory/routes/stages.py")
src = p.read_text()

OLD = ('    if fsm.state in {\n'
       '        _State.TEACH, _State.TEACH_CHECK,\n'
       '        _State.CONCEPT_TEACH, _State.CONCEPT_TEACH_CHECK, _State.CONCEPT_STAGE,\n'
       '    }:\n'
       '        fsm.transition_to(_State.TEACH_CHECK,  trigger="comprehension_skipped")\n'
       '        fsm.transition_to(_State.REQUIREMENTS, trigger="teach_complete")\n'
       '        dll.current.confirm({})\n'
       '        dll.add_stage("requirements_001", "requirements")\n'
       '        # Save Alex\'s spec before clearing, so we can restore on back\n'
       '        current_specs = store.load_field(session_id, "stage_specs") or {}\n'
       '        if "1" in current_specs:\n'
       '            store.save_field(session_id, "teach_spec", current_specs["1"])\n'
       '\n'
       '\n'
       '        store.save(session_id, fsm, dll)')

NEW = ('    if fsm.state in {_State.CONCEPT_TEACH, _State.CONCEPT_TEACH_CHECK}:\n'
       '        # Concept session: skip Alex check, hand to Jordan for this concept\n'
       '        fsm.transition_to(_State.CONCEPT_STAGE, trigger="comprehension_skipped")\n'
       '        dll.current.confirm({})\n'
       '        store.save(session_id, fsm, dll)\n'
       '    elif fsm.state in {_State.TEACH, _State.TEACH_CHECK}:\n'
       '        # Legacy session\n'
       '        fsm.transition_to(_State.TEACH_CHECK,  trigger="comprehension_skipped")\n'
       '        fsm.transition_to(_State.REQUIREMENTS, trigger="teach_complete")\n'
       '        dll.current.confirm({})\n'
       '        dll.add_stage("requirements_001", "requirements")\n'
       '        current_specs = store.load_field(session_id, "stage_specs") or {}\n'
       '        if "1" in current_specs:\n'
       '            store.save_field(session_id, "teach_spec", current_specs["1"])\n'
       '        store.save(session_id, fsm, dll)')

if OLD not in src:
    print("FAILED - block not found")
    raise SystemExit(1)

p.write_text(src.replace(OLD, NEW, 1))
print("OK")