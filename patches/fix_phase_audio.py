# Fix 1: audio_path in tts.py
tts_path = "src/competitive_programming_factory/voice/tts.py"
tts = open(tts_path).read()

old1 = '''def audio_path(session_id: str, stage_n: int) -> str:
    settings = _settings()
    return f"{settings.audio_storage_dir}/{session_id}_stage_{stage_n}.wav"'''

new1 = '''def audio_path(session_id: str, stage_n: int, phase: str = "interview") -> str:
    settings = _settings()
    return f"{settings.audio_storage_dir}/{session_id}_{phase}_stage_{stage_n}.wav"'''

if old1 in tts:
    open(tts_path, "w").write(tts.replace(old1, new1))
    print("✓ Fixed tts.py audio_path")
else:
    print("✗ tts.py pattern not found")

# Fix 2: voice.py - pass phase to audio_path
voice_path = "src/competitive_programming_factory/routes/voice.py"
text = open(voice_path).read()

# get_stage_audio_file endpoint - needs to know phase from FSM
old2 = """    savepath = audio_path(session_id, stage_n)
    if not Path(savepath).exists():
        text, voice_id = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath, voice_id=voice_id)
    return Response(
        content    = Path(savepath).read_bytes(),"""

new2 = """    import competitive_programming_factory.session_store as _store
    _fsm_result = engine.load_session(session_id)
    _phase = "teach" if (_fsm_result and _fsm_result[0].state.value in {"Teach", "Teach Comprehension Check"}) else "interview"
    savepath = audio_path(session_id, stage_n, _phase)
    if not Path(savepath).exists():
        text, voice_id = _stage_text(session_id, stage_n)
        await generate_tts(text, save_path=savepath, voice_id=voice_id)
    return Response(
        content    = Path(savepath).read_bytes(),"""

if old2 in text:
    text = text.replace(old2, new2)
    print("✓ Fixed get_stage_audio_file")
else:
    print("✗ get_stage_audio_file pattern not found")

open(voice_path, "w").write(text)

import py_compile

for p in [tts_path, voice_path]:
    try:
        py_compile.compile(p, doraise=True)
        print(f"✓ {p} OK")
    except py_compile.PyCompileError as e:
        print(f"✗ {p}: {e}")
