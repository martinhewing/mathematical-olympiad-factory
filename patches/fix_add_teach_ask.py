path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

endpoint = '''@router.post("/session/{session_id}/teach/ask")
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
    concept_text = "\n".join(f"- {c.get('name','')}: {c.get('explanation','')}" for c in concepts)
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
        messages=[{{"role": "user", "content": prompt}}],
    )
    import json
    raw = msg.content[0].text.strip()
    try:
        data = json.loads(raw)
        reply = data.get("reply", raw)
    except Exception:
        reply = raw
    return {{
        "verdict":               "PARTIAL",
        "feedback":              reply,
        "probe":                 reply,
        "concepts_demonstrated": [],
        "concepts_missing":      [],
        "next_url":              f"/session/{{session_id}}/stage/1",
        "session_complete":      False,
    }}


'''

if 'teach/ask' not in text:
    # insert before teach/complete
    target = '@router.post("/session/{session_id}/teach/complete")'
    if target in text:
        text = text.replace(target, endpoint + target)
        open(path, "w").write(text)
        print("Fixed")
    else:
        print("teach/complete not found either — appending before last route")
        # append before submit
        target2 = '@router.post("/session/{session_id}/stage/{stage_n}/submit")'
        text = text.replace(target2, endpoint + target2)
        open(path, "w").write(text)
        print("Fixed via submit target")
else:
    print("Already exists")
