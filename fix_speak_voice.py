path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

old = '''    speak_text = payload.get("text", "").strip()
    if not speak_text:
        raise HTTPException(status_code=422, detail="No text provided")
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        await generate_tts(speak_text, save_path=tmp)'''

new = '''    speak_text = payload.get("text", "").strip()
    if not speak_text:
        raise HTTPException(status_code=422, detail="No text provided")
    req_voice  = payload.get("voice_id", "")
    use_voice  = req_voice if req_voice and req_voice != "ALEX_VOICE" else None
    if not use_voice:
        # pick voice based on requested role
        cfg = _settings()
        use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALEX_VOICE" else cfg.cartesia_voice_id
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        await generate_tts(speak_text, save_path=tmp, voice_id=use_voice)'''

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
