path = "src/competitive_programming_factory/routes/stages.py"
lines = open(path).readlines()

# Find start and end of teach_ask function
start = None
end = None
for i, l in enumerate(lines):
    if "async def teach_ask" in l or "def teach_ask" in l:
        start = i
    if start and i > start and l.startswith("@router"):
        end = i
        break

if start is None:
    print("teach_ask not found")
else:
    print(f"Found teach_ask at lines {start + 1}-{end}")
    new_func = '''async def teach_ask(session_id: str, audio: UploadFile = File(...)):
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
    prompt = (
        f"You are Alex, a warm Senior Staff Engineer tutoring a candidate.\\n"
        f"Problem: {problem}\\n"
        f"Concepts covered:\\n{concept_text}\\n\\n"
        f"The candidate says: \\"{transcript}\\"\\n\\n"
        f"Reply in 2-3 sentences. Be encouraging. Address them as {first_name}.\\n"
        f'Return ONLY JSON: {{"reply": "your response"}}'
    )
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    try:
        reply = json.loads(raw).get("reply", raw)
    except Exception:
        reply = raw
    return {
        "verdict":               "PARTIAL",
        "feedback":              reply,
        "probe":                 reply,
        "transcript":            transcript,
        "concepts_demonstrated": [],
        "concepts_missing":      [],
        "next_url":              f"/session/{session_id}/stage/1",
        "session_complete":      False,
    }

'''
    new_lines = lines[:start] + [new_func] + lines[end:]
    open(path, "w").writelines(new_lines)
    print("Replaced function body")

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
