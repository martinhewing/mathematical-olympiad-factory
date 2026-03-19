path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

old = '''@router.post("/session/{session_id}/teach/ask")
def teach_ask(session_id: str, answer: str = Form(...)):
    """Candidate asks Alex a question during TEACH phase."""
    from competitive_programming_factory.engine.session_engine import render_and_call
    from competitive_programming_factory.config import get_settings
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    spec = engine.get_or_generate_stage(session_id, 1)
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    problem    = store.load_field(session_id, "problem_statement") or ""
    concepts   = spec.get("concepts", [])
    concept_text = "\\n".join(f"- {c.get('name','')}: {c.get('explanation','')}" for c in concepts)
    prompt = f"""You are Alex, a warm Senior Staff Engineer tutoring a candidate before their system design interview.
Problem: {problem}
Key concepts covered:
{concept_text}
The candidate asks: "{answer}"
Reply in 2-3 sentences. Be encouraging and use a concrete analogy. Address them as {first_name}.
Return ONLY JSON: {{"reply": "your response"}}"""
    import anthropic
    cfg = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    raw = msg.content[0].text.strip()
    try:
        data = json.loads(raw)
        reply = data.get("reply", raw)
    except Exception:
        reply = raw
    return {
        "verdict":               "PARTIAL",
        "feedback":              reply,
        "probe":                 reply,
        "concepts_demonstrated": [],
        "concepts_missing":      [],
        "next_url":              f"/session/{session_id}/stage/1",
        "session_complete":      False,
    }'''

new = '''@router.post("/session/{session_id}/teach/ask")
async def teach_ask(session_id: str, audio: UploadFile = File(...)):
    """Candidate asks Alex a question during TEACH phase via voice."""
    from competitive_programming_factory.config import get_settings
    from competitive_programming_factory.voice.stt import transcribe
    import anthropic, json
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
    prompt = f"""You are Alex, a warm Senior Staff Engineer tutoring a candidate before their system design interview.
Problem: {problem}
Key concepts covered:
{concept_text}

The candidate says: "{transcript}"

Reply in 2-3 sentences. Be encouraging and use a concrete analogy. Address them as {first_name}.
Return ONLY JSON: {{"reply": "your response"}}"""
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{{"role": "user", "content": prompt}}],
    )
    raw = msg.content[0].text.strip()
    try:
        reply = json.loads(raw).get("reply", raw)
    except Exception:
        reply = raw
    return {{
        "verdict":               "PARTIAL",
        "feedback":              reply,
        "probe":                 reply,
        "transcript":            transcript,
        "concepts_demonstrated": [],
        "concepts_missing":      [],
        "next_url":              f"/session/{{session_id}}/stage/1",
        "session_complete":      False,
    }}'''

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found — checking what's there:")
    for i, l in enumerate(text.splitlines()[87:125], 88):
        print(f"  {i}: {repr(l)}")
