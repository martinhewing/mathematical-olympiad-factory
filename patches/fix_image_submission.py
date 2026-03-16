path_s = "src/competitive_programming_factory/routes/stages.py"
path_v = "src/competitive_programming_factory/routes/voice.py"

import py_compile

# ── stages.py: teach_ask accepts optional images ─────────────────
text = open(path_s).read()

old = '''async def teach_ask(session_id: str, audio: UploadFile = File(...)):
    """Candidate asks Alex a question during TEACH phase via voice."""
    from competitive_programming_factory.config import get_settings
    from competitive_programming_factory.voice.stt import transcribe
    import anthropic, json, re
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript   = await transcribe(audio_bytes, content_type=content_type)
    spec       = engine.get_or_generate_stage(session_id, 1)
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    problem    = store.load_field(session_id, "problem_statement") or ""
    concepts   = spec.get("concepts", [])
    concept_text = "\\n".join(f"- {c.get('name','')}: {c.get('explanation','')}" for c in concepts)
    prompt = (
        f"You are Alex, a warm Senior Staff Engineer tutoring a candidate.\\n"
        f"Problem: {problem}\\n"
        f"Concepts covered:\\n{concept_text}\\n\\n"
        f"The candidate says: \\"{transcript}\\"\\n\\n"
        f"Reply in 2-3 sentences. Be encouraging. Address them as {first_name}.\\n"
        f\'Return ONLY JSON: {{"reply": "your response"}}\'
    )
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )'''

new = '''async def teach_ask(
    session_id: str,
    audio: UploadFile = File(...),
    images: list[UploadFile] = File(default=[]),
):
    """Candidate asks Alex a question during TEACH phase via voice + optional diagrams."""
    from competitive_programming_factory.config import get_settings
    from competitive_programming_factory.voice.stt import transcribe
    import anthropic, json, re, base64
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript   = await transcribe(audio_bytes, content_type=content_type)
    spec       = engine.get_or_generate_stage(session_id, 1)
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    problem    = store.load_field(session_id, "problem_statement") or ""
    concepts   = spec.get("concepts", [])
    concept_text = "\\n".join(f"- {c.get('name','')}: {c.get('explanation','')}" for c in concepts)
    prompt_text = (
        f"You are Alex, a warm Senior Staff Engineer tutoring a candidate.\\n"
        f"Problem: {problem}\\n"
        f"Concepts covered:\\n{concept_text}\\n\\n"
        f"The candidate says: \\"{transcript}\\"\\n\\n"
        + ("The candidate has also shared diagram(s) of their design. Review them as part of your feedback.\\n\\n" if images else "")
        + f"Reply in 2-3 sentences. Be encouraging. Address them as {first_name}.\\n"
        + \'Return ONLY JSON: {"reply": "your response"}\'
    )
    # Build message content — text + optional images
    user_content = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            media_type = img.content_type or "image/png"
            user_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type,
                           "data": base64.b64encode(img_bytes).decode()},
            })
    user_content.append({"type": "text", "text": prompt_text})
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": user_content}],
    )'''

if old in text:
    open(path_s, "w").write(text.replace(old, new))
    print("✓ teach_ask updated")
else:
    print("✗ teach_ask not found")

py_compile.compile(path_s, doraise=True)
print("✓ stages.py syntax OK")

# ── voice.py: stage voice endpoint accepts images, JS sends them ──
text = open(path_v).read()

old_endpoint = '''    audio:      UploadFile = File(...),
):
    """
    Submit spoken answer. Transcribes via Cartesia STT → Claude assessment.
    Returns same JSON as text submit + transcript field.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/wav"

    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Audio too short")

    transcript = await transcribe(audio_bytes, content_type=content_type)

    if len(transcript.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="We couldn't hear that clearly. Check your microphone is connected and try again — speak for at least 3 seconds.",
        )

    assessment = engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = transcript,
    )
    # Convert Pydantic model or dict to plain dict
    if hasattr(assessment, "model_dump"):
        assessment = assessment.model_dump()
    return {**assessment, "transcript": transcript, "input_mode": "voice"}'''

new_endpoint = '''    audio:      UploadFile = File(...),
    images:     list[UploadFile] = File(default=[]),
):
    """
    Submit spoken answer + optional diagrams. Transcribes via STT → Claude assessment.
    Returns same JSON as text submit + transcript field.
    """
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/wav"

    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Audio too short")

    transcript = await transcribe(audio_bytes, content_type=content_type)

    if len(transcript.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="We couldn't hear that clearly. Check your microphone is connected and try again — speak for at least 3 seconds.",
        )

    # Attach images to transcript for Claude assessment
    image_data = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            import base64
            image_data.append({
                "media_type": img.content_type or "image/png",
                "data": base64.b64encode(img_bytes).decode(),
            })

    assessment = engine.process_submission(
        session_id = session_id,
        stage_n    = stage_n,
        answer     = transcript,
        images     = image_data,
    )
    # Convert Pydantic model or dict to plain dict
    if hasattr(assessment, "model_dump"):
        assessment = assessment.model_dump()
    return {**assessment, "transcript": transcript, "input_mode": "voice"}'''

if old_endpoint in text:
    text = text.replace(old_endpoint, new_endpoint)
    print("✓ stage voice endpoint updated")
else:
    print("✗ stage voice endpoint not found")

# ── JS: bundle whiteboard images into FormData on submit ──────────
old_js = '''  const form = new FormData();'''
new_js = '''  // Attach any whiteboard images
  const thumbImgs = document.querySelectorAll('.whiteboard-thumb img');
  const imageFiles = [];
  for (const img of thumbImgs) {{
    const res  = await fetch(img.src);
    const blob = await res.blob();
    imageFiles.push(new File([blob], 'diagram.png', {{type: blob.type}}));
  }}
  const form = new FormData();
  imageFiles.forEach(f => form.append('images', f));'''

if old_js in text:
    text = text.replace(old_js, new_js)
    print("✓ JS FormData updated")
else:
    print("✗ JS FormData not found")

open(path_v, "w").write(text)
py_compile.compile(path_v, doraise=True)
print("✓ voice.py syntax OK")
