async def teach_ask(
    session_id: str,
    audio:  UploadFile        = File(...),
    images: list[UploadFile]  = File(default=[]),
):
    """Candidate asks Alex a question during TEACH phase via voice + optional diagrams."""
    from competitive_programming_factory.config import get_settings
    from competitive_programming_factory.voice.stt import transcribe
    import anthropic, json, re, base64
    if not store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # ── 1. Transcribe ─────────────────────────────────────────────────────
    audio_bytes  = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript   = await transcribe(audio_bytes, content_type=content_type)

    # ── 2. Short-circuit accidental/empty recordings ──────────────────────
    if len(transcript.split()) < 8:
        nudge = (
            "Sorry, I didn't catch that — it sounded like the mic cut off. "
            "Take your time and ask when you're ready."
        )
        return {
            "verdict": "PARTIAL", "feedback": nudge, "probe": nudge,
            "transcript": transcript, "concepts_demonstrated": [],
            "concepts_missing": [], "next_url": f"/session/{session_id}/stage/1",
            "session_complete": False,
        }

    # ── 3. Load session state ─────────────────────────────────────────────
    spec       = engine.get_or_generate_stage(session_id, 1)
    first_name = store.load_field(session_id, "candidate_first_name") or "there"
    problem    = store.load_field(session_id, "problem_statement") or ""

    result = engine.load_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    fsm, dll = result

    # ── 4. Extract the SINGLE concept in scope for this segment ──────────
    concept_name        = spec.get("stage_title") or spec.get("concept_id", "the current concept")
    concept_explanation = spec.get("explanation", "")
    concept_analogy     = spec.get("analogy", "")
    concept_probe_warn  = spec.get("probe_warning", "")
    if not concept_explanation and spec.get("concepts"):
        c = spec["concepts"][0]
        concept_name        = c.get("name", concept_name)
        concept_explanation = c.get("explanation", "")
        concept_probe_warn  = c.get("probe_warning", "")

    # ── 5. Build already-covered guard from Alex's prior turns ────────────
    alex_prior = [
        t["content"] for t in (dll.current.turns if dll.current else [])
        if t.get("speaker") == "alex" and t.get("content")
    ]
    already_covered = (
        "WHAT YOU HAVE ALREADY SAID (do NOT repeat any of this):\n"
        + "\n".join(f"- {t[:120]}" for t in alex_prior)
        if alex_prior else
        "Nothing covered yet — this is your opening."
    )

    # ── 6. Append candidate turn to DLL ──────────────────────────────────
    candidate_content = transcript + (' [candidate submitted diagram(s)]' if images else '')
    dll.current.add_turn(speaker="candidate", content=candidate_content, turn_type="teach_question")

    # ── 7. Build message history from DLL ────────────────────────────────
    history  = dll.context_window_build(max_turns=20)
    messages: list[dict] = []
    for turn in history:
        speaker = turn.get("speaker", "")
        content = turn.get("content", "")
        if not content:
            continue
        role = "user" if speaker == "candidate" else "assistant"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + content
        else:
            messages.append({"role": role, "content": content})
    if not messages:
        messages = [{"role": "user", "content": transcript}]
    if messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": transcript})

    # Attach diagram images to last user message
    if images:
        img_blocks = []
        for img in images:
            img_bytes = await img.read()
            if img_bytes:
                mt = img.content_type or "image/png"
                img_blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(img_bytes).decode()},
                })
        if img_blocks:
            existing = messages[-1]["content"]
            messages[-1]["content"] = img_blocks + [{"type": "text", "text": existing}]

    # ── 8. System prompt scoped strictly to the current concept ──────────
    system_prompt = (
        f"You are Alistair, a warm and precise tutor helping {first_name} master competitive programming and mathematical olympiad problems.\n"
        + "\n━━━ YOUR SCOPE THIS SEGMENT — HARD LIMIT ━━━\n"
        + f"You are teaching ONE concept and ONE concept only: **{concept_name}**.\n"
        + f"Problem context: {problem}\n"
        + f"What {concept_name} means: {concept_explanation}\n"
        + (f"Key probe point: {concept_probe_warn}\n" if concept_probe_warn else "")
        + (f"Your analogy: {concept_analogy}\n" if concept_analogy else "")
        + "\nRULES:\n"
        + f"- ONLY discuss {concept_name}. Nothing else.\n"
        + "- If the candidate asks about a different concept, redirect warmly: "
          f"'Great question — we'll cover that in its own segment. "
          f"For now let's stay focused on {concept_name}.'\n"
        + "- Do NOT preview, hint at, or explain concepts from other segments.\n"
        + "- Do NOT expand the scope even if the candidate pushes you to.\n"
        + "\n" + already_covered + "\n\n"
        + "Respond in 2-4 sentences. Do NOT repeat anything in the ALREADY SAID list. "
        + 'Return ONLY JSON: {"reply": "your response"}'
    )

    # ── 9. Call Claude ────────────────────────────────────────────────────
    cfg    = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    msg    = client.messages.create(
        model      = "claude-sonnet-4-20250514",
        max_tokens = 400,
        system     = system_prompt,
        messages   = messages,
    )
    raw = msg.content[0].text.strip()
    try:
        clean = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        reply = json.loads(clean).get("reply", clean)
    except Exception:
        reply = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    # ── 10. Persist Alistair reply and save ──────────────────────────────
    dll.current.add_turn(speaker="alex", content=reply, turn_type="teach_response")
    store.save(session_id, fsm, dll)

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

